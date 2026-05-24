import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      fmt: tool({
        description: `Format runner. Run ruff format and/or prettier on the project.

Usage:
  fmt                               Format all supported files
  fmt --check                       Check mode (read-only, exit 1 if unformatted)
  fmt --ruff                        Ruff format only (default)
  fmt --prettier                    Prettier only
  fmt --all                         Both ruff and prettier
  fmt --json                        JSON output`,
        args: {
          command: z.string().describe("The fmt command and args (e.g. '--check', '--ruff --json')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^fmt\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("fmt.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 120000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`fmt failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `fmt error: ${err.message}`;
          }
        },
      }),
    },
  };
}
