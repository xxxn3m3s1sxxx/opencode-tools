import { spawnSync } from "child_process"
import { existsSync } from "fs"
import { resolve, dirname } from "path"
import { fileURLToPath } from "url"

let _pluginDir = ""
try {
  _pluginDir = dirname(fileURLToPath(import.meta.url))
} catch {
  try {
    _pluginDir = typeof __dirname !== "undefined" ? __dirname : ""
  } catch { /* no __dirname */ }
}
// Stack-trace fallback for OpenCode's custom loader
function _derivePluginDir(): string {
  try {
    const stack = new Error().stack || ""
    const m = stack.match(/\((.+?)[\/\\]utils\.ts/)
    return m ? dirname(m[1]) : ""
  } catch { return "" }
}
if (!_pluginDir) _pluginDir = _derivePluginDir()

export function findToolPy(name: string, cwd: string): string {
  // Guard gegen Scan-/Fehl-Aufrufe mit Kontext-Objekt/undefined statt Strings:
  // OpenCode ruft beim Plugin-Scan exportierte Funktionen ggf. mit dem
  // Plugin-Kontext auf → ohne Guard wirft path.resolve den Node-internen
  // TypeError 'The "paths[N]" property must be of type string'.
  // WICHTIG: No-Op (return ""), KEIN throw — ein throw wird vom Loader als
  // 'failed to load plugin' gewertet und kaskadiert den Server-Boot.
  if (typeof name !== "string" || name.length === 0) return ""
  if (typeof cwd !== "string" || cwd.length === 0) cwd = process.cwd()
  const candidates: string[] = []
  if (_pluginDir) {
    candidates.push(resolve(_pluginDir, name))
    candidates.push(resolve(_pluginDir, "..", "src", name))
  }
  candidates.push(resolve(cwd, name))
  const found = candidates.find(existsSync)
  if (!found) throw new Error(`${name} not found in plugin dir, src/, or CWD (${cwd}) -- run install script or copy .py files to project root`)
  return found
}

const _pythonCache = new Map<string, string>()

export function detectPython(): string {
  const key = process.platform
  if (_pythonCache.has(key)) return _pythonCache.get(key)!
  const candidates = process.platform === "win32"
    ? [["python"], ["py", "-3"], ["py"], ["python3"]]
    : [["python3"], ["python"], ["py", "-3"], ["py"]]
  for (const [cmd, ...args] of candidates) {
    try {
      const r = spawnSync(cmd, [...args, "-c", "import sys; print(sys.executable)"], { encoding: "utf-8", timeout: 3000 })
      if (r.status === 0 && !r.error) {
        const fp = (r.stdout || "").trim().split(/\r?\n/)[0].trim()
        if (fp) { _pythonCache.set(key, fp); return fp }
      }
    } catch { /* try next */ }
  }
  _pythonCache.set(key, "python"); return "python"
}

export function splitArgs(cmd: string): string[] {
  const args: string[] = []; const re = /[^\s"']+|"([^"]*)"|'([^']*)'/g; let m
  while ((m = re.exec(cmd)) !== null) args.push(m[1] || m[2] || m[0])
  return args
}

// ===========================================================================
// v2-Adapter (OpenCode >= 2.0, 2026-10-14)
// ===========================================================================
// v1-Funktions-Exporte scheitern unter v2 mit
// PluginModule.LoadError ("must export a default definition with an id and an
// effect or setup function"). Jedes Tool-Plugin exportiert daher
// `{ id, setup(ctx) }` und registriert sein Tool ueber ctx.tool.transform.
// Diese Helfer bilden das ab und halten die v1-Execute-Bodies unveraendert
// (Signatur `run(input, ctx)` mit ctx = { cwd, ...execCtx }).

export function commandSchema(description: string) {
  return {
    type: "object" as const,
    properties: { command: { type: "string" as const, description } },
    required: ["command"],
    additionalProperties: false,
  }
}

export function registerTool(
  ctx: any,
  spec: {
    name: string
    description: string
    input: any
    run: (input: any, ctx: any) => any
  },
) {
  const transform = ctx?.tool?.transform
  if (typeof transform !== "function") {
    // Kein v2-tool-Domain vorhanden -> No-Op statt throw (Loader-Gate).
    console.warn(`[utils] ctx.tool.transform fehlt - Tool "${spec.name}" nicht registriert`)
    return Promise.resolve()
  }
  return transform((editor: any) => {
    editor.add({
      name: spec.name,
      description: spec.description,
      input: spec.input,
      async execute(input: any, execCtx: any) {
        const cwd = execCtx?.cwd || execCtx?.directory || execCtx?.worktree || process.cwd()
        const out = await spec.run(input, { ...(execCtx || {}), cwd })
        return { content: typeof out === "string" ? out : String(out) }
      },
    })
  })
}

// utils.ts wird ebenfalls als Plugin gescannt -> gueltiger Default-Export,
// damit kein "failed to load plugin" mehr entsteht. Reines No-Op (die
// Named-Exports oben sind der eigentliche Zweck des Moduls).
export default { id: "tools-utils", async setup() { /* shared helper, not a plugin */ } }
