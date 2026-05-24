#!/usr/bin/env python3
"""tags — ctags-style symbol indexer. Build a searchable index of all definitions.

Usage:
  tags                              Build and show tag index for current project
  tags <symbol>                     Look up a specific symbol
  tags --build                      Force rebuild index
  tags --json                       JSON output
  tags --root <dir>                 Index a specific directory
  tags --stats                      Show index statistics
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from typing import Any

from common import VERSION, SOURCE_EXTS, _walk_files, _read_file, reconfigure_stdout_stderr

reconfigure_stdout_stderr()

CPP_TAG_PATTERNS: list[tuple[str, str]] = [
    (r"(?:class|struct)\s+(\w+)", "class"),
    (r"(?:enum|union)\s+(\w+)", "enum"),
    (r"(?:void|int|bool|char|float|double|size_t|auto|const\s+\w+[\s*&]+)(\w+)\s*\(", "function"),
    (r"(\w+)\s*::\s*(\w+)\s*\(", "method"),
    (r"#define\s+(\w+)", "macro"),
    (r"using\s+(\w+)\s*=", "typealias"),
    (r"typedef\s+.*\s+(\w+);", "typedef"),
]

TS_TAG_PATTERNS: list[tuple[str, str]] = [
    (r"(?:export\s+)?(?:async\s+)?function\s+(\w+)", "function"),
    (r"(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", "class"),
    (r"(?:export\s+)?interface\s+(\w+)", "interface"),
    (r"(?:export\s+)?type\s+(\w+)\s*=", "typealias"),
    (r"(?:export\s+)?(?:const\s+)?enum\s+(\w+)", "enum"),
    (r"(?:export\s+)?const\s+(\w+)\s*(?::[^=;]+)?\s*=", "variable"),
    (r"(?:export\s+)?let\s+(\w+)\s*(?::[^=;]+)?\s*=", "variable"),
    (r"(?:export\s+)?var\s+(\w+)\s*(?::[^=;]+)?\s*=", "variable"),
    (r"(?:export\s+)?default\s+(?:function|class)\s+(\w+)", "default_export"),
    (r"@\w+\s*\n\s*(?:export\s+)?(?:class|function)\s+(\w+)", "decorated"),
]


def _py_tags(filepath: str) -> list[dict[str, Any]]:
    content = _read_file(filepath)
    if content is None:
        return []
    try:
        tree = ast.parse(content, filepath)
    except SyntaxError:
        return []
    tags: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            tags.append({"name": node.name, "kind": "function", "line": node.lineno, "file": filepath})
        elif isinstance(node, ast.ClassDef):
            tags.append({"name": node.name, "kind": "class", "line": node.lineno, "file": filepath})
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    tags.append({"name": t.id, "kind": "variable", "line": t.lineno, "file": filepath})
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            for alias in node.names:
                aname = alias.asname or alias.name.split(".")[0]
                tags.append({"name": aname, "kind": "import", "line": getattr(node, "lineno", 0), "file": filepath})
    return tags


def _cpp_tags(filepath: str) -> list[dict[str, Any]]:
    content = _read_file(filepath)
    if content is None:
        return []
    tags: list[dict[str, Any]] = []
    for pattern, kind in CPP_TAG_PATTERNS:
        for m in re.finditer(pattern, content):
            name = m.group(1) if kind != "method" else m.group(2)
            line_no = content[: m.start()].count("\n") + 1
            tags.append({"name": name, "kind": kind, "line": line_no, "file": filepath})
    return tags


def _ts_tags(filepath: str) -> list[dict[str, Any]]:
    content = _read_file(filepath)
    if content is None:
        return []
    tags: list[dict[str, Any]] = []
    for pattern, kind in TS_TAG_PATTERNS:
        for m in re.finditer(pattern, content, re.MULTILINE):
            name = m.group(1)
            line_no = content[: m.start()].count("\n") + 1
            tags.append({"name": name, "kind": kind, "line": line_no, "file": filepath})
    return tags


def _ext_to_lang(ext: str) -> str:
    if ext == ".py":
        return "py"
    if ext in (".c", ".cpp", ".h", ".hpp", ".cc", ".cxx", ".hxx", ".hh"):
        return "cpp"
    if ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        return "ts"
    return ""


def build_index(root: str) -> dict[str, list[dict[str, Any]]]:
    files = _walk_files(root, SOURCE_EXTS)
    index: dict[str, list[dict[str, Any]]] = {}
    tag_count = 0
    for fp in files:
        ext = os.path.splitext(fp)[1].lower()
        lang = _ext_to_lang(ext)
        if lang == "py":
            tags_list = _py_tags(fp)
        elif lang == "cpp":
            tags_list = _cpp_tags(fp)
        elif lang == "ts":
            tags_list = _ts_tags(fp)
        else:
            continue
        for t in tags_list:
            name = t["name"]
            index.setdefault(name, []).append(t)
            tag_count += 1
    return index


def lookup(index: dict[str, list[dict[str, Any]]], symbol: str) -> list[dict[str, Any]]:
    return index.get(symbol, [])


def index_stats(index: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    total_symbols = len(index)
    total_tags = sum(len(v) for v in index.values())
    by_kind: dict[str, int] = {}
    by_lang: dict[str, int] = {}
    for name, tags_list in index.items():
        for t in tags_list:
            by_kind[t["kind"]] = by_kind.get(t["kind"], 0) + 1
            ext = os.path.splitext(t["file"])[1].lower()
            by_lang[_ext_to_lang(ext)] = by_lang.get(_ext_to_lang(ext), 0) + 1
    return {
        "total_symbols": total_symbols,
        "total_tags": total_tags,
        "by_kind": dict(sorted(by_kind.items(), key=lambda x: -x[1])),
        "by_language": by_lang,
    }


def format_index(index: dict[str, list[dict[str, Any]]], root: str) -> str:
    lines: list[str] = []
    stat = index_stats(index)
    lines.append(f"  {stat['total_tags']} tags for {stat['total_symbols']} symbols across {stat['by_language']}:")
    for lang, count in sorted(stat["by_language"].items()):
        lines.append(f"    {lang}: {count}")
    lines.append("")
    by_kind = stat["by_kind"]
    lines.append(f"  Kinds: {', '.join(f'{k}={v}' for k, v in by_kind.items())}")
    lines.append("")
    for name in sorted(index.keys())[:50]:
        tags_list = index[name]
        files = sorted(set(t["file"] for t in tags_list))
        kinds = sorted(set(t["kind"] for t in tags_list))
        rels = ", ".join(os.path.relpath(f, root) for f in files[:3])
        if len(files) > 3:
            rels += f" (+{len(files) - 3} more)"
        lines.append(f"  {name:<30s} [{', '.join(kinds):20s}] {rels}")
    if len(index) > 50:
        lines.append(f"  ... and {len(index) - 50} more symbols")
    return "\n".join(lines)


def format_lookup(name: str, tags_list: list[dict[str, Any]], root: str) -> str:
    lines: list[str] = []
    lines.append(f"  {name} — {len(tags_list)} definition{'s' if len(tags_list) != 1 else ''}:")
    for t in sorted(tags_list, key=lambda x: (x["file"], x["line"])):
        rel = os.path.relpath(t["file"], root)
        lines.append(f"    {t['kind']:<12s} {rel}:{t['line']}")
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"tags.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0

    use_json = "--json" in args
    stats_only = "--stats" in args
    root = os.getcwd()

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--json", "--stats", "--build"):
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

    if not os.path.isdir(root):
        print(f"Directory not found: {root}", file=sys.stderr)
        return 1

    index = build_index(root)

    if stats_only:
        s = index_stats(index)
        if use_json:
            print(json.dumps(s, indent=2))
        else:
            lines = [f"  {s['total_tags']} tags, {s['total_symbols']} symbols"]
            for lang, count in sorted(s["by_language"].items()):
                lines.append(f"    {lang}: {count}")
            print("\n".join(lines))
        return 0

    # Lookup mode: first non-flag arg is the symbol
    clean_args = [a for a in args if not a.startswith("-")]
    if clean_args:
        symbol = clean_args[0]
        tags_list = lookup(index, symbol)
        if not tags_list:
            print(f"  Symbol '{symbol}' not found")
            return 1
        if use_json:
            print(json.dumps(tags_list, indent=2))
        else:
            print(format_lookup(symbol, tags_list, root))
        return 0

    # Default: show full index
    if use_json:
        print(json.dumps(index, indent=2))
    else:
        print(format_index(index, root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
