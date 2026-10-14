import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"
import { registerTool, commandSchema } from "./utils.ts"

export default {
  id: "ghost",
  async setup(ctx: any) {
    await registerTool(ctx, {
        name: "ghost",
        description: `Dead code finder. Detect unused functions, classes, and imports.

Usage:
  ghost                           Scan current directory
  ghost --lang py                 Python only
  ghost --lang ts                 TypeScript/JS only
  ghost --json                    JSON output
  ghost --min-uses <N>            Minimum uses (default: 1)`,
        input: commandSchema("The ghost command and args (e.g. '--lang py --json')"),
        async run({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^ghost\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("ghost.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 60000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`ghost failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `ghost error: ${err.message}`;
          }
        },
    })
  },
}

