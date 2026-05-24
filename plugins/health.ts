import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      health: tool({
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
        args: {
          command: z.string().describe("The health command and args (e.g. '--quick', '--check --quick', '--json')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
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
      }),
    },
  };
}
