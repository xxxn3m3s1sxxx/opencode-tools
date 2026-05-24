import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      todo: tool({
        description: `Scan for TODO, FIXME, HACK, XXX markers across the codebase.

Usage:
  todo                              Scan and show all markers grouped by file
  todo --count                      Just show counts per tag type
  todo --json                       JSON output
  todo --file <path>                Scan a specific file only
  todo --root <dir>                 Scan a specific directory

Tag types: TODO, FIXME, HACK, XXX, BUG, OPTIMIZE, NOTE, REVIEW, WORKAROUND`,
        args: {
          command: z.string().describe("The todo command and args (e.g. '--count', '--json', '')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
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
      }),
    },
  };
}
