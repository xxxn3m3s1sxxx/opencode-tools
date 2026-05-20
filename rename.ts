import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs } from "./utils.ts"

export default (async () => {
  const z = tool.schema
  return {
    tool: {
      rename: tool({
        description: `Word-boundary symbol rename across project files.

Usage:
  rename <old_name> <new_name>              Rename symbol in all source files
  rename <old_name> <new_name> --dry-run    Preview only, no changes
  rename <old_name> <new_name> --lang py    Only Python files

Searches all source files (.py, .ts, .js, .cpp, .c, .rs, .go, .java)
within the project tree, skipping .git, node_modules, __pycache__, etc.
Uses \\b word-boundary matching for safe renames.

Examples:
  rename foo bar                       Rename foo -> bar everywhere
  rename myFunc myFunc2 --dry-run      Preview before renaming
  rename old_name new_name --lang py   Only Python files`,
        args: {
          command: z.string().describe("The rename command and args (e.g. 'foo bar', 'foo bar --dry-run', 'foo bar --lang py')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^rename\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), ["rename.py", ...args], { cwd, encoding: "utf-8", timeout: 60000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`rename failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `rename error: ${err.message}`;
          }
        },
      }),
    },
  };
}) satisfies Plugin;
