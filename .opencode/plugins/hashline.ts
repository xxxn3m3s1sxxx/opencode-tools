import type { Plugin } from "@opencode-ai/plugin"
import { tool } from "@opencode-ai/plugin"
import { tmpdir } from "os"
import { randomUUID } from "crypto"
import { readFileSync, writeFileSync, unlinkSync, existsSync } from "fs"
import { resolve, isAbsolute, dirname, join } from "path"
import { fileURLToPath } from "url"
import { detectPython } from "./utils.ts"

let pluginDir = ""
try {
  pluginDir = dirname(fileURLToPath(import.meta.url))
} catch { /* import.meta not available */ }

const z = tool.schema
const CMD_TIMEOUT = 30_000

const VERSION = "0.3.0"
const stats = { edit_calls: 0, direct_ok: 0, hashline_ok: 0, hashline_fail: 0 }

function strip(e: any): string {
  return e.stderr?.toString().trim() || e.stdout?.toString().trim() || e.message || String(e)
}

const HashlinePlugin: Plugin = async ({ $, worktree }) => {
  const python = detectPython()
  const hlPy = [...(pluginDir ? [resolve(pluginDir, "hashline.py")] : []), `${worktree}/hashline.py`]
    .find(existsSync)

  let ok = false
  try { ok = hlPy && (await $`${python} ${hlPy}`.quiet().nothrow()).exitCode === 1 } catch (e) { console.warn("[hashline] validation error:", e) }
  if (!ok) { console.warn("[hashline] hashline.py not found — disabled"); return {} }

  function tmp(): string { return join(tmpdir(), `hl-${randomUUID().slice(0,8)}.tmp`) }
  function absPath(p: string, w: string): string {
    return isAbsolute(p) ? p : resolve(w, p)
  }
  async function pyRun<T>(prom: Promise<T>, label: string): Promise<T> {
    return Promise.race([
      prom,
      new Promise<never>((_, rej) =>
        setTimeout(() => rej(new Error(`timeout after ${CMD_TIMEOUT/1000}s: ${label}`)), CMD_TIMEOUT)
      ),
    ])
  }

  return {
    tool: {
    edit: tool({
      description:
        "Edit a file by finding and replacing text. " +
        "Tries exact match first; on failure, auto-retries with hash-anchored matching.",
      args: {
        filePath: z.string().describe("The path to the file (absolute or worktree-relative)"),
        oldString: z.string().describe("The text to replace"),
        newString: z.string().describe("The text to replace it with"),
      },
      async execute(a, ctx) {
        stats.edit_calls++
        const p = absPath(a.filePath, ctx.worktree)

        // Try direct edit first
        try {
          const content = readFileSync(p, "utf-8").replace(/^\ufeff/, "")
          const idx = content.indexOf(a.oldString)
          if (idx !== -1) {
            const updated = content.slice(0, idx) + a.newString + content.slice(idx + a.oldString.length)
            writeFileSync(p, updated, "utf-8")
            stats.direct_ok++
            return `Applied edit to ${a.filePath}`
          }
          throw new Error("oldString not found in file")
        } catch (e0: any) {
          // Fallback: hashline replace
          const of = tmp(), nf = tmp()
          writeFileSync(of, a.oldString, "utf-8"); writeFileSync(nf, a.newString, "utf-8")
          try {
            const r = await pyRun(
              $`${python} ${hlPy} replace ${p} --file-old ${of} --file-new ${nf}`.quiet(),
              `edit fallback ${a.filePath}`
            )
            stats.hashline_ok++
            return `edit() failed → hashline fallback OK: ${r.text().trim() || `Updated ${a.filePath}`}`
          } catch (e1: any) {
            stats.hashline_fail++
            throw new Error(
              `edit() failed (${strip(e0)}). ` +
              `hashline fallback also failed (${strip(e1)}). ` +
              `Try a smaller matching segment, or check file for whitespace differences.`
            )
          } finally {
            try { unlinkSync(of) } catch { /* cleanup */ }; try { unlinkSync(nf) } catch { /* cleanup */ }
          }
        }
      },
    }),
    hashline_edit: tool({
      description:
        "Edit a file using hash-anchored content hashes. " +
        "Handles trailing whitespace, indent mismatches, and extra blank lines " +
        "that edit() rejects. Use hashline_stats to see how often edit() needs fallback.",
      args: {
        path: z.string().describe("File path (absolute or worktree-relative)"),
        old: z.string().describe("Old text to find"),
        "new": z.string().describe("New replacement text"),
      },
      async execute(a, ctx) {
        const p = absPath(a.path, ctx.worktree)
        const of = tmp(), nf = tmp()
        writeFileSync(of, a.old, "utf-8"); writeFileSync(nf, a["new"], "utf-8")
        try {
          const r = await pyRun(
            $`${python} ${hlPy} replace ${p} --file-old ${of} --file-new ${nf}`.quiet(),
            `hashline_edit ${a.path}`
          )
          return r.text().trim() || `Updated ${a.path}`
        } catch (e: any) {
          throw new Error(`hashline_edit: ${strip(e)}`)
        } finally {
          try { unlinkSync(of) } catch { /* cleanup */ }; try { unlinkSync(nf) } catch { /* cleanup */ }
        }
      },
    }),
    hashline_patch: tool({
      description:
        "Apply a raw hashline diff to a file. " +
        "Format: @@ path\\n+ ANCHOR~payload / = A..B~repl / - A..B",
      args: {
        path: z.string().describe("File to edit"),
        diff: z.string().describe("Hashline diff text with @@ headers"),
      },
      async execute(a, ctx) {
        const p = absPath(a.path, ctx.worktree)
        const df = tmp()
        writeFileSync(df, a.diff, "utf-8")
        try {
          const r = await pyRun(
            $`${python} ${hlPy} edit ${p} ${df}`.quiet(),
            `hashline_patch ${a.path}`
          )
          return r.text().trim() || `Patched ${a.path}`
        } catch (e: any) {
          throw new Error(`hashline_patch: ${strip(e)}`)
        } finally {
          try { unlinkSync(df) } catch { /* cleanup */ }
        }
      },
    }),
    hashline_stats: tool({
      description:
        "Show how often edit() has needed hashline fallback. " +
        "High fallback rate means your prompt's oldText frequently doesn't match exact file content.",
      args: {},
      async execute() {
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
    }),
    },
  }
}

export default HashlinePlugin
