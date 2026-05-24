#!/usr/bin/env python3
"""churn — git churn analysis. Find files with the most changes.

Usage:
  churn                           All files, sorted by commit count
  churn -n <N>                    Top N files (default: 20)
  churn --since <date>            Only commits since date (e.g. '2026-01-01')
  churn --min-commits <N>         Minimum commits (default: 2)
  churn --json                    JSON output
  churn --root <dir>              Run in specific directory
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import defaultdict

from common import VERSION, reconfigure_stdout_stderr

reconfigure_stdout_stderr()


def _run(cmd: list[str], cwd: str, timeout: int = 60) -> str:
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd
        )
        if r.returncode != 0:
            return ""
        return r.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _ensure_git_repo(root: str) -> bool:
    out = _run(["git", "rev-parse", "--git-dir"], root)
    return bool(out.strip())


def get_churn(root: str, since: str = "", top_n: int = 0, min_commits: int = 2) -> dict[str, int]:
    cmd = ["git", "log", "--pretty=format:", "--name-only"]
    if since:
        cmd.extend(["--since", since])
    cmd.append("--diff-filter=AMCR")

    out = _run(cmd, root)
    if not out:
        return {}

    counts: dict[str, int] = defaultdict(int)
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith("{"):
            counts[line] += 1

    filtered = {f: c for f, c in counts.items() if c >= min_commits}
    sorted_files = sorted(filtered.items(), key=lambda x: -x[1])

    if top_n > 0:
        sorted_files = sorted_files[:top_n]

    return dict(sorted_files)


def format_pretty(churn: dict[str, int]) -> str:
    if not churn:
        return "churn: No data (empty repo or no matching commits)"

    lines: list[str] = ["churn:"]
    for i, (f, c) in enumerate(churn.items(), 1):
        bar = "█" * min(c, 40)
        lines.append(f"  {i:3d}. {bar} {c:3d}x  {f}")
    lines.append("")
    lines.append(f"  Total: {len(churn)} files")
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"churn.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0

    root = os.getcwd()
    use_json = "--json" in args
    top_n = 20
    since = ""
    min_commits = 2

    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--root="):
            root = a.split("=", 1)[1]
        elif a == "--root" and i + 1 < len(args):
            root = args[i + 1]
            i += 1
        elif a.startswith("-n"):
            val = a[2:] or (args[i + 1] if i + 1 < len(args) else "20")
            try:
                top_n = int(val)
            except ValueError:
                pass
            if not a[2:]:
                i += 1
        elif a.startswith("--since"):
            val = a.split("=", 1)[1] if "=" in a else (args[i + 1] if i + 1 < len(args) else "")
            since = val
            if "=" not in a:
                i += 1
        elif a.startswith("--min-commits"):
            val = a.split("=", 1)[1] if "=" in a else (args[i + 1] if i + 1 < len(args) else "2")
            try:
                min_commits = int(val)
            except ValueError:
                pass
            if "=" not in a:
                i += 1
        i += 1

    if not os.path.isdir(root):
        print(f"Directory not found: {root}", file=sys.stderr)
        return 1

    if not _ensure_git_repo(root):
        print("Not a git repository", file=sys.stderr)
        return 1

    churn = get_churn(root, since, top_n, min_commits)

    if use_json:
        print(json.dumps({"files": churn, "count": len(churn)}, indent=2))
    else:
        print(format_pretty(churn))

    return 0 if churn else 1


if __name__ == "__main__":
    sys.exit(main())
