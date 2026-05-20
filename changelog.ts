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
      changelog: tool({
        description: `Formatted git log with category grouping.

Usage:
  changelog                         Recent commits (last 20)
  changelog -n 50                   Last 50 commits
  changelog v1.0..HEAD              Commits between tags
  changelog --file <path>           Commits touching a file
  changelog --since 2024-01-01      Commits since date

Groups commits by conventional-commit prefix (feat/fix/docs/refactor/etc).

Examples:
  changelog -n 10                   Last 10 commits
  changelog --since 2025-01-01      This year's commits
  changelog --file src/main.ts      File history`,
        args: {
          command: z.string().describe("The changelog command and args (e.g. '-n 10', '--since 2025-01-01', 'v1.0..HEAD')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^changelog\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), ["changelog.py", ...args], { cwd, encoding: "utf-8", timeout: 30000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`changelog failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `changelog error: ${err.message}`;
          }
        },
      }),
    },
  };
}) satisfies Plugin;
