import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      snapshot: tool({
        description: `Capture workspace context for MemPalace auto-save.

Takes a snapshot of the current workspace state: git status, file changes,
recent commits, tool versions, and directory structure.

Usage:
  snapshot                          Save snapshot to .opencode/snapshots/
  snapshot --show                   Print snapshot to stdout only
  snapshot --mine                   Save + mine into MemPalace
  snapshot --json                   JSON output`,
        args: {
          command: z.string().describe("The snapshot command and args (e.g. '--show', '--json', '')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^snapshot\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("snapshot.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 30000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`snapshot failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `snapshot error: ${err.message}`;
          }
        },
      }),
    },
  };
}
