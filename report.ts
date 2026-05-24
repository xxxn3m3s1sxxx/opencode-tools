import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      report: tool({
        description: `Project health report. Combines check + audit + fmt + churn + health.

Usage:
  report                          Full report (markdown)
  report --quick                  Skip slow checks
  report --json                   JSON output
  report --output <file>          Write to file`,
        args: {
          command: z.string().describe("The report command and args (e.g. '--quick', '--json')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^report\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("report.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 300000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`report failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `report error: ${err.message}`;
          }
        },
      }),
    },
  };
}
