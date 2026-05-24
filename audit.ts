import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { spawnSync } from "child_process"
import { detectPython, splitArgs, findToolPy } from "./utils.ts"

export default async (ctx: any) => {
  const z = tool.schema
  return {
    tool: {
      audit: tool({
        description: `Secret scanner. Find API keys, passwords, tokens, private keys.

Usage:
  audit                           Scan current directory
  audit --root <dir>              Scan specific directory
  audit --json                    JSON output
  audit --quiet                   Only show secrets, no header/footer
  audit --allowlist <file>        File with allowed patterns`,
        args: {
          command: z.string().describe("The audit command and args (e.g. '--json', '--quiet')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^audit\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("audit.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 120000 });
            if (proc.error) throw proc.error;
            if (proc.status !== 0) {
              const msg = (proc.stderr?.trim() || proc.stdout?.trim() || `exit ${proc.status}`);
              throw new Error(`audit failed: ${msg}`);
            }
            return proc.stdout || "";
          } catch (err: any) {
            return `audit error: ${err.message}`;
          }
        },
      }),
    },
  };
}
