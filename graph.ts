import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"

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

export default (async () => {
  const z = tool.schema
  return {
    tool: {
      graph: tool({
        description: `File-level dependency analyzer. Show imports, dependents, and cycles.

Usage:
  graph <file>                  Show imports + dependents of a file
  graph <file> --in             Show what imports this file
  graph <file> --out            Show what this file imports
  graph <file> --tree           Full dependency tree
  graph --circular              Find circular dependencies
  graph --stats                 Project-wide dependency stats

Examples:
  graph src/main.py             Deps of main.py
  graph src/utils.py --tree     Full dependency tree
  graph --circular              Find cycles`,
        args: {
          command: z.string().describe("The graph command and args (e.g. 'src/main.py', 'src/utils.py --tree', '--circular')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^graph\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), ["graph.py", ...args], { cwd, encoding: "utf-8", timeout: 30000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`graph failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `graph error: ${err.message}`;
          }
        },
      }),
    },
  };
}) satisfies Plugin;
