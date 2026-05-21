#!/usr/bin/env python3
"""graph — file-level dependency analyzer. Show imports, dependents, and cycles.

Usage:
  graph <file>                  Show dependencies of a file
  graph <file> --in             Show what imports this file (dependents)
  graph <file> --out            Show what this file imports (dependencies)
  graph <file> --tree           Show dependency tree (depth-first)
  graph --circular              Find circular dependencies in project
  graph --stats                 Project-wide dependency statistics
  graph --json                  JSON output (for plugin)

Examples:
  graph src/main.py             Deps of main.py
  graph src/utils.py --tree     Full dependency tree
  graph --circular              Find cycles
"""
import json
import os
import re
import sys
from collections import defaultdict

VERSION = "0.1.0"

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass

EXCLUDE_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv', '.env',
    'build', 'dist', '.mypy_cache', '.pytest_cache', '.ruff_cache',
    '.eggs', '.idea', '.vscode', 'target', '.next', '.nuxt',
}

SOURCE_EXTS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs',
    '.cpp', '.c', '.h', '.hpp', '.cc', '.cxx', '.hxx', '.hh',
}


def _walk_files(root: str) -> list[str]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith('.')]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in SOURCE_EXTS:
                files.append(os.path.join(dirpath, fn))
    return sorted(files)


def _read_file(filepath: str) -> str | None:
    try:
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            return f.read().replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError):
        return None


# ─── Import Parsers ──────────────────────────────────────────────────────

PY_IMPORT_RE = re.compile(
    r'^\s*(?:from\s+([.\w]+)\s+)?import\s+(.+)$',
    re.MULTILINE,
)
PY_FROM_RE = re.compile(r'from\s+([.\w]+)\s+import')


def _parse_py_imports(source: str) -> list[str]:
    mods = set()
    for m in PY_IMPORT_RE.finditer(source):
        if m.group(1):
            mods.add(m.group(1))
        for name in m.group(2).split(','):
            name = name.strip().split()[0]
            if name:
                mods.add(name.split('.')[0])
    return sorted(mods)


TS_IMPORT_RE = re.compile(
    r"""import\s+(?:type\s+)?(?:(?:\{[^}]*\}|\w+(?:\s*,\s*(?:\{[^}]*\}|\w+))?|\*\s+as\s+\w+)\s+from\s+)?['"]([^'"]+)['"]""",
)
TS_REQUIRE_RE = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")
TS_EXPORT_RE = re.compile(r"""export\s+(?:type\s+)?(?:\{[^}]*\}|(?:\w+\s+)*\w+)\s+from\s+['"]([^'"]+)['"]""")


def _parse_ts_imports(source: str) -> list[str]:
    mods = set()
    for m in TS_IMPORT_RE.finditer(source):
        mods.add(m.group(1))
    for m in TS_REQUIRE_RE.finditer(source):
        mods.add(m.group(1))
    for m in TS_EXPORT_RE.finditer(source):
        mods.add(m.group(1))
    return sorted(mods)


CPP_INCLUDE_RE = re.compile(r'#include\s+["<]([^">]+)[">]')


def _parse_cpp_imports(source: str) -> list[str]:
    return sorted(set(m.group(1) for m in CPP_INCLUDE_RE.finditer(source)))


def _resolve_import_path(imp: str, filepath: str, root: str) -> str | None:
    base = os.path.dirname(filepath)

    # Prioritize same extension as importing file
    caller_ext = os.path.splitext(filepath)[1].lower()
    exts_ordered = [caller_ext] + sorted(e for e in SOURCE_EXTS if e != caller_ext)

    if imp.startswith('.'):
        rel = os.path.normpath(os.path.join(base, imp))
        for ext in exts_ordered:
            p = rel + ext
            if os.path.exists(p):
                return os.path.relpath(p, root)
        for ext in exts_ordered:
            p = os.path.join(rel, '__init__' + ext)
            if os.path.exists(p):
                return os.path.relpath(p, root)
        return None

    candidates = []
    parts = imp.split('/')
    for i in range(len(parts), 0, -1):
        prefix = '/'.join(parts[:i])
        suffix = '/'.join(parts[i:])

        for ext in exts_ordered:
            candidates.append(os.path.join(root, prefix + ext))
            if suffix:
                candidates.append(os.path.join(root, prefix, suffix + ext))
            candidates.append(os.path.join(root, prefix, '__init__' + ext))
            if suffix:
                candidates.append(os.path.join(root, prefix, suffix, '__init__' + ext))

    for c in candidates:
        if os.path.exists(c):
            return os.path.relpath(c, root)
    return imp


def _parse_imports(source: str, ext: str) -> list[str]:
    if ext == '.py':
        return _parse_py_imports(source)
    elif ext in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'):
        return _parse_ts_imports(source)
    elif ext in ('.cpp', '.c', '.h', '.hpp', '.cc', '.cxx', '.hxx', '.hh'):
        return _parse_cpp_imports(source)
    return []


# ─── Graph Building ──────────────────────────────────────────────────────


def build_graph(root: str) -> dict[str, dict[str, list[str]]]:
    files = _walk_files(root)
    node_map: dict[str, str] = {}
    edges: dict[str, list[str]] = defaultdict(list)
    rev_edges: dict[str, list[str]] = defaultdict(list)

    for fp in files:
        rel = os.path.relpath(fp, root)
        node_map[rel] = rel

    for fp in files:
        rel = os.path.relpath(fp, root)
        ext = os.path.splitext(fp)[1].lower()
        content = _read_file(fp)
        if content is None:
            continue
        raw_imports = _parse_imports(content, ext)
        for imp in raw_imports:
            resolved = _resolve_import_path(imp, fp, root)
            if resolved and resolved in node_map:
                edges[rel].append(resolved)
                rev_edges[resolved].append(rel)

    return {
        'files': sorted(node_map.keys()),
        'edges': dict(edges),
        'reverse': dict(rev_edges),
    }


def find_deps(graph: dict, file_rel: str) -> dict:
    edges = graph['edges']
    rev = graph['reverse']
    return {
        'file': file_rel,
        'imports': sorted(edges.get(file_rel, [])),
        'imported_by': sorted(rev.get(file_rel, [])),
    }


def find_tree(graph: dict, file_rel: str, max_depth: int = 5) -> list:
    edges = graph['edges']
    visited = set()
    result = []

    def _walk(node: str, depth: int, chain: list[str]):
        if depth > max_depth:
            return
        if node in visited:
            result.append({'file': node, 'depth': depth, 'cycle': True, 'chain': chain + [node]})
            return
        visited.add(node)
        deps = edges.get(node, [])
        result.append({'file': node, 'depth': depth, 'deps': deps})
        for d in deps:
            _walk(d, depth + 1, chain + [node])

    _walk(file_rel, 0, [])
    return result


def find_cycles(graph: dict) -> list[list[str]]:
    edges = graph['edges']
    all_files = graph['files']
    cycles = []
    visited = set()
    path_stack = []

    def _dfs(node: str, path: list[str]):
        visited.add(node)
        path_stack.append(node)
        for neighbor in edges.get(node, []):
            if neighbor in path_stack:
                cycle = path_stack[path_stack.index(neighbor):]
                if len(cycle) > 1:
                    cycles.append(cycle)
            elif neighbor not in visited:
                _dfs(neighbor, path)
        path_stack.pop()

    for f in all_files:
        if f not in visited:
            _dfs(f, [])
    return cycles


def stats(graph: dict) -> dict:
    edges = graph['edges']
    rev = graph['reverse']
    n_files = len(graph['files'])
    n_edges = sum(len(v) for v in edges.values())

    classes = {'leaf': 0, 'root': 0, 'hub': 0, 'cluster': 0}
    for f in graph['files']:
        out_deg = len(edges.get(f, []))
        in_deg = len(rev.get(f, []))
        if out_deg == 0 and in_deg == 0:
            pass
        elif out_deg == 0:
            classes['leaf'] += 1
        elif in_deg == 0:
            classes['root'] += 1
        elif out_deg >= 5 or in_deg >= 5:
            classes['hub'] += 1
        else:
            classes['cluster'] += 1

    cycles = find_cycles(graph)
    return {
        'total_files': n_files,
        'total_edges': n_edges,
        'average_out_degree': round(n_edges / max(n_files, 1), 2),
        'leaf_files': classes['leaf'],
        'root_files': classes['root'],
        'hub_files': classes['hub'],
        'cluster_files': classes['cluster'],
        'cycles': len(cycles),
    }


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('--help', '-h'):
        print(__doc__.strip())
        return 0 if args and args[0] in ('--help', '-h') else 1

    if args[0] == '--version':
        print(f"graph.py {VERSION}")
        return 0

    root = os.getcwd()
    use_json = False
    show_in = show_out = show_tree = show_circular = show_stats = False
    file_arg = None

    raw = list(args)
    i = 0
    while i < len(raw):
        a = raw[i]
        if a == '--json':
            use_json = True; i += 1
        elif a == '--in':
            show_in = True; i += 1
        elif a == '--out':
            show_out = True; i += 1
        elif a == '--tree':
            show_tree = True; i += 1
        elif a == '--circular':
            show_circular = True; i += 1
        elif a == '--stats':
            show_stats = True; i += 1
        elif a == '--root' and i + 1 < len(raw):
            root = raw[i + 1]; i += 2
        elif a.startswith('--root='):
            root = a.split('=', 1)[1]; i += 1
        elif a.startswith('--'):
            print(f"Unknown flag: {a}", file=sys.stderr); return 1
        elif os.path.isdir(a):
            root = a; i += 1
        else:
            file_arg = a; i += 1

    if not os.path.isdir(root):
        print(f"Root directory not found: {root}", file=sys.stderr)
        return 1

    graph = build_graph(root)

    if show_circular:
        cycles = find_cycles(graph)
        if use_json:
            print(json.dumps({'cycles': cycles}, indent=2))
        else:
            print("Circular dependencies:")
            if not cycles:
                print("  (none found)")
            else:
                for cyc in cycles:
                    print(f"  {' -> '.join(cyc + [cyc[0]])}")
        return 0

    if show_stats:
        s = stats(graph)
        if use_json:
            print(json.dumps(s, indent=2))
        else:
            print("Project dependency statistics:")
            print(f"  Files:               {s['total_files']}")
            print(f"  Edges:               {s['total_edges']}")
            print(f"  Average out-degree:  {s['average_out_degree']}")
            print(f"  Root files (no deps): {s['root_files']}")
            print(f"  Leaf files (no deps): {s['leaf_files']}")
            print(f"  Hub files:            {s['hub_files']}")
            print(f"  Cluster files:        {s['cluster_files']}")
            print(f"  Cycles:               {s['cycles']}")
        return 0

    if not file_arg:
        # default: show stats
        s = stats(graph)
        if use_json:
            print(json.dumps(s, indent=2))
        else:
            print("Project dependency statistics:")
            print(f"  Files:               {s['total_files']}")
            print(f"  Edges:               {s['total_edges']}")
            print(f"  Average out-degree:  {s['average_out_degree']}")
            print(f"  Root files:          {s['root_files']}")
            print(f"  Leaf files:          {s['leaf_files']}")
            print(f"  Hub files:           {s['hub_files']}")
            print(f"  Cycles:              {s['cycles']}")
        return 0

    # Resolve file arg to relative path
    filepath = file_arg
    if not os.path.exists(filepath):
        filepath = os.path.join(root, file_arg)
    if not os.path.exists(filepath):
        print(f"File not found: {file_arg}", file=sys.stderr)
        return 1
    file_rel = os.path.relpath(os.path.abspath(filepath), root)
    edges = graph['edges']
    rev = graph['reverse']
    imports = sorted(edges.get(file_rel, []))
    imported_by = sorted(rev.get(file_rel, []))

    if show_tree:
        tree = find_tree(graph, file_rel)
        if use_json:
            print(json.dumps({'file': file_rel, 'tree': tree}, indent=2))
        else:
            print(f"Dependency tree for {file_rel}:")
            seen = set()
            for entry in tree:
                indent = "  " * entry['depth']
                marker = " [CYCLE]" if entry.get('cycle') else ""
                print(f"{indent}{entry['file']}{marker}")
        return 0

    if show_in and not show_out:
        # only in
        result = {'file': file_rel, 'imported_by': imported_by}
        if use_json:
            print(json.dumps(result, indent=2))
        else:
            print(f"`{file_rel}` is imported by:")
            for f in imported_by or ['(none)']:
                print(f"  {f}")
        return 0

    if show_out and not show_in:
        # only out
        result = {'file': file_rel, 'imports': imports}
        if use_json:
            print(json.dumps(result, indent=2))
        else:
            print(f"`{file_rel}` imports:")
            for f in imports or ['(none)']:
                print(f"  {f}")
        return 0

    # Default: show both
    result = {'file': file_rel, 'imports': imports, 'imported_by': imported_by}
    if use_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"`{file_rel}`:")
        print(f"  imports ({len(imports)}):")
        for f in imports or ['(none)']:
            print(f"    {f}")
        print(f"  imported by ({len(imported_by)}):")
        for f in imported_by or ['(none)']:
            print(f"    {f}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
