import type { Plugin } from "@opencode-ai/plugin";
import { tool } from "@opencode-ai/plugin";
import { spawnSync } from "child_process";

let _python: string | null = null
function detectPython(): string {
  if (_python) return _python
  const candidates = process.platform === "win32"
    ? [["python"], ["py", "-3"], ["py"], ["python3"]]
    : [["python3"], ["python"], ["py", "-3"], ["py"]]
  for (const [cmd, ...args] of candidates) {
    try {
      const r = spawnSync(cmd, [...args, "-c", "import sys; print(sys.executable)"], { encoding: "utf-8", timeout: 3000 })
      if (r.status === 0 && !r.error) {
        const fp = (r.stdout || "").trim().split(/\r?\n/)[0].trim()
        if (fp) { _python = fp; return fp }
      }
    } catch { /* try next */ }
  }
  _python = "python"; return _python
}

function splitArgs(cmd: string): string[] {
  const args: string[] = []; const re = /[^\s"']+|"([^"]*)"|'([^']*)'/g; let m
  while ((m = re.exec(cmd)) !== null) args.push(m[1] || m[2] || m[0])
  return args
}

export default (async () => {
  const z = tool.schema
  return {
    tool: {
      verify: tool({
        description: `Post-edit verification tool. Confirms edits were applied correctly.

Usage:
  verify <file>                           Show file summary
  verify <file>:<line>                    Show context at line  
  verify <file> <text>                    Check if text exists in file
  verify <file>:<line> <text>             Check specific line content
  verify <file> --old <old> --new <new>   Confirm replace worked
  verify <file> --not <text>              Assert text is absent
  verify <file> --contains <text>         Assert text is present

Examples:
  verify atlas_api.cpp:20 "atlas_valloc"   Line 20 has atlas_valloc?
  verify impact.py --old "bug" --new "fix"  Replace verified?
  verify atlas_api.cpp                      File summary
  verify atlas_infer.py:612 --context 5     Context at line 612`,
        args: {
          command: z.string().describe("The verify command arguments (e.g. 'atlas_api.cpp:20 atlas_valloc', 'impact.py --summary', 'hashline.py --not bug')"),
        },
        async execute({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^verify(?:\.py)?\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), ["verify.py", ...args], { cwd, encoding: "utf-8", timeout: 30000 });
            if (proc.error) throw proc.error;
            const output = (proc.stdout || "").trim();
            const err = (proc.stderr || "").trim();

            if (proc.status !== 0) return err || output || `verify: exit ${proc.status}`;
            return output || err;
          } catch (err: any) {
            return `verify error: ${err.message}`;
          }
        },
      }),
    },
  };
}) satisfies Plugin;
