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
