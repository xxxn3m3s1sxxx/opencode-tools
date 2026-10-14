import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"
import { registerTool, commandSchema } from "./utils.ts"

export default {
  id: "tags",
  async setup(ctx: any) {
    await registerTool(ctx, {
        name: "tags",
        description: `ctags-style symbol indexer. Build a searchable index of all definitions.

Usage:
  tags                              Build and show tag index for current project
  tags <symbol>                     Look up a specific symbol
  tags --build                      Force rebuild index
  tags --json                       JSON output
  tags --root <dir>                 Index a specific directory
  tags --stats                      Show index statistics
  tags --max-files <N>              Limit files to index (default: 10000)`,
        input: commandSchema("The tags command and args (e.g. '--stats', 'ImpactAnalyzer', '--json')"),
        async run({ command }: { command: string }, ctx: any) {
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
    })
  },
}

