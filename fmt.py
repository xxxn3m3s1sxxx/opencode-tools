#!/usr/bin/env python3
"""fmt — format runner. Run ruff format (and optional prettier) on the project.

Usage:
  fmt                               Format all supported files
  fmt --check                       Check mode (read-only, exit 1 if unformatted)
  fmt --ruff                        Ruff format only (default)
  fmt --prettier                    Prettier only (requires prettier on PATH)
  fmt --all                         Both ruff and prettier
  fmt --json                        JSON output
  fmt --root <dir>                  Run in specific directory
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from common import VERSION, EXCLUDE_DIRS, reconfigure_stdout_stderr

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


def fmt_ruff(root: str, check: bool = False) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "ruff", "format"]
    if check:
        cmd.append("--check")
    cmd.append(".")
    out, code = _run(cmd, root, 60)
    return {
        "tool": "ruff",
        "status": "ok" if code == 0 else "fail",
        "check": check,
        "exit_code": code,
        "output": out,
    }


def fmt_prettier(root: str, check: bool = False) -> dict[str, Any]:
    cmd = ["npx", "prettier"]
    if check:
        cmd.append("--check")
    else:
        cmd.append("--write")
    cmd.extend(["--ignore-path", ".gitignore", "."])
    out, code = _run(cmd, root, 120)
    return {
        "tool": "prettier",
        "status": "ok" if code == 0 else "fail",
        "check": check,
        "exit_code": code,
        "output": out,
    }


def _fmt_row(label: str, status: str, detail: str = "") -> str:
    icon = "✅" if status == "ok" else "❌"
    return f"  {icon} {label:<12s} {detail}"


def format_pretty(results: list[dict[str, Any]]) -> str:
    lines: list[str] = ["fmt:"]
    all_ok = True
    for r in results:
        if r["status"] == "ok":
            lines.append(_fmt_row(r["tool"], "ok", "(check)" if r.get("check") else ""))
        else:
            all_ok = False
            mode = "check" if r.get("check") else "format"
            lines.append(_fmt_row(r["tool"], "fail", f"{mode} exited {r['exit_code']}"))
    lines.append("")
    if all_ok:
        lines.append("  ✅ All formatters passed")
    else:
        lines.append("  ❌ Some formatters failed")
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"fmt.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0

    root = os.getcwd()
    use_json = "--json" in args
    check = "--check" in args
    only_ruff = "--ruff" in args or not ("--prettier" in args or "--all" in args)
    only_prettier = "--prettier" in args
    both = "--all" in args

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

    if both or only_ruff:
        results.append(fmt_ruff(root, check))
    if both or only_prettier:
        results.append(fmt_prettier(root, check))

    if use_json:
        print(json.dumps(results, indent=2))
    else:
        print(format_pretty(results))

    return 0 if all(r["status"] == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
