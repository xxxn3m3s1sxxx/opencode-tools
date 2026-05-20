import { Tool } from "@opencode-ai/sdk";

export const tools: Tool[] = [
  {
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

    parameters: {
      type: "object",
      properties: {
        command: {
          type: "string",
          description: "The verify command arguments (e.g. 'atlas_api.cpp:20 atlas_valloc', 'impact.py --summary', 'hashline.py --not bug')",
        },
      },
      required: ["command"],
    },

    execute: async ({ command }: { command: string }, context) => {
      try {
        const cwd = context?.cwd || process.cwd();
        const proc = Bun.spawnSync(["python", "verify.py", ...command.trim().split(/\s+/)], { cwd });
        const output = proc.stdout.toString().trim();
        const stderr = proc.stderr.toString().trim();

        if (proc.exitCode !== 0 && !stderr) {
          return { content: [{ type: "text", text: output || stderr || `verify: exit ${proc.exitCode}` }], isError: true };
        }

        return { content: [{ type: "text", text: output || stderr }] };
      } catch (err: any) {
        return { content: [{ type: "text", text: `verify error: ${err.message}` }], isError: true };
      }
    },
  },
];

export default { tools };
