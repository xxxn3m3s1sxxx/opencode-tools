#!/usr/bin/env python3
"""search — grep wrapper with rich output formatting.

Usage:
  search <pattern>                    Search in current directory
  search <pattern> <path>            Search in specific path
  search <pattern> --include *.py    Only Python files
  search <pattern> --context 3       Show 3 lines of context
  search <pattern> --json            JSON output (for plugin)

Examples:
  search def main                    Find all Python main function defs
  search "from .* import" --include *.py
  search "TODO|FIXME" --context 2
"""
import json
import os
import re
import subprocess
import sys

VERSION = "0.1.0"
MAX_FILE_SIZE = 50 * 1024 * 1024  # skip files > 50MB

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass


def _has_rg() -> bool:
    try:
        r = subprocess.run(['rg', '--version'], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _rg_search(pattern: str, path: str, include: str | None, context: int) -> list[dict]:
    cmd = ['rg', '-n', '--no-heading']
    if include:
        cmd.extend(['--glob', include])
    if context:
        cmd.extend(['-C', str(context)])
    cmd.append(pattern)
    cmd.append(path)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        if r.returncode not in (0, 1):
            return []
        return _parse_rg_output(r.stdout, context)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def _parse_rg_output(output: str, context: int) -> list[dict]:
    results = []
    current_group = None
    current_lines = []
    current_lnum = 0
    current_file = ""

    for line in output.rstrip('\n').split('\n'):
        if not line.strip():
            if current_group is not None:
                results.append(current_group)
                current_group = None
                current_lines = []
            continue
        m = re.match(r'^(.+?):(\d+):(.+)$', line)
        if m:
            if current_group is not None:
                results.append(current_group)
            current_file = m.group(1)
            current_lnum = int(m.group(2))
            content = m.group(3)
            current_group = {
                'file': current_file,
                'line': current_lnum,
                'match': content,
                'context_before': [],
                'context_after': [],
                'is_context': False,
            }
            current_lines = [(current_lnum, content, False)]
        elif current_group is not None:
            cm = re.match(r'^(\d+)?[-]?(.+)$', line)
            if cm:
                current_group.setdefault('context_after', []).append(cm.group(2).strip())

    if current_group is not None:
        results.append(current_group)
    return results


def _py_search(pattern: str, path: str, include: str | None, context: int) -> list[dict]:
    results = []
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        print(f"Invalid regex: {e}", file=sys.stderr)
        return []

    path = os.path.abspath(path)
    for root, _dirs, files in os.walk(path):
        # Skip .git, __pycache__, node_modules
        if '.git' in root or '__pycache__' in root or 'node_modules' in root:
            continue
        for f in sorted(files):
            fpath = os.path.join(root, f)
            if include and not _match_glob(f, include):
                continue
            try:
                sz = os.path.getsize(fpath)
                if sz > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                    lines = fh.readlines()
            except (OSError, UnicodeDecodeError):
                continue
            relpath = os.path.relpath(fpath, os.path.dirname(path)) if os.path.isdir(path) else fpath
            for i, line in enumerate(lines, 1):
                if compiled.search(line.rstrip('\n')):
                    entry = {
                        'file': relpath if os.path.isdir(path) else fpath,
                        'line': i,
                        'match': line.rstrip('\n'),
                        'context_before': [lines[j-1].rstrip('\n') for j in range(max(1, i-context), i)],
                        'context_after': [lines[j-1].rstrip('\n') for j in range(i+1, min(len(lines)+1, i+context+1))],
                        'is_context': False,
                    }
                    results.append(entry)
    return results


def _match_glob(filename: str, pattern: str) -> bool:
    if '*' in pattern:
        parts = pattern.split('*')
        return all(p in filename for p in parts if p)
    return filename.endswith(pattern.lstrip('*'))


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('--help', '-h'):
        print(__doc__.strip())
        return 0 if args and args[0] in ('--help', '-h') else 1

    if args[0] == '--version':
        print(f"search.py {VERSION}")
        return 0

    use_json = False
    context = 0
    include = None
    path = os.getcwd()
    pattern = ""

    raw = list(args)
    i = 0
    while i < len(raw):
        a = raw[i]
        if a == '--json':
            use_json = True; i += 1
        elif a.startswith('--context='):
            context = int(a.split('=', 1)[1]); i += 1
        elif a == '--context' and i + 1 < len(raw):
            context = int(raw[i + 1]); i += 2
        elif a.startswith('--include='):
            include = a.split('=', 1)[1]; i += 1
        elif a == '--include' and i + 1 < len(raw):
            include = raw[i + 1]; i += 2
        elif a.startswith('-'):
            print(f"Unknown flag: {a}", file=sys.stderr); return 1
        elif not pattern:
            pattern = a; i += 1
        else:
            path = a; i += 1

    if not pattern:
        print("No search pattern provided", file=sys.stderr)
        return 1

    if not os.path.exists(path):
        print(f"Path not found: {path}", file=sys.stderr)
        return 1

    if _has_rg():
        results = _rg_search(pattern, path, include, context)
    else:
        results = _py_search(pattern, path, include, context)

    if use_json:
        print(json.dumps({'pattern': pattern, 'path': path, 'results': results, 'count': len(results)}, indent=2))
    else:
        if not results:
            print(f"No matches found for `{pattern}`")
            return 1
        print(f"{len(results)} match(es) for `{pattern}`:")
        print()
        for r in results:
            ctx_before = r.get('context_before', [])
            ctx_after = r.get('context_after', [])
            for cb in ctx_before:
                if cb.strip():
                    print(f"  {r['file']}:  {cb}")
            print(f"  {r['file']}:{r['line']}  {r['match']}")
            for ca in ctx_after:
                if ca.strip():
                    print(f"  {r['file']}:  {ca}")
            print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
