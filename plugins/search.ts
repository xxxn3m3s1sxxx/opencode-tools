import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"
import { registerTool, commandSchema } from "./utils.ts"

export default {
  id: "search",
  async setup(ctx: any) {
    await registerTool(ctx, {
        name: "search",
        description: `Rich grep wrapper with Regex, file filters, and context lines.

Usage:
  search <pattern>                    Search in current directory
  search <pattern> <path>            Search in specific path
  search <pattern> --include *.py    Only Python files
  search <pattern> --context 3       Show 3 lines of context
  search <pattern> --json            JSON output (for plugin)

Examples:
  search "def main"                  Find all Python main function defs
  search "from .* import" --include *.py
  search "TODO|FIXME" --context 2`,
        input: commandSchema("The search command and args (e.g. 'def main', '\"from .* import\" --include *.py', 'TODO --context 2')"),
        async run({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^search\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("search.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 30000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`search failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `search error: ${err.message}`;
          }
        },
    })
  },
}

