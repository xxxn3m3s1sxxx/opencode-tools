import { Tool } from "@opencode-ai/sdk";
import { spawnSync } from "child_process";

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
  const proc = spawnSync("python", ["trace.py", ...args, "--json"], { cwd, encoding: "utf-8", timeout: 30000 });
  if (proc.error) throw proc.error;
  if (proc.status !== 0) throw new Error(proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
  return proc.stdout;
}

export const tools: Tool[] = [
  {
    name: "trace",
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

    parameters: {
      type: "object", properties: {
        command: {
          type: "string",
          description: "Command (e.g. 'forward', 'generate_c --down -d 3', 'AtlasModel --up')",
        },
      },
      required: ["command"],
    },

    execute: async ({ command }: { command: string }, context) => {
      try {
        const cwd = context?.cwd || process.cwd();
        const args = command.trim().split(/\s+/);
        const symbol = args.find((a: string) => !a.startsWith("-")) || "unknown";
        const stdout = runPy(args, cwd);
        let data: TraceResult;
        try { data = JSON.parse(stdout); } catch { return { content: [{ type: "text", text: stdout }] }; }
        return { content: [{ type: "text", text: formatOutput(symbol, data) }] };
      } catch (err: any) {
        return { content: [{ type: "text", text: `trace error: ${err.message}` }], isError: true };
      }
    },
  },
];

export default { tools };
