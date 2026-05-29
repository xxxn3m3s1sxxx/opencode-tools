#!/usr/bin/env python3
"""ghost — dead code finder. Detect unused functions, classes, and imports.

Usage:
  ghost                           Scan current directory
  ghost --root <dir>              Scan specific directory
  ghost --lang py                 Only Python files
  ghost --lang ts                 Only TypeScript/JS files
  ghost --json                    JSON output
  ghost --min-uses <N>            Minimum uses before considered "used" (default: 1)
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import defaultdict
from typing import Any

from common import VERSION, EXCLUDE_DIRS, PY_SOURCE_EXTS, TS_SOURCE_EXTS, reconfigure_stdout_stderr

reconfigure_stdout_stderr()


def _walk(root: str, exts: set[str]) -> list[str]:
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for f in filenames:
            _, ext = os.path.splitext(f)
            if ext.lower() in exts:
                files.append(os.path.join(dirpath, f))
    return sorted(files)


def _unused_py(filepath: str, min_uses: int) -> list[dict[str, Any]]:
    unused: list[dict[str, Any]] = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read(), filename=filepath)
    except (SyntaxError, OSError):
        return unused

    definitions: dict[str, int] = defaultdict(int)
    references: dict[str, int] = defaultdict(int)
    def_kinds: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions[node.name] += 1
            def_kinds[node.name] = "function"
        elif isinstance(node, ast.ClassDef):
            definitions[node.name] += 1
            def_kinds[node.name] = "class"
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            references[node.id] += 1
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            references[node.attr] += 1

    _TEST_LIFECYCLE = {
        "setUp",
        "tearDown",
        "setUpClass",
        "tearDownClass",
        "setUpModule",
        "tearDownModule",
    }

    for name, def_count in definitions.items():
        ref_count = references.get(name, 0)
        if name.startswith("_") and not name.startswith("__"):
            continue
        if name in _TEST_LIFECYCLE or name.startswith("test_"):
            continue
        if name.startswith("Test"):
            continue
        if name in {"main"}:
            continue
        if ref_count < min_uses:
            unused.append(
                {
                    "name": name,
                    "kind": def_kinds.get(name, "function"),
                    "file": filepath,
                    "definitions": def_count,
                    "references": ref_count,
                }
            )

    return unused


_TS_FUNC_PATTERN = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)|"
    r"(?:export\s+)?(?:const\s+)(?P<const_name>\w+)\s*=\s*(?:async\s+)?(?:\(|function)"
)

_TS_CLASS_PATTERN = re.compile(r"(?:export\s+)?class\s+(?P<name>\w+)")

_TS_REF_PATTERN = re.compile(r"(?<![.\w])(?P<name>\w+)(?=\s*[\(,;:)\]={}])")


def _scan_ts(filepath: str, content: str) -> tuple[list[str], list[str], list[str]]:
    funcs: list[str] = []
    classes: list[str] = []
    refs: list[str] = []
    for m in _TS_FUNC_PATTERN.finditer(content):
        name = m.group("name") or m.group("const_name")
        if name:
            funcs.append(name)
    for m in _TS_CLASS_PATTERN.finditer(content):
        classes.append(m.group("name"))
    for m in _TS_REF_PATTERN.finditer(content):
        name = m.group("name")
        if name and not name[0].isupper() and not name.startswith("_"):
            refs.append(name)
    return funcs, classes, refs


def _unused_ts(filepath: str, min_uses: int) -> list[dict[str, Any]]:
    unused: list[dict[str, Any]] = []
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError:
        return unused

    funcs, classes, refs = _scan_ts(filepath, content)
    all_defs: dict[str, str] = {}
    for fn in funcs:
        all_defs[fn] = "function"
    for cl in classes:
        all_defs[cl] = "class"

    ref_counts: dict[str, int] = defaultdict(int)
    for r in refs:
        ref_counts[r] += 1

    for name, kind in all_defs.items():
        if name in {"main", "exports", "default", "handler"}:
            continue
        rc = ref_counts.get(name, 0)
        if rc < min_uses:
            unused.append(
                {
                    "name": name,
                    "kind": kind,
                    "file": filepath,
                    "definitions": 1,
                    "references": rc,
                }
            )

    return unused


def _filter_builtins(name: str) -> bool:
    builtins = {
        "print",
        "len",
        "str",
        "int",
        "dict",
        "list",
        "set",
        "tuple",
        "bool",
        "float",
        "type",
        "open",
        "range",
        "zip",
        "map",
        "filter",
        "sorted",
        "reversed",
        "enumerate",
        "isinstance",
        "hasattr",
        "getattr",
        "setattr",
        "staticmethod",
        "classmethod",
        "property",
        "super",
        "object",
        "Exception",
        "ValueError",
        "TypeError",
        "KeyError",
        "IndexError",
        "AttributeError",
        "ImportError",
        "RuntimeError",
        "OSError",
        "IOError",
        "StopIteration",
        "True",
        "False",
        "None",
    }
    return name in builtins


def main() -> int:
    args = sys.argv[1:]

    if "--version" in args or "-V" in args:
        print(f"ghost.py {VERSION}")
        return 0

    if "-h" in args or "--help" in args:
        print(__doc__.strip())
        return 0

    root = os.getcwd()
    use_json = "--json" in args
    min_uses = 1
    lang = "all"

    for a in args:
        if a.startswith("--root="):
            root = a.split("=", 1)[1]
        elif a == "--root":
            idx = args.index(a) + 1
            if idx < len(args):
                root = args[idx]
        elif a.startswith("--min-uses"):
            val = (
                a.split("=", 1)[1] if "=" in a else (args[args.index(a) + 1] if args.index(a) + 1 < len(args) else "1")
            )
            try:
                min_uses = int(val)
            except ValueError:
                pass
        elif a == "--lang":
            idx = args.index(a) + 1
            if idx < len(args):
                lang = args[idx]
        elif a.startswith("--lang="):
            lang = a.split("=", 1)[1]

    if not os.path.isdir(root):
        print(f"Directory not found: {root}", file=sys.stderr)
        return 1

    exts_map: dict[str, set[str]] = {
        "all": PY_SOURCE_EXTS | TS_SOURCE_EXTS,
        "py": PY_SOURCE_EXTS,
        "python": PY_SOURCE_EXTS,
        "ts": TS_SOURCE_EXTS,
        "js": TS_SOURCE_EXTS,
        "typescript": TS_SOURCE_EXTS,
    }
    exts = exts_map.get(lang, PY_SOURCE_EXTS)
    files = _walk(root, exts)

    all_unused: list[dict[str, Any]] = []

    for fp in files:
        if fp.endswith(".py"):
            results = _unused_py(fp, min_uses)
        else:
            results = _unused_ts(fp, min_uses)
        for r in results:
            r_name = r["name"]
            if _filter_builtins(r_name):
                continue
            pr = os.path.relpath(r["file"], root)
            r["file"] = pr
            all_unused.append(r)

    all_unused.sort(key=lambda x: (x["file"], x["name"]))

    if use_json:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "total": len(all_unused),
                    "min_uses": min_uses,
                    "unused": all_unused,
                },
                indent=2,
            )
        )
    else:
        if all_unused:
            by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for u in all_unused:
                by_file[u["file"]].append(u)
            print("ghost: Dead Code Found 👻")
            print()
            for fp, items in sorted(by_file.items()):
                print(f"  {fp}:")
                for item in items:
                    kind_icon = "🧊" if item["kind"] == "class" else "👻"
                    print(f"    {kind_icon} {item['name']} ({item['kind']}, refs: {item['references']})")
            print()
            print(f"  Total: {len(all_unused)} unused symbols in {len(by_file)} files")
        else:
            print("ghost: No dead code found ✨")

    return 0


if __name__ == "__main__":
    sys.exit(main())
