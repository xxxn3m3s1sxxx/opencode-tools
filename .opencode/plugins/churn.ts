import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      churn: tool({
        description: `Git churn analysis. Find files with the most changes.

Usage:
  churn                           All files, sorted by commit count
  churn -n <N>                    Top N files (default: 20)
  churn --since <date>            Commits since date (e.g. '2026-01-01')
  churn --min-commits <N>         Minimum commits (default: 2)
  churn --json                    JSON output`,
        args: {
          command: z.string().describe("The churn command and args (e.g. '-n 10', '--since 2026-01-01')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^churn\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("churn.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 60000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`churn failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `churn error: ${err.message}`;
          }
        },
      }),
    },
  };
}
