import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"
import { registerTool, commandSchema } from "./utils.ts"

export default {
  id: "health",
  async setup(ctx: any) {
    await registerTool(ctx, {
        name: "health",
        description: `Project health summary. Analyze test status, lint quality, and code metrics.

Usage:
  health                          Show full health summary
  health --json                   JSON output
  health --check                  Exit 0 only if all checks pass
  health --quick                  Skip running tests (faster)

Metrics:
  - pytest:   pass rate, total/fail count
  - mypy:     error count
  - ruff:     violation count
  - lines:    total lines of code per language
  - files:    source file count per language`,
        input: commandSchema("The health command and args (e.g. '--quick', '--check --quick', '--json')"),
        async run({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^health\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("health.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 120000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`health failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `health error: ${err.message}`;
          }
        },
    })
  },
}

