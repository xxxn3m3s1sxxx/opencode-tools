import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"
import { registerTool, commandSchema } from "./utils.ts"

export default {
  id: "fmt",
  async setup(ctx: any) {
    await registerTool(ctx, {
        name: "fmt",
        description: `Format runner. Run ruff format and/or prettier on the project.

Usage:
  fmt                               Format all supported files
  fmt --check                       Check mode (read-only, exit 1 if unformatted)
  fmt --ruff                        Ruff format only (default)
  fmt --prettier                    Prettier only
  fmt --all                         Both ruff and prettier
  fmt --json                        JSON output`,
        input: commandSchema("The fmt command and args (e.g. '--check', '--ruff --json')"),
        async run({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^fmt\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("fmt.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 120000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`fmt failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `fmt error: ${err.message}`;
          }
        },
    })
  },
}

