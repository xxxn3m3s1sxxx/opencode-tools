import type { Plugin } from "@opencode-ai/plugin";
import { tool } from "@opencode-ai/plugin";
import { spawnSync } from "child_process";

let _python: string | null = null
function detectPython(): string {
  if (_python) return _python
  const candidates = process.platform === "win32"
    ? [["python"], ["py", "-3"], ["py"], ["python3"]]
    : [["python3"], ["python"], ["py", "-3"], ["py"]]
  for (const [cmd, ...args] of candidates) {
    try {
      const r = spawnSync(cmd, [...args, "-c", "import sys; print(sys.executable)"], { encoding: "utf-8", timeout: 3000 })
      if (r.status === 0 && !r.error) {
        const fp = (r.stdout || "").trim().split(/\r?\n/)[0].trim()
        if (fp) { _python = fp; return fp }
      }
    } catch { /* try next */ }
  }
  _python = "python"; return _python
}

function splitArgs(cmd: string): string[] {
  const args: string[] = []; const re = /[^\s"']+|"([^"]*)"|'([^']*)'/g; let m
  while ((m = re.exec(cmd)) !== null) args.push(m[1] || m[2] || m[0])
  return args
}

interface ImpactResult {
  symbol: string;
  project: string;
  definitions: Array<{ type: string; name: string; file: string; line: number; context?: string }>;
  references: Array<{ type: string; file: string; line: number; context?: string }>;
  tests: Array<{ type: string; file: string; line: number; context?: string }>;
  callees: Array<{ name: string; file: string; line: number }>;
}

function fmtCount(n: number, label: string): string {
  return n === 0 ? `0 ${label}` : `${n} ${label}${n !== 1 ? "s" : ""}`;
}

function relPath(file: string, root: string): string {
  if (!root) return file;
  const rel = file.replace(root.replace(/\\/g, "/"), "").replace(/^[/\\]/, "");
  return rel || file;
}

function formatOutput(symbol: string, data: ImpactResult): string {
  const lines: string[] = [];
  const root = data.project;

  lines.push(`impact: \`${symbol}\``);
  lines.push("");

  // Definitions
  const defs = data.definitions || [];
  lines.push(`  [def] ${fmtCount(defs.length, "occurrence")}`);
  if (defs.length === 0) {
    lines.push("    (not found)");
  }
  for (const d of defs.slice(0, 5)) {
    const path = relPath(d.file, root);
    const ctx = d.context ? `  -- ${d.context}` : "";
    lines.push(`    ${path}:${d.line}  (${d.type})${ctx}`);
  }
  if (defs.length > 5) {
    lines.push(`    ... and ${defs.length - 5} more`);
  }

  // References (non-test)
  const isTest = (f: string) => /test_/.test(f.replace(/\\/g, "/"));
  const refs = (data.references || []).filter((r) => !isTest(r.file));
  lines.push("");
  lines.push(`  [ref] ${fmtCount(refs.length, "occurrence")}`);
  for (const r of refs.slice(0, 10)) {
    const path = relPath(r.file, root);
    const ctx = r.context ? `  -- ${r.context}` : "";
    lines.push(`    ${path}:${r.line}${ctx}`);
  }
  if (refs.length > 10) {
    lines.push(`    ... and ${refs.length - 10} more`);
  }

  // Tests
  const tests = data.tests || [];
  lines.push("");
  lines.push(`  [test] ${fmtCount(tests.length, "occurrence")}`);
  for (const t of tests.slice(0, 10)) {
    const path = relPath(t.file, root);
    const ctx = t.context ? `  -- ${t.context}` : "";
    lines.push(`    ${path}:${t.line}${ctx}`);
  }
  if (tests.length > 10) {
    lines.push(`    ... and ${tests.length - 10} more`);
  }

  // Call graph (limited)
  const callees = data.callees || [];
  if (callees.length > 0) {
    lines.push("");
    const uniqueCall = new Set(callees.map((c) => c.name));
    lines.push(`  [calls] ${uniqueCall.size} distinct callees`);
    const sorted = [...uniqueCall].slice(0, 15);
    for (const name of sorted) {
      const first = callees.find((c) => c.name === name)!;
      const path = relPath(first.file, root);
      lines.push(`    ${path}:${first.line}  -> ${name}`);
    }
    if (sorted.length < uniqueCall.size) {
      lines.push(`    ... and ${uniqueCall.size - 15} more callees`);
    }
  }

  return lines.join("\n");
}

async function runImpact(args: string[], cwd: string): Promise<string> {
  const proc = spawnSync(detectPython(), ["impact.py", ...args], { cwd, encoding: "utf-8", timeout: 30000 });
  if (proc.error) throw proc.error;
  if (proc.status !== 0) {
    const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
    throw new Error(`impact failed: ${msg}`);
  }
  return proc.stdout || "";
}

export default (async () => {
  const z = tool.schema
  return {
    tool: {
      impact: tool({
        description: `Change Impact Analyzer. Find definitions, references, tests, and callers for any symbol in the codebase.

Usage:
  impact def <symbol>          Find definition of symbol
  impact refs <symbol>         Find all references  
  impact tests <symbol>        Find test files using symbol
  impact graph <symbol>        Show callers + callees
  impact <symbol>              Show everything (def + refs + tests)
  impact <file>:<line>         Infer symbol at file:line

Examples:
  impact atlas_valloc          Find all uses of atlas_valloc
  impact atlas_load            Find definition + references
  impact atlas_infer.py:152    Infer symbol at line 152
  impact AtlasModel --py       Limit to Python files
  impact generate --cpp        Limit to C++ files`,
        args: {
          command: z.string().describe("The impact command and symbol to analyze (e.g. 'atlas_load', 'def forward', 'tests AtlasModel', 'graph atlas_valloc')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const args = splitArgs(command.trim().replace(/^impact(?:\.py)?\s+/, ""));
            const symbol = args.find((a: string) => !a.startsWith("-")) || args[0] || "";

            if (!args.includes("--json")) {
              args.push("--json");
            }

            const stdout = await runImpact(args, cwd);
            let data: ImpactResult;
            try {
              data = JSON.parse(stdout);
            } catch {
              return stdout;
            }

            return formatOutput(symbol, data);
          } catch (err: any) {
            return `impact error: ${err.message}`;
          }
        },
      }),
    },
  };
}) satisfies Plugin;
