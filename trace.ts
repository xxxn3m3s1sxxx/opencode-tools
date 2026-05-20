import type { Plugin } from "@opencode-ai/plugin";
import { tool } from "@opencode-ai/plugin";
import { spawnSync } from "child_process";
import { detectPython, splitArgs, findToolPy } from "./utils.ts";

interface TraceCaller {
  type: string; caller: string; callee: string; file: string; line: number; context?: string;
}
interface TraceChain {
  symbol: string; callees: string[];
}
interface TraceResult {
  symbol: string; project: string; depth: number;
  callers: TraceCaller[]; chain: TraceChain[];
}

function relPath(file: string, root: string): string {
  if (!root) return file;
  const rel = file.replace(root.replace(/\\/g, "/"), "").replace(/^[/\\]/, "");
  return rel || file;
}

function formatOutput(symbol: string, data: TraceResult): string {
  const lines: string[] = [];
  const root = data.project;
  lines.push(`trace: \`${symbol}\` (depth=${data.depth})`);
  lines.push("");

  const callers = data.callers || [];
  if (callers.length > 0) {
    const unique: Array<{ caller: string; file: string; line: number; context?: string }> = [];
    const seen = new Set<string>();
    for (const c of callers) {
      const key = `${c.file}:${c.line}`;
      if (!seen.has(key)) {
        seen.add(key);
        unique.push({ caller: c.caller || "(module)", file: c.file, line: c.line, context: c.context });
      }
    }
    lines.push(`  [callers] ${unique.length} unique`);
    for (const c of unique.slice(0, 15)) {
      const path = relPath(c.file, root);
      const ctx = c.context ? `  -- ${c.context.slice(0, 80)}` : "";
      lines.push(`    ${c.caller.padEnd(25)}  ${path}:${c.line}${ctx}`);
    }
    if (unique.length > 15) lines.push(`    ... and ${unique.length - 15} more`);
    lines.push("");
  }

  const chain = data.chain || [];
  if (chain.length > 0) {
    lines.push(`  [chain] ${data.symbol}`);
    for (const level of chain) {
      for (const callee of level.callees || []) {
        lines.push(`    ${level.symbol} -> ${callee}`);
      }
    }
    lines.push("");
  }

  if (callers.length === 0 && chain.length === 0) {
    lines.push("  (no call chain found)");
  }
  return lines.join("\n");
}

function runPy(args: string[], cwd: string): string {
  if (!args.includes("--json")) args.push("--json");
  const proc = spawnSync(detectPython(), [findToolPy("trace.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 30000 });
  if (proc.error) throw proc.error;
  if (proc.status !== 0) throw new Error(proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
  return proc.stdout;
}

export default (async () => {
  const z = tool.schema
  return {
    tool: {
      trace: tool({
        description: `Recursive call chain analyzer. Follow execution paths through the codebase.

Usage:
  trace <symbol> [-d N]         Show call chain N levels deep (default: 2)
  trace <symbol> --up           Show callers only (who calls this)
  trace <symbol> --down         Show callees only (what this calls)
  trace <file>:<line>           Infer symbol from context

Examples:
  trace forward                 Trace forward() through the codebase
  trace generate_c --down -d 3  Deep dive into generate_c callees
  trace AtlasModel --up         Who references AtlasModel`,
        args: {
          command: z.string().describe("Command (e.g. 'forward', 'generate_c --down -d 3', 'AtlasModel --up')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const args = splitArgs(command.trim().replace(/^trace(?:\.py)?\s+/, ""));
            const symbol = args.filter((a: string) => !a.startsWith("-")).pop() || "unknown";
            const stdout = runPy(args, cwd);
            let data: TraceResult;
            try { data = JSON.parse(stdout); } catch { return stdout; }
            return formatOutput(symbol, data);
          } catch (err: any) {
            return `trace error: ${err.message}`;
          }
        },
      }),
    },
  };
}) satisfies Plugin;
