#!/usr/bin/env python3
"""health — project health summary. Analyze test status, lint quality, and code metrics.

Usage:
  health                          Show full health summary
  health --json                   JSON output
  health --check                  Exit 0 only if all checks pass
  health --quick                  Skip running tests (faster)

Metrics:
  - pytest:   pass rate, total/fail count
  - mypy:     error count
  - ruff:     violation count
  - lines:    total lines of code per language
  - files:    source file count per language
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any

from common import VERSION, reconfigure_stdout_stderr

reconfigure_stdout_stderr()

PY_SOURCE_EXTS = {".py"}
CPP_SOURCE_EXTS = {".c", ".cpp", ".h", ".hpp", ".cc", ".cxx", ".hxx", ".hh"}
TS_SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
ALL_EXTS = PY_SOURCE_EXTS | CPP_SOURCE_EXTS | TS_SOURCE_EXTS
EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".eggs",
    "env",
    "venv",
    ".ruff_cache",
    ".mypy_cache",
}


def _run_cmd(cmd: list[str], cwd: str, timeout: int = 120) -> tuple[str, str, int]:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd
        )
        return r.stdout, r.stderr, r.returncode
    except FileNotFoundError:
        return "", "command not found", -1
    except subprocess.TimeoutExpired:
        return "", "timed out", -1


def _walk_files(root: str) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in ALL_EXTS:
                files.append(os.path.join(dirpath, name))
    return files


def _count_lines(files: list[str]) -> tuple[int, dict[str, int]]:
    total = 0
    by_lang: dict[str, int] = {}
    for fp in files:
        ext = os.path.splitext(fp)[1].lower()
        lang = "python" if ext in PY_SOURCE_EXTS else ("cpp" if ext in CPP_SOURCE_EXTS else "typescript")
        try:
            with open(fp, "r", encoding="utf-8-sig", errors="replace") as f:
                count = sum(1 for _ in f)
            total += count
            by_lang[lang] = by_lang.get(lang, 0) + count
        except OSError:
            pass
    return total, by_lang


def _run_pytest(root: str, quick: bool = False) -> dict[str, Any]:
    if quick:
        return {"status": "skipped", "total": 0, "passed": 0, "failed": 0, "errors": 0}

    stdout, stderr, code = _run_cmd([sys.executable, "-m", "pytest", "-q", "--tb=no"], root, timeout=120)
    total = 0
    passed = 0
    failed = 0
    errors = 0

    match = re.search(r"(\d+) passed", stdout or stderr)
    if match:
        passed = int(match.group(1))
    match = re.search(r"(\d+) failed", stdout or stderr)
    if match:
        failed = int(match.group(1))
    match = re.search(r"(\d+) errors", stdout or stderr)
    if match:
        errors = int(match.group(1))
    total = passed + failed + errors

    return {
        "status": "ok" if code == 0 else "fail",
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
    }


def _run_mypy(root: str, quick: bool = False) -> dict[str, Any]:
    if quick:
        return {"status": "skipped", "errors": 0, "files": 0}

    stdout, stderr, code = _run_cmd([sys.executable, "-m", "mypy", "."], root, timeout=120)
    output = stdout or stderr
    match = re.search(r"(\d+) errors in (\d+) files", output)
    if match:
        return {
            "status": "fail" if int(match.group(1)) > 0 else "ok",
            "errors": int(match.group(1)),
            "files": int(match.group(2)),
        }
    if "No issues found" in output or "Success" in output:
        return {"status": "ok", "errors": 0, "files": 0}
    return {"status": "fail", "errors": -1, "files": 0}


def _run_ruff(root: str, quick: bool = False) -> dict[str, Any]:
    if quick:
        return {"status": "skipped", "violations": 0, "files": 0}

    stdout, stderr, code = _run_cmd([sys.executable, "-m", "ruff", "check", "."], root, timeout=60)
    output = stdout or stderr
    if code == 0:
        return {"status": "ok", "violations": 0, "files": 0}
    match = re.search(r"Found (\d+) error(?:s)?", output)
    if match:
        return {"status": "fail", "violations": int(match.group(1)), "files": 0}
    return {"status": "fail", "violations": -1, "files": 0}


def _collect_metrics(root: str, quick: bool = False) -> dict[str, Any]:
    files = _walk_files(root)
    total_lines, lines_by_lang = _count_lines(files)

    by_ext: dict[str, int] = {}
    for fp in files:
        ext = os.path.splitext(fp)[1].lower()
        by_ext[ext] = by_ext.get(ext, 0) + 1

    file_count = {
        "total": len(files),
        "python": sum(1 for f in files if os.path.splitext(f)[1].lower() in PY_SOURCE_EXTS),
        "cpp": sum(1 for f in files if os.path.splitext(f)[1].lower() in CPP_SOURCE_EXTS),
        "typescript": sum(1 for f in files if os.path.splitext(f)[1].lower() in TS_SOURCE_EXTS),
    }

    return {
        "files": file_count,
        "lines": {"total": total_lines, "by_language": lines_by_lang},
    }


def health(root: str, quick: bool = False) -> dict[str, Any]:
    metrics = _collect_metrics(root, quick)
    return {
        "version": VERSION,
        "project": root,
        "metrics": metrics,
        "tests": _run_pytest(root, quick),
        "mypy": _run_mypy(root, quick),
        "ruff": _run_ruff(root, quick),
    }


def _fmt_line(key: str, label: str, value: str) -> str:
    return f"  {label:<14s} {value}"


def format_pretty(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"health: opencode-tools v{data['version']}")
    lines.append(f"  project: {data['project']}")
    lines.append("")

    m = data["metrics"]
    lines.append("[metrics]")
    lines.append(
        f"  files:   {m['files']['total']} ({m['files']['python']} py, {m['files']['cpp']} cpp, {m['files']['typescript']} ts)"
    )
    lines.append(f"  lines:   {m['lines']['total']}")
    for lang, count in sorted(m["lines"]["by_language"].items()):
        lines.append(f"    {lang}: {count}")
    lines.append("")

    t = data["tests"]
    lines.append(f"[tests] {t['status']}")
    if t["status"] != "skipped":
        lines.append(f"  total:   {t['total']}")
        lines.append(f"  passed:  {t['passed']}")
        lines.append(f"  failed:  {t['failed']}")
        lines.append(f"  errors:  {t['errors']}")
    lines.append("")

    for tool, key in [("mypy", "mypy"), ("ruff", "ruff")]:
        x = data[tool]
        lines.append(f"[{tool}] {x['status']}")
        if x["status"] != "skipped":
            if tool == "mypy":
                lines.append(f"  errors:  {x['errors']} in {x['files']} files")
            else:
                lines.append(f"  violations: {x['violations']}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"health.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args or not args:
        print(__doc__.strip())
        return 0

    use_json = "--json" in args
    check_mode = "--check" in args
    quick = "--quick" in args

    root = os.getcwd()
    for a in args:
        if a.startswith("--root="):
            root = a.split("=", 1)[1]
        elif a == "--root":
            idx = args.index(a) + 1
            if idx < len(args):
                root = args[idx]

    result = health(root, quick)

    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(format_pretty(result))

    if check_mode:
        checks = [result["tests"]["status"], result["mypy"]["status"], result["ruff"]["status"]]
        if "fail" in checks:
            return 1
        if "skipped" in checks and quick:
            return 0
        return 0 if all(c == "ok" for c in checks) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
