import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      tags: tool({
        description: `ctags-style symbol indexer. Build a searchable index of all definitions.

Usage:
  tags                              Build and show tag index for current project
  tags <symbol>                     Look up a specific symbol
  tags --build                      Force rebuild index
  tags --json                       JSON output
  tags --root <dir>                 Index a specific directory
  tags --stats                      Show index statistics`,
        args: {
          command: z.string().describe("The tags command and args (e.g. '--stats', 'ImpactAnalyzer', '--json')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^tags\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("tags.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 30000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`tags failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `tags error: ${err.message}`;
          }
        },
      }),
    },
  };
}
