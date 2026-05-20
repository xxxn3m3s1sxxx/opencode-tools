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
      rename: tool({
        description: `Word-boundary symbol rename across project files.

Usage:
  rename <old_name> <new_name>              Rename symbol in all source files
  rename <old_name> <new_name> --dry-run    Preview only, no changes
  rename <old_name> <new_name> --lang py    Only Python files

Searches all source files (.py, .ts, .js, .cpp, .c, .rs, .go, .java)
within the project tree, skipping .git, node_modules, __pycache__, etc.
Uses \\b word-boundary matching for safe renames.

Examples:
  rename foo bar                       Rename foo -> bar everywhere
  rename myFunc myFunc2 --dry-run      Preview before renaming
  rename old_name new_name --lang py   Only Python files`,
        args: {
          command: z.string().describe("The rename command and args (e.g. 'foo bar', 'foo bar --dry-run', 'foo bar --lang py')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^rename\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), ["rename.py", ...args], { cwd, encoding: "utf-8", timeout: 60000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`rename failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `rename error: ${err.message}`;
          }
        },
      }),
    },
  };
}) satisfies Plugin;
