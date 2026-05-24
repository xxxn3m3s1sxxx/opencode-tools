import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      check: tool({
        description: `Pre-commit gate. Run lint → mypy → tests, exit 0 only if all pass.

Usage:
  check                             Run all checks (lint + mypy + tests)
  check --lint                      Lint only (ruff)
  check --mypy                      Mypy only
  check --test                      Tests only (pytest)
  check --quick                     Skip tests (lint + mypy only)
  check --json                      JSON output`,
        args: {
          command: z.string().describe("The check command and args (e.g. '--quick', '--lint', '--json')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^check\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("check.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 180000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`check failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `check error: ${err.message}`;
          }
        },
      }),
    },
  };
}
