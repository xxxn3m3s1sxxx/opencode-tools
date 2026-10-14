import { spawnSync } from "child_process"
import { tmpdir } from "os"
import { randomUUID } from "crypto"
import { writeFileSync, unlinkSync, existsSync } from "fs"
import { resolve, isAbsolute, dirname, join } from "path"
import { fileURLToPath } from "url"
import { detectPython } from "./utils.ts"

// v2-Port (OpenCode >= 2.0, 2026-10-14):
//  - Ladevertrag `export default { id, setup(ctx) }`
//  - `$` (Bun-Shell) existiert in v2 nicht mehr -> spawnSync
//  - Tool `edit` (Override des Built-ins) wird BEWUSST nicht registriert:
//    das Built-in-edit bleibt unangetastet; hashline_edit/-_patch/-_stats
//    liefern die Hashline-Funktion. (Abweichung vom v1-Umfang, dokumentiert.)

let pluginDir = ""
try {
  pluginDir = dirname(fileURLToPath(import.meta.url))
} catch { /* import.meta not available */ }

const CMD_TIMEOUT = 30_000
const VERSION = "0.5.3"
const stats = { edit_calls: 0, direct_ok: 0, hashline_ok: 0, hashline_fail: 0 }

function strip(e: any): string {
  return e?.stderr?.toString().trim() || e?.stdout?.toString().trim() || e?.message || String(e)
}

function runPy(python: string, hlPy: string, args: string[]): string {
  const proc = spawnSync(python, [hlPy, ...args], { encoding: "utf-8", timeout: CMD_TIMEOUT })
  if (proc.error) throw proc.error
  if (proc.status !== 0) throw new Error(String(proc.stderr || proc.stdout || `exit ${proc.status}`).trim())
  return String(proc.stdout || "").trim()
}

function tmp(): string { return join(tmpdir(), `hl-${randomUUID().slice(0, 8)}.tmp`) }

export default {
  id: "hashline",
  async setup(ctx: any) {
    const python = detectPython()
    const baseDir = ctx?.location?.directory || process.cwd()
    const hlPy = [
      ...(pluginDir ? [resolve(pluginDir, "hashline.py")] : []),
      resolve(baseDir, "hashline.py"),
    ].find(existsSync)

    let ok = false
    if (hlPy) {
      try {
        const proc = spawnSync(python, [hlPy], { encoding: "utf-8", timeout: CMD_TIMEOUT })
        ok = !proc.error && proc.status === 1
      } catch { ok = false }
    }
    if (!ok) { console.warn("[hashline] hashline.py not found - disabled"); return }

    const transform = ctx?.tool?.transform
    if (typeof transform !== "function") { console.warn("[hashline] ctx.tool.transform missing - disabled"); return }

    const absPath = (p: string, c: string) => (isAbsolute(p) ? p : resolve(c || baseDir, p))

    const register = (spec: {
      name: string
      description: string
      input: any
      execute: (a: any, cwd: string) => string | Promise<string>
    }) => transform((editor: any) => {
      editor.add({
        name: spec.name,
        description: spec.description,
        input: spec.input,
        async execute(input: any, execCtx: any) {
          const cwd = execCtx?.worktree || execCtx?.directory || execCtx?.cwd || baseDir
          const out = await spec.execute(input || {}, cwd)
          return { content: typeof out === "string" ? out : String(out) }
        },
      })
    })

    await register({
      name: "hashline_edit",
      description:
        "Edit a file using hash-anchored content hashes. " +
        "Handles trailing whitespace, indent mismatches, and extra blank lines " +
        "that edit() rejects. Use hashline_stats to see how often edit() needs fallback.",
      input: {
        type: "object",
        properties: {
          path: { type: "string", description: "File path (absolute or worktree-relative)" },
          old: { type: "string", description: "Old text to find" },
          "new": { type: "string", description: "New replacement text" },
        },
        required: ["path", "old", "new"],
        additionalProperties: false,
      },
      execute(a, cwd) {
        const p = absPath(a.path, cwd)
        const of = tmp(), nf = tmp()
        writeFileSync(of, a.old, "utf-8"); writeFileSync(nf, a["new"], "utf-8")
        try {
          const out = runPy(python, hlPy!, ["replace", p, "--file-old", of, "--file-new", nf])
          stats.hashline_ok++
          return out || `Updated ${a.path}`
        } catch (e: any) {
          stats.hashline_fail++
          throw new Error(`hashline_edit: ${strip(e)}`)
        } finally {
          try { unlinkSync(of) } catch { /* cleanup */ }; try { unlinkSync(nf) } catch { /* cleanup */ }
        }
      },
    })

    await register({
      name: "hashline_patch",
      description:
        "Apply a raw hashline diff to a file. " +
        "Format: @@ path\n+ ANCHOR~payload / = A..B~repl / - A..B",
      input: {
        type: "object",
        properties: {
          path: { type: "string", description: "File to edit" },
          diff: { type: "string", description: "Hashline diff text with @@ headers" },
        },
        required: ["path", "diff"],
        additionalProperties: false,
      },
      execute(a, cwd) {
        const p = absPath(a.path, cwd)
        const df = tmp()
        writeFileSync(df, a.diff, "utf-8")
        try {
          return runPy(python, hlPy!, ["edit", p, df]) || `Patched ${a.path}`
        } catch (e: any) {
          throw new Error(`hashline_patch: ${strip(e)}`)
        } finally {
          try { unlinkSync(df) } catch { /* cleanup */ }
        }
      },
    })

    await register({
      name: "hashline_stats",
      description:
        "Show how often edit() has needed hashline fallback. " +
        "High fallback rate means your prompt's oldText frequently doesn't match exact file content.",
      input: { type: "object", properties: {}, additionalProperties: false },
      execute() {
        const rate = stats.edit_calls > 0
          ? ((stats.hashline_ok / stats.edit_calls) * 100).toFixed(1)
          : "0.0"
        const saved = stats.hashline_ok * 50
        return [
          `hashline plugin active (v${VERSION})`,
          `edit() calls:        ${stats.edit_calls}`,
          `  direct OK:         ${stats.direct_ok}`,
          `  hashline salvaged:  ${stats.hashline_ok}`,
          `  both failed:       ${stats.hashline_fail}`,
          `intervention rate:   ${rate}%`,
          `retries avoided:     ~${saved} tok saved (est. 50 tok/retry)`,
          stats.edit_calls === 0 ? "  (no edit() calls yet this session)" : "",
        ].filter(Boolean).join("\n")
      },
    })
  },
}
