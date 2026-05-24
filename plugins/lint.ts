import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      lint: tool({
        description: `Run project lint/typecheck and parse output into structured results.

Usage:
  lint                            Run auto-detected lint command
  lint <tool>                     Run specific tool (ruff, eslint, tsc, mypy, pylint)
  lint <tool> <file>              Run on specific file
  lint --json                     Structured JSON output

Examples:
  lint                            Auto-detect and run
  lint ruff                       Run ruff on current project
  lint tsc                        Run TypeScript type check
  lint --json                     Machine-readable output`,
        args: {
          command: z.string().describe("The lint command and args (e.g. '', 'ruff', 'tsc', 'ruff src/main.py', '--json')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^lint\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("lint.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 120000 });
            if (proc.error) throw proc.error;
            const output = (proc.stdout || "").trim();
            const err = (proc.stderr || "").trim();
            if (proc.status !== 0) {
              return err || output || `lint: exit ${proc.status}`;
            }
            return output || err;
          } catch (err: any) {
            return `lint error: ${err.message}`;
          }
        },
      }),
    },
  };
}
