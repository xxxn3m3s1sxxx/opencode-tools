import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
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
            const proc = spawnSync(detectPython(), [findToolPy("changelog.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 30000 });
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
}
