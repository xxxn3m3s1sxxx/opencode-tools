import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"
import { registerTool, commandSchema } from "./utils.ts"

export default {
  id: "todo",
  async setup(ctx: any) {
    await registerTool(ctx, {
        name: "todo",
        description: `Scan for TODO, FIXME, HACK, XXX markers across the codebase.

Usage:
  todo                              Scan and show all markers grouped by file
  todo --count                      Just show counts per tag type
  todo --json                       JSON output
  todo --file <path>                Scan a specific file only
  todo --root <dir>                 Scan a specific directory

Tag types: TODO, FIXME, HACK, XXX, BUG, OPTIMIZE, NOTE, REVIEW, WORKAROUND`,
        input: commandSchema("The todo command and args (e.g. '--count', '--json', '')"),
        async run({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^todo\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("todo.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 30000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`todo failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `todo error: ${err.message}`;
          }
        },
    })
  },
}

