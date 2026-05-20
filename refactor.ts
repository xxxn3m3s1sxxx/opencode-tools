import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs } from "./utils.ts"

export default (async () => {
  const z = tool.schema
  return {
    tool: {
      refactor: tool({
        description: `AST-based symbol renaming (safer than word-boundary).

Usage:
  refactor <old_name> <new_name>              Rename in all Python files
  refactor <old_name> <new_name> --dry-run    Preview only, no changes
  refactor <old_name> <new_name> --file <f>   Only in specific file
  refactor <old_name> <new_name> --json       Machine-readable output

Uses Python AST to find exact symbol references, not substring matches.
Safer than rename: no false positives on partial matches.

Examples:
  refactor foo bar                       Rename foo -> bar everywhere
  refactor myFunc myFunc2 --dry-run      Preview before renaming
  refactor old_name new_name --file src/main.py`,
        args: {
          command: z.string().describe("The refactor command (e.g. 'foo bar', 'foo bar --dry-run', 'foo bar --file src/main.py')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^refactor\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), ["refactor.py", ...args], { cwd, encoding: "utf-8", timeout: 60000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`refactor failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `refactor error: ${err.message}`;
          }
        },
      }),
    },
  };
}) satisfies Plugin;
