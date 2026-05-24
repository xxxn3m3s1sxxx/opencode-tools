#!/usr/bin/env python3
"""check — pre-commit gate. Run lint → mypy → tests, exit 0 only if all pass.

Usage:
  check                             Run all checks (lint + mypy + tests)
  check --lint                      Lint only (ruff)
  check --mypy                      Mypy only
  check --test                      Tests only (pytest)
  check --quick                     Skip tests (lint + mypy only)
  check --json                      JSON output
  check --root <dir>                Run checks in specific directory
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from common import VERSION, reconfigure_stdout_stderr

reconfigure_stdout_stderr()


def _run(cmd: list[str], cwd: str, timeout: int = 120) -> tuple[str, int]:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd
        )
        return (r.stdout + r.stderr).strip(), r.returncode
    except FileNotFoundError:
        return "command not found", -1
    except subprocess.TimeoutExpired:
        return "timed out", -1


def check_ruff(root: str) -> dict[str, Any]:
    out, code = _run([sys.executable, "-m", "ruff", "check", "."], root, 60)
    if code == 0:
        return {"status": "ok", "tool": "ruff", "errors": 0, "output": ""}
    import re

    m = re.search(r"Found (\d+) error", out)
    count = int(m.group(1)) if m else -1
    return {"status": "fail", "tool": "ruff", "errors": count, "output": out}


def check_mypy(root: str) -> dict[str, Any]:
    out, code = _run([sys.executable, "-m", "mypy", "."], root, 120)
    import re

    m = re.search(r"(\d+) errors? in (\d+) files?", out)
    if m:
        return {"status": "fail", "tool": "mypy", "errors": int(m.group(1)), "files": int(m.group(2)), "output": out}
    if "No issues found" in out or "Success" in out:
        return {"status": "ok", "tool": "mypy", "errors": 0, "files": 0, "output": ""}
    return {"status": "fail", "tool": "mypy", "errors": -1, "files": 0, "output": out}


def check_tests(root: str) -> dict[str, Any]:
    out, code = _run([sys.executable, "-m", "pytest", "-q", "--tb=short"], root, 180)
    import re

    passed = 0
    failed = 0
    errors = 0
    m = re.search(r"(\d+) passed", out)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+) failed", out)
    if m:
        failed = int(m.group(1))
    m = re.search(r"(\d+) errors", out)
    if m:
        errors = int(m.group(1))
    total = passed + failed + errors
    return {
        "status": "ok" if code == 0 else "fail",
        "tool": "pytest",
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "output": "" if code == 0 else out,
    }


def _fmt_row(label: str, status: str, detail: str = "") -> str:
    icon = "✅" if status == "ok" else ("❌" if status == "fail" else "⏭️")
    return f"  {icon} {label:<12s} {detail}"


def format_pretty(results: list[dict[str, Any]]) -> str:
    lines: list[str] = ["check:"]
    all_ok = True
    for r in results:
        if r["status"] == "ok":
            if r["tool"] == "ruff":
                lines.append(_fmt_row("ruff", "ok", "0 errors"))
            elif r["tool"] == "mypy":
                lines.append(_fmt_row("mypy", "ok", "0 errors"))
            elif r["tool"] == "pytest":
                lines.append(_fmt_row("pytest", "ok", f"{r['passed']}/{r['total']} passed"))
        elif r["status"] == "fail":
            all_ok = False
            if r["tool"] == "ruff":
                lines.append(_fmt_row("ruff", "fail", f"{r['errors']} errors"))
            elif r["tool"] == "mypy":
                lines.append(_fmt_row("mypy", "fail", f"{r['errors']} errors in {r.get('files', 0)} files"))
            elif r["tool"] == "pytest":
                lines.append(_fmt_row("pytest", "fail", f"{r['failed']} failed, {r['errors']} errors"))
        else:
            all_ok = False
            lines.append(_fmt_row(r["tool"], "skipped"))

    lines.append("")
    if all_ok:
        lines.append("  ✅ All checks passed")
    else:
        lines.append("  ❌ Some checks failed")

    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"check.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0

    use_json = "--json" in args
    quick = "--quick" in args
    only_lint = "--lint" in args
    only_mypy = "--mypy" in args
    only_test = "--test" in args
    root = os.getcwd()

    for a in args:
        if a.startswith("--root="):
            root = a.split("=", 1)[1]
        elif a == "--root":
            idx = args.index(a) + 1
            if idx < len(args):
                root = args[idx]

    if not os.path.isdir(root):
        print(f"Directory not found: {root}", file=sys.stderr)
        return 1

    results: list[dict[str, Any]] = []

    if only_mypy:
        results = [check_mypy(root)]
    elif only_test:
        results = [check_tests(root)]
    elif only_lint:
        results = [check_ruff(root)]
    else:
        results.append(check_ruff(root))
        results.append(check_mypy(root))
        if not quick:
            results.append(check_tests(root))

    if use_json:
        print(json.dumps(results, indent=2))
    else:
        print(format_pretty(results))

    return 0 if all(r["status"] == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
