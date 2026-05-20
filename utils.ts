import { spawnSync } from "child_process"

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
