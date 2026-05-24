#!/usr/bin/env python3
"""snapshot — capture workspace context for MemPalace auto-save.

Takes a snapshot of the current workspace state: git status, file changes,
recent commits, tool versions, and directory structure. Saves as a timestamped
markdown file for MemPalace mining.

Usage:
  snapshot                          Save snapshot to .opencode/snapshots/
  snapshot --show                   Print snapshot to stdout only
  snapshot --mine                   Save + mine into MemPalace (needs Python 3.11)
  snapshot --dir <path>             Snapshot a specific directory
  snapshot --json                   JSON output
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from common import VERSION, reconfigure_stdout_stderr

reconfigure_stdout_stderr()

EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", "build", "dist", ".eggs", "env", "venv", ".ruff_cache", ".mypy_cache", ".opencode"}
SNAPSHOT_DIR = ".opencode/snapshots"


def _run(cmd: list[str], cwd: str | None = None, timeout: int = 30) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd)
        return (r.stdout or r.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _git_info(root: str) -> dict[str, Any]:
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    commit = _run(["git", "rev-parse", "--short", "HEAD"], root)
    msg = _run(["git", "log", "-1", "--format=%s"], root)
    status = _run(["git", "status", "--short"], root)
    dirty_lines = [l for l in status.split("\n") if l.strip()] if status else []
    log = _run(["git", "log", "--oneline", "-10"], root)
    log_lines = log.split("\n") if log else []

    return {
        "branch": branch or "(not a git repo)",
        "commit": commit or "",
        "message": msg or "",
        "dirty_files": len(dirty_lines),
        "dirty": [l[:80] for l in dirty_lines[:20]],
        "recent_commits": [l[:80] for l in log_lines],
    }


def _file_stats(root: str) -> dict[str, Any]:
    total_files = 0
    total_lines = 0
    by_ext: dict[str, int] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            fp = os.path.join(dirpath, name)
            total_files += 1
            by_ext[ext] = by_ext.get(ext, 0) + 1
            try:
                with open(fp, "rb") as f:
                    total_lines += sum(1 for _ in f)
            except OSError:
                pass

    return {
        "total_files": total_files,
        "total_lines": total_lines,
        "by_extension": dict(sorted(by_ext.items(), key=lambda x: -x[1])),
    }


def _tool_versions(root: str) -> dict[str, str]:
    versions = {}
    tools = ["common", "graph", "changelog", "impact", "lint", "refactor", "rename", "verify", "search", "calltrace", "hashline", "health", "snapshot"]
    for t in tools:
        fp = os.path.join(root, f"{t}.py")
        if os.path.exists(fp):
            r = _run([sys.executable, fp, "--version"], root)
            if r:
                versions[t] = r.split()[-1]
    return versions


def _dir_tree(root: str, max_depth: int = 2) -> list[str]:
    lines: list[str] = []
    root_name = os.path.basename(root) or root

    def walk(dirpath: str, depth: int) -> None:
        if depth > max_depth:
            return
        indent = "  " * depth
        dirname = os.path.basename(dirpath) or dirpath
        lines.append(f"{indent}{dirname}/")
        try:
            entries = sorted(os.listdir(dirpath))
        except OSError:
            return
        for e in entries:
            if e.startswith("."):
                continue
            if e in EXCLUDE_DIRS:
                continue
            full = os.path.join(dirpath, e)
            if os.path.isdir(full):
                walk(full, depth + 1)
            else:
                lines.append(f"{indent}  {e}")

    walk(root, 0)
    return lines


def snapshot(root: str) -> dict[str, Any]:
    now = datetime.now()
    return {
        "tool": "snapshot",
        "version": VERSION,
        "timestamp": now.isoformat(),
        "date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "project": root,
        "project_name": os.path.basename(root) or root,
        "git": _git_info(root),
        "files": _file_stats(root),
        "tools": _tool_versions(root),
    }


def format_markdown(data: dict[str, Any], tree: list[str]) -> str:
    lines: list[str] = []
    lines.append(f"# Snapshot: {data['project_name']}")
    lines.append(f"**Date:** {data['date']}")
    lines.append(f"**Tool:** snapshot v{data['version']}")
    lines.append("")

    lines.append("## Git")
    lines.append(f"- **Branch:** {data['git']['branch']}")
    lines.append(f"- **Commit:** {data['git']['commit']}")
    lines.append(f"- **Message:** {data['git']['message']}")
    lines.append(f"- **Dirty files:** {data['git']['dirty_files']}")
    if data['git']['dirty']:
        lines.append("- Changes:")
        for l in data['git']['dirty']:
            lines.append(f"  - `{l}`")
    if data['git']['recent_commits']:
        lines.append("- Recent commits:")
        for l in data['git']['recent_commits']:
            lines.append(f"  - `{l}`")
    lines.append("")

    lines.append("## Files")
    lines.append(f"- **Total files:** {data['files']['total_files']}")
    lines.append(f"- **Total lines:** {data['files']['total_lines']}")
    lines.append("- By extension:")
    for ext, count in data['files']['by_extension'].items():
        lines.append(f"  - `{ext}`: {count}")
    lines.append("")

    lines.append("## Directory Tree")
    for l in tree:
        lines.append(l)
    lines.append("")

    if data["tools"]:
        lines.append("## Tool Versions")
        for t, v in data["tools"].items():
            lines.append(f"- **{t}:** v{v}")
        lines.append("")

    return "\n".join(lines)


def save_snapshot(root: str, data: dict[str, Any], tree: list[str]) -> str:
    snap_dir = Path(root) / SNAPSHOT_DIR
    snap_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fp = snap_dir / f"snapshot_{timestamp}.md"
    fp.write_text(format_markdown(data, tree), encoding="utf-8")
    return str(fp)


def try_mempalace_mine(filepath: str) -> bool:
    candidates = [
        r"C:\Users\skap\AppData\Local\Programs\Python\Python311\python.exe",
    ]
    for py in candidates:
        if os.path.exists(py):
            r = subprocess.run(
                [py, "-m", "mempalace", "mine", "--mode", "projects", os.path.dirname(filepath)],
                capture_output=True, text=True, timeout=30,
            )
            return r.returncode == 0
    return False


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"snapshot.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0

    show_only = "--show" in args
    do_mine = "--mine" in args
    use_json = "--json" in args

    root = os.getcwd()
    for a in args:
        if a.startswith("--dir="):
            root = a.split("=", 1)[1]
        elif a == "--dir":
            idx = args.index(a) + 1
            if idx < len(args):
                root = args[idx]

    if not os.path.isdir(root):
        print(f"Directory not found: {root}", file=sys.stderr)
        return 1

    data = snapshot(root)
    tree = _dir_tree(root)

    if use_json:
        print(json.dumps(data, indent=2))
        return 0

    if show_only:
        print(format_markdown(data, tree))
        return 0

    path = save_snapshot(root, data, tree)
    print(f"Snapshot saved: {path}")

    if do_mine:
        if try_mempalace_mine(path):
            print("Filed into MemPalace ✅")
        else:
            print("MemPalace not available (needs Python 3.11)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
