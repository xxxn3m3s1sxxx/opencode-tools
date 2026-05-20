import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default (async () => {
  const z = tool.schema
  return {
    tool: {
      graph: tool({
        description: `File-level dependency analyzer. Show imports, dependents, and cycles.

Usage:
  graph <file>                  Show imports + dependents of a file
  graph <file> --in             Show what imports this file
  graph <file> --out            Show what this file imports
  graph <file> --tree           Full dependency tree
  graph --circular              Find circular dependencies
  graph --stats                 Project-wide dependency stats

Examples:
  graph src/main.py             Deps of main.py
  graph src/utils.py --tree     Full dependency tree
  graph --circular              Find cycles`,
        args: {
          command: z.string().describe("The graph command and args (e.g. 'src/main.py', 'src/utils.py --tree', '--circular')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^graph\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("graph.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 30000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`graph failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `graph error: ${err.message}`;
          }
        },
      }),
    },
  };
}) satisfies Plugin;
