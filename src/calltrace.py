#!/usr/bin/env python3
"""trace — recursive call chain analyzer. Follow execution paths through the codebase.

Commands:
  trace <symbol> [-d N]       Show call chain N levels deep (default: 2)
  trace <symbol> --up         Show callers only (who calls this)
  trace <symbol> --down       Show callees only (what this calls)
  trace <file>:<line>         Infer symbol from context

Options:
  -d, --depth N              Max recursion depth (default: 2)
  --up                        Show callers (reverse chain)
  --down                      Show callees (forward chain)
  --viz                       ASCII tree visualization
  --json                      JSON output (for plugin)
  --root DIR                  Project root (auto-detect)

Exit code: 0 = found, 1 = symbol not found
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys

from typing import Any

from common import VERSION, CPP_SOURCE_EXTS, reconfigure_stdout_stderr

reconfigure_stdout_stderr()

ImpactAnalyzer: Any = None
try:
    from impact import ImpactAnalyzer as _IA

    ImpactAnalyzer = _IA
    from impact import _is_python as _is_python_fn, _grep_find_references as _grep_refs_fn

    _is_python = _is_python_fn
    _grep_find_references = _grep_refs_fn
except ImportError:
    # Fallback: import from explicit path (sibling file)
    _impact_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "impact.py")
    if os.path.exists(_impact_path):
        import importlib.util as _util

        _spec = _util.spec_from_file_location("impact", _impact_path)
        if _spec and _spec.loader:
            _mod = _util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            ImpactAnalyzer = _mod.ImpactAnalyzer
            _is_python = _mod._is_python
            _grep_find_references = _mod._grep_find_references


def _read_file(filepath: str) -> str:
    """Read file, stripping BOM and normalizing CRLF to LF."""
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read().replace("\r\n", "\n")


def _is_cpp(filepath: str) -> bool:
    _, ext = os.path.splitext(filepath)
    return ext.lower() in CPP_SOURCE_EXTS


_CPP_FUNC_PAT = re.compile(r"(?:[\w:<>*&]+\s+)?(\w+)\s*\([^;{]*\)\s*(?:const|override)?\s*\{")
_CPP_ENCLOSING_CACHE: dict[str, dict[int, str]] = {}


def _find_enclosing_function_cpp(filepath: str, line_no: int) -> str | None:
    """Find the C++ function enclosing a given line using brace matching."""
    if filepath in _CPP_ENCLOSING_CACHE:
        return _CPP_ENCLOSING_CACHE[filepath].get(line_no)

    try:
        source = _read_file(filepath)
    except (OSError, UnicodeDecodeError):
        return None
    if not source:
        return None

    lines = source.split("\n")
    total = len(source)
    line_info: dict[int, str] = {}

    for m in _CPP_FUNC_PAT.finditer(source):
        name = m.group(1)
        brace_pos = m.end() - 1
        start_line = source[:brace_pos].count("\n") + 1

        depth = 1
        pos = brace_pos + 1
        while pos < total and depth > 0:
            c = source[pos]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            pos += 1

        end_line = source[:pos].count("\n") if depth == 0 else len(lines)
        for ln in range(start_line, end_line + 1):
            if ln not in line_info:
                line_info[ln] = name

    _CPP_ENCLOSING_CACHE[filepath] = line_info
    return line_info.get(line_no)


_ENCLOSING_CACHE: dict[str, dict[int, str]] = {}


def _find_enclosing_function(filepath: str, line_no: int) -> str | None:
    """Find the name of the function enclosing a given line (Python only)."""
    if filepath in _ENCLOSING_CACHE:
        tree_info = _ENCLOSING_CACHE[filepath]
    else:
        try:
            source = _read_file(filepath)
            tree = ast.parse(source, filepath)
        except (SyntaxError, OSError):
            return None
        # Precompute: for each line, the innermost enclosing function
        tree_info = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.lineno is not None and node.end_lineno is not None:
                    for ln in range(node.lineno, node.end_lineno + 1):
                        tree_info[ln] = node.name
            elif isinstance(node, ast.ClassDef):
                if node.lineno is not None and node.end_lineno is not None:
                    for ln in range(node.lineno, node.end_lineno + 1):
                        if ln not in tree_info:
                            tree_info[ln] = node.name
        _ENCLOSING_CACHE[filepath] = tree_info
    return tree_info.get(line_no)


def _grep_occurrences(filepath: str, symbol: str) -> list[dict[str, Any]]:
    """Find all occurrences of symbol using word-boundary grep."""
    matches: list[dict[str, Any]] = []
    try:
        source = _read_file(filepath)
        lines = source.split("\n") if source else []
    except (OSError, UnicodeDecodeError):
        return matches
    pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
    for i, line in enumerate(lines, 1):
        if pattern.search(line):
            matches.append(
                {
                    "type": "occurrence",
                    "file": filepath,
                    "line": i,
                    "context": line[:120].strip(),
                }
            )
    return matches


def _build_index(files: list[str]) -> dict[str, list[dict[str, Any]]]:
    """Build inverted index: symbol -> [(file, line, context)] from source files."""
    idx: dict[str, list[dict[str, Any]]] = {}
    for fp in files:
        try:
            source = _read_file(fp)
            if not source:
                continue
            lines = source.split("\n")
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(lines, 1):
            for m in re.finditer(r"\b(\w+)\b", line):
                sym = m.group(1)
                if sym not in idx:
                    idx[sym] = []
                idx[sym].append(
                    {
                        "file": fp,
                        "line": i,
                        "context": line[:120].strip(),
                    }
                )
    return idx


def _find_callers_from_index(
    analyzer: Any,
    symbol: str,
    depth: int,
    lang: str,
    idx: dict[str, list[dict[str, Any]]],
    visited: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Find who calls a given symbol, using pre-built inverted index."""
    if visited is None:
        visited = set()
    if depth <= 0 or symbol in visited:
        return []

    visited.add(symbol)
    results = []

    occs = idx.get(symbol, [])
    for occ in occs:
        fp = occ["file"]
        if lang != "all":
            ext = os.path.splitext(fp)[1].lower()
            if lang == "py" and ext != ".py":
                continue
            if lang == "cpp" and ext not in (".cpp", ".c", ".h", ".hpp", ".cc", ".cxx", ".hxx", ".hh"):
                continue
            if lang == "ts" and ext not in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
                continue
        caller = None
        if _is_python(fp):
            caller = _find_enclosing_function(fp, occ["line"])
        elif _is_cpp(fp):
            caller = _find_enclosing_function_cpp(fp, occ["line"])
        if caller != symbol and caller not in visited:
            name = caller or ""
            results.append(
                {
                    "type": "caller",
                    "caller": name,
                    "callee": symbol,
                    "file": occ["file"],
                    "line": occ["line"],
                    "context": occ.get("context", ""),
                }
            )
            if depth > 1 and name:
                deeper = _find_callers_from_index(analyzer, name, depth - 1, lang, idx, visited)
                results.extend(deeper)

    return results


def _find_callers(
    analyzer: Any, symbol: str, depth: int, lang: str, visited: set[str] | None = None, files: list[str] | None = None
) -> list[dict[str, Any]]:
    """Find who calls a given symbol, recursively up to depth."""
    if visited is None:
        visited = set()
    if depth <= 0 or symbol in visited:
        return []

    # Cache file list at top-level call, pass down via recursion
    if files is None:
        files = analyzer._walk_files(lang)

    visited.add(symbol)
    results = []

    for fp in files:
        occs = _grep_occurrences(fp, symbol)
        for occ in occs:
            caller = None
            if _is_python(fp):
                caller = _find_enclosing_function(occ["file"], occ["line"])
            elif _is_cpp(fp):
                caller = _find_enclosing_function_cpp(occ["file"], occ["line"])
            if caller != symbol and caller not in visited:
                name = caller or ""
                results.append(
                    {
                        "type": "caller",
                        "caller": name,
                        "callee": symbol,
                        "file": occ["file"],
                        "line": occ["line"],
                        "context": occ.get("context", ""),
                    }
                )
                if depth > 1 and name:
                    deeper = _find_callers(analyzer, name, depth - 1, lang, visited, files)
                    results.extend(deeper)

    return results


def _find_call_chain(
    analyzer: Any,
    symbol: str,
    depth: int,
    lang: str,
    visited: set[str] | None = None,
    chain: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build call chain recursively (callees only, forward)."""
    if visited is None:
        visited = set()
    if chain is None:
        chain = []
    if depth <= 0 or symbol in visited:
        return chain

    visited.add(symbol)

    callees = analyzer.find_callees(symbol, lang)
    if callees:
        chain.append(
            {
                "symbol": symbol,
                "callees": sorted(set(c["name"] for c in callees)),
            }
        )
        for callee in set(c["name"] for c in callees):
            if callee not in visited:
                _find_call_chain(analyzer, callee, depth - 1, lang, visited, chain)

    return chain


def _tree_char(i: int, total: int) -> str:
    return "└── " if i == total - 1 else "├── "


def format_pretty(
    symbol: str, callers: list[dict[str, Any]], chain: list[dict[str, Any]], root: str | os.PathLike[str], depth: int
) -> str:
    lines = []
    lines.append(f"trace: `{symbol}`")
    lines.append(f"  depth: {depth}")
    lines.append("")

    if callers:
        seen = set()
        lines.append(f"  [callers] {len(callers)}")
        for c in callers:
            key = (c["file"], c["line"])
            if key not in seen:
                seen.add(key)
                rel = os.path.relpath(c["file"], root)
                caller_label = c["caller"] if c["caller"] else "(module)"
                ctx = c.get("context", "")[:80]
                tc = f"  -- {ctx}" if ctx else ""
                lines.append(f"    {caller_label:<25s}  {rel}:{c['line']}{tc}")
        lines.append("")

    if chain:
        lines.append(f"  [chain] {symbol}")
        for level in chain:
            sym = level["symbol"]
            callees = level.get("callees", [])
            for i, callee in enumerate(callees):
                lines.append(f"    {_tree_char(i, len(callees))}{sym} -> {callee}")

    if not callers and not chain:
        lines.append("  (no call chain found)")

    return "\n".join(lines)


def format_viz(
    symbol: str, callers: list[dict[str, Any]], chain: list[dict[str, Any]], root: str | os.PathLike[str], depth: int
) -> str:
    """ASCII tree visualization of call chain."""
    lines = []
    lines.append(f"trace: `{symbol}` (viz, depth={depth})")
    lines.append("")

    if chain:
        # Build parent->children map
        children_of: dict[str, list[str]] = {}
        for level in chain:
            sym = level["symbol"]
            if sym not in children_of:
                children_of[sym] = []
            for c in level.get("callees", []):
                children_of[sym].append(c)
                if c not in children_of:
                    children_of[c] = []

        def _append_tree(node: str, prefix: str, is_last: bool, visited: set[str]) -> None:
            if node in visited:
                lines.append(f"{prefix}{'└── ' if is_last else '├── '}{node} (cycle)")
                return
            visited.add(node)
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{node}")
            kids = children_of.get(node, [])
            if kids:
                new_prefix = prefix + ("    " if is_last else "│   ")
                for i, kid in enumerate(kids):
                    _append_tree(kid, new_prefix, i == len(kids) - 1, visited)

        _append_tree(symbol, "", True, set())

    if callers:
        # Build callee->callers map
        unique: dict[str, list[dict[str, Any]]] = {}
        for c in callers:
            callee = c["callee"]
            if callee not in unique:
                unique[callee] = []
            key = (c["file"], c["line"])
            if key not in {(x["file"], x["line"]) for x in unique[callee]}:
                unique[callee].append(c)

        if chain:
            lines.append("")

        lines.append("  [callers]")
        caller_list = unique.get(symbol, [])
        for i, c in enumerate(caller_list):
            rel = os.path.relpath(c["file"], root)
            label = c["caller"] if c["caller"] else "(module)"
            lines.append(f"    {_tree_char(i, len(caller_list))}{label}  ({rel}:{c['line']})")

    if not callers and not chain:
        lines.append("  (no call chain found)")

    return "\n".join(lines)


def format_json(
    symbol: str, callers: list[dict[str, Any]], chain: list[dict[str, Any]], root: str | os.PathLike[str], depth: int
) -> str:
    return json.dumps(
        {
            "symbol": symbol,
            "project": str(root),
            "depth": depth,
            "callers": callers,
            "chain": chain,
        },
        indent=2,
    )


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 0

    if ImpactAnalyzer is None:
        print("Error: impact.py not found. trace depends on impact.py in the same directory.")
        return 1

    args = sys.argv[1:]

    if args[0] == "--version":
        print(f"calltrace.py {VERSION}")
        return 0

    use_json = "--json" in args
    use_viz = "--viz" in args
    lang = "all"
    root_dir = None
    depth = 2
    mode = "both"

    clean_args = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            i += 1
            continue
        if a == "--viz":
            i += 1
            continue
        if a == "--root" and i + 1 < len(args):
            root_dir = args[i + 1]
            i += 2
            continue
        if a.startswith("--root="):
            root_dir = a.split("=", 1)[1]
            i += 1
            continue
        if a in ("-d", "--depth") and i + 1 < len(args):
            try:
                depth = int(args[i + 1])
            except ValueError:
                print(f"Invalid --depth value: {args[i + 1]}", file=sys.stderr)
                return 1
            i += 2
            continue
        if a == "--up":
            mode = "up"
            i += 1
            continue
        if a == "--down":
            mode = "down"
            i += 1
            continue
        if a == "--py":
            lang = "py"
            i += 1
            continue
        if a == "--cpp":
            lang = "cpp"
            i += 1
            continue
        if a.startswith("--"):
            print(f"Unknown flag: {a}")
            return 1
        clean_args.append(a)
        i += 1

    if not clean_args:
        print("Usage: trace <symbol> [options]")
        return 1

    symbol_raw = clean_args[0]
    analyzer = ImpactAnalyzer(root_dir)

    # Parse file:line syntax (handle Windows C:\ paths)
    file_line_match = re.match(r"^([A-Za-z]:\\.+?):(\d+)$", symbol_raw)
    if not file_line_match:
        file_line_match = re.match(r"^([^:]+):(\d+)$", symbol_raw)
    if file_line_match and os.path.isfile(file_line_match.group(1)):
        filepath, line_str = file_line_match.group(1), file_line_match.group(2)
        try:
            line_no = int(line_str)
            inferred = analyzer.infer_symbol(filepath, line_no)
            if inferred:
                symbol = inferred
            else:
                print(f"Could not infer symbol at {filepath}:{line_no}", file=sys.stderr)
                return 1
        except ValueError:
            symbol = symbol_raw
    else:
        symbol = symbol_raw

    callers = []
    chain = []

    if mode in ("up", "both"):
        idx = _build_index(analyzer._walk_files(lang))
        callers = _find_callers_from_index(analyzer, symbol, depth, lang, idx)

    if mode in ("down", "both"):
        chain = _find_call_chain(analyzer, symbol, depth, lang)

    if use_json:
        print(format_json(symbol, callers, chain, analyzer.root, depth))
    elif use_viz:
        print(format_viz(symbol, callers, chain, analyzer.root, depth))
    else:
        print(format_pretty(symbol, callers, chain, analyzer.root, depth))

    found = bool(callers or chain)
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
