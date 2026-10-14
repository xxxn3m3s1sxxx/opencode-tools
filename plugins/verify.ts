import { spawnSync } from "child_process";
import { detectPython, splitArgs, findToolPy } from "./utils.ts";
import { registerTool, commandSchema } from "./utils.ts"

export default {
  id: "verify",
  async setup(ctx: any) {
    await registerTool(ctx, {
        name: "verify",
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
        input: commandSchema("The verify command arguments (e.g. 'atlas_api.cpp:20 atlas_valloc', 'impact.py --summary', 'hashline.py --not bug')"),
        async run({ command }: { command: string }, ctx: any) {
          try {
            const cwd = ctx?.cwd || process.cwd();
            const raw = command.trim().replace(/^verify(?:\.py)?\s+/, "");
            const args = splitArgs(raw);
            const proc = spawnSync(detectPython(), [findToolPy("verify.py", cwd), ...args], { cwd, encoding: "utf-8", timeout: 30000 });
            if (proc.error) throw proc.error;
            const output = (proc.stdout || "").trim();
            const err = (proc.stderr || "").trim();

            if (proc.status !== 0) return err || output || `verify: exit ${proc.status}`;
            return output || err;
          } catch (err: any) {
            return `verify error: ${err.message}`;
          }
        },
    })
  },
}

