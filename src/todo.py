#!/usr/bin/env python3
"""todo — scan for TODO, FIXME, HACK, XXX markers across the codebase.

Usage:
  todo                              Scan and show all markers grouped by file
  todo --all                        Include resolved markers (if tracked)
  todo --count                      Just show counts per tag type
  todo --json                       JSON output
  todo --file <path>                Scan a specific file only
  todo --root <dir>                 Scan a specific directory

Tag types: TODO, FIXME, HACK, XXX, BUG, OPTIMIZE, NOTE, REVIEW, WORKAROUND
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from typing import Any

from common import VERSION, SOURCE_EXTS, _walk_files, _read_file, reconfigure_stdout_stderr

reconfigure_stdout_stderr()

TAG_PATTERN = re.compile(
    r"(?i)(?<!\w)(TODO|FIXME|HACK|XXX|BUG|OPTIMIZE|NOTE|REVIEW|WORKAROUND)" r"(?:\(([^)]*)\))?\s*:\s*(.*?)$",
    re.MULTILINE,
)
TAG_ORDER = ["TODO", "FIXME", "HACK", "XXX", "BUG", "OPTIMIZE", "NOTE", "REVIEW", "WORKAROUND"]


def _scan_file(filepath: str) -> list[dict[str, Any]]:
    content = _read_file(filepath)
    if content is None:
        return []
    markers: list[dict[str, Any]] = []
    for m in TAG_PATTERN.finditer(content):
        line_no = content[: m.start()].count("\n") + 1
        markers.append(
            {
                "tag": m.group(1).upper(),
                "author": m.group(2) or "",
                "message": m.group(3).strip(),
                "line": line_no,
                "file": filepath,
            }
        )
    return markers


def scan(root: str, single_file: str | None = None) -> list[dict[str, Any]]:
    if single_file:
        if not os.path.exists(single_file):
            return []
        return _scan_file(single_file)

    files = _walk_files(root, SOURCE_EXTS)
    all_markers: list[dict[str, Any]] = []
    for fp in files:
        all_markers.extend(_scan_file(fp))
    return all_markers


def _fmt_count(count: int) -> str:
    return f"{count} item{'s' if count != 1 else ''}"


def format_pretty(markers: list[dict[str, Any]], root: str) -> str:
    lines: list[str] = []
    if not markers:
        lines.append("  No TODO/FIXME/HACK markers found.")
        lines.append("  (clean codebase — or nothing matched)")
        return "\n".join(lines)

    by_file: dict[str, list[dict[str, Any]]] = {}
    for m in markers:
        by_file.setdefault(m["file"], []).append(m)

    total = len(markers)
    lines.append(f"  {_fmt_count(total)} across {len(by_file)} files:")
    lines.append("")

    for fp in sorted(by_file.keys()):
        rel = os.path.relpath(fp, root)
        items = sorted(by_file[fp], key=lambda x: x["line"])
        tags = Counter(m["tag"] for m in items)
        tag_summary = ", ".join(f"{k}={v}" for k, v in sorted(tags.most_common()))
        lines.append(f"  {rel}  ({tag_summary}):")
        for m in items:
            tag = m["tag"]
            msg = m["message"][:100]
            author = f" ({m['author']})" if m["author"] else ""
            lines.append(f"    {tag:<12s} L{m['line']:4d}{author}  {msg}")
        lines.append("")

    return "\n".join(lines)


def format_count(markers: list[dict[str, Any]]) -> str:
    if not markers:
        return "  No markers found."

    counts = Counter(m["tag"] for m in markers)
    total = len(markers)
    lines: list[str] = []
    lines.append(f"  Total: {total}")
    for tag in TAG_ORDER:
        if tag in counts:
            lines.append(f"  {tag:<12s} {counts[tag]}")
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"todo.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0

    use_json = "--json" in args
    count_only = "--count" in args
    single_file: str | None = None
    root = os.getcwd()

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--json", "--count", "--all"):
            i += 1
            continue
        if a == "--file" and i + 1 < len(args):
            single_file = args[i + 1]
            i += 2
            continue
        if a.startswith("--file="):
            single_file = a.split("=", 1)[1]
            i += 1
            continue
        if a == "--root" and i + 1 < len(args):
            root = args[i + 1]
            i += 2
            continue
        if a.startswith("--root="):
            root = a.split("=", 1)[1]
            i += 1
            continue
        if a.startswith("-"):
            print(f"Unknown flag: {a}", file=sys.stderr)
            return 1
        i += 1

    if not os.path.isdir(root) and single_file is None:
        print(f"Directory not found: {root}", file=sys.stderr)
        return 1

    markers = scan(root, single_file)

    if use_json:
        print(json.dumps(markers, indent=2))
        return 0

    if count_only:
        print(format_count(markers))
        return 0

    print(format_pretty(markers, root))
    return 0 if markers else 1


if __name__ == "__main__":
    sys.exit(main())
