import { Tool } from "@opencode-ai/sdk";

interface ImpactResult {
  symbol: string;
  project: string;
  definitions: Array<{ type: string; name: string; file: string; line: number; context?: string }>;
  references: Array<{ type: string; file: string; line: number; context?: string }>;
  tests: Array<{ type: string; file: string; line: number; context?: string }>;
  callees: Array<{ name: string; file: string; line: number }>;
}

function fmtCount(n: number, label: string): string {
  return n === 0 ? `0 ${label}` : `${n} ${label}${n !== 1 ? "s" : ""}`;
}

function relPath(file: string, root: string): string {
  const rel = file.replace(root.replace(/\\/g, "/"), "").replace(/^[/\\]/, "");
  return rel || file;
}

function formatOutput(symbol: string, data: ImpactResult): string {
  const lines: string[] = [];
  const root = data.project;

  lines.push(`impact: \`${symbol}\``);
  lines.push("");

  // Definitions
  const defs = data.definitions || [];
  lines.push(`  [def] ${fmtCount(defs.length, "occurrence")}`);
  if (defs.length === 0) {
    lines.push("    (not found)");
  }
  for (const d of defs.slice(0, 5)) {
    const path = relPath(d.file, root);
    const ctx = d.context ? `  -- ${d.context}` : "";
    lines.push(`    ${path}:${d.line}  (${d.type})${ctx}`);
  }
  if (defs.length > 5) {
    lines.push(`    ... and ${defs.length - 5} more`);
  }

  // References (non-test)
  const isTest = (f: string) => /test_/.test(f.replace(/\\/g, "/"));
  const refs = (data.references || []).filter((r) => !isTest(r.file));
  lines.push("");
  lines.push(`  [ref] ${fmtCount(refs.length, "occurrence")}`);
  for (const r of refs.slice(0, 10)) {
    const path = relPath(r.file, root);
    const ctx = r.context ? `  -- ${r.context}` : "";
    lines.push(`    ${path}:${r.line}${ctx}`);
  }
  if (refs.length > 10) {
    lines.push(`    ... and ${refs.length - 10} more`);
  }

  // Tests
  const tests = data.tests || [];
  lines.push("");
  lines.push(`  [test] ${fmtCount(tests.length, "occurrence")}`);
  for (const t of tests.slice(0, 10)) {
    const path = relPath(t.file, root);
    const ctx = t.context ? `  -- ${t.context}` : "";
    lines.push(`    ${path}:${t.line}${ctx}`);
  }
  if (tests.length > 10) {
    lines.push(`    ... and ${tests.length - 10} more`);
  }

  // Call graph (limited)
  const callees = data.callees || [];
  if (callees.length > 0) {
    lines.push("");
    const uniqueCall = new Set(callees.map((c) => c.name));
    lines.push(`  [calls] ${uniqueCall.size} distinct callees`);
    const sorted = [...uniqueCall].slice(0, 15);
    for (const name of sorted) {
      const first = callees.find((c) => c.name === name)!;
      const path = relPath(first.file, root);
      lines.push(`    ${path}:${first.line}  -> ${name}`);
    }
    if (sorted.length < uniqueCall.size) {
      lines.push(`    ... and ${uniqueCall.size - 15} more callees`);
    }
  }

  return lines.join("\n");
}

async function runImpact(args: string[], cwd: string): Promise<string> {
  const cmd = `python impact.py ${args.join(" ")} --json`;
  const proc = Bun.spawnSync(cmd.split(" "), { cwd });
  if (proc.exitCode !== 0) {
    const stderr = proc.stderr.toString().trim();
    throw new Error(`impact failed: ${stderr || proc.stdout.toString().trim()}`);
  }
  return proc.stdout.toString();
}

export const tools: Tool[] = [
  {
    name: "impact",
    description: `Change Impact Analyzer. Find definitions, references, tests, and callers for any symbol in the codebase.

Usage:
  impact def <symbol>          Find definition of symbol
  impact refs <symbol>         Find all references  
  impact tests <symbol>        Find test files using symbol
  impact graph <symbol>        Show callers + callees
  impact <symbol>              Show everything (def + refs + tests)
  impact <file>:<line>         Infer symbol at file:line

Examples:
  impact atlas_valloc          Find all uses of atlas_valloc
  impact atlas_load            Find definition + references
  impact atlas_infer.py:152    Infer symbol at line 152
  impact AtlasModel --py       Limit to Python files
  impact generate --cpp        Limit to C++ files`,

    parameters: {
      type: "object",
      properties: {
        command: {
          type: "string",
          description: "The impact command and symbol to analyze (e.g. 'atlas_load', 'def forward', 'tests AtlasModel', 'graph atlas_valloc')",
        },
      },
      required: ["command"],
    },

    execute: async ({ command }: { command: string }, context) => {
      try {
        const cwd = context?.cwd || process.cwd();
        const args = command.trim().split(/\s+/);
        const symbol = args[args.length - 1];

        // Add --json flag
        if (!args.includes("--json")) {
          args.push("--json");
        }

        const stdout = await runImpact(args, cwd);
        let data: ImpactResult;
        try {
          data = JSON.parse(stdout);
        } catch {
          // Not JSON — plain text output
          return { content: [{ type: "text", text: stdout }] };
        }

        const formatted = formatOutput(symbol, data);
        return { content: [{ type: "text", text: formatted }] };
      } catch (err: any) {
        return {
          content: [{ type: "text", text: `impact error: ${err.message}` }],
          isError: true,
        };
      }
    },
  },
];

export default { tools };
