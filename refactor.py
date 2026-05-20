#!/usr/bin/env python3
"""refactor — AST-based symbol renaming (safer than word-boundary).

Usage:
  refactor <old_name> <new_name>              Rename symbol in all Python files
  refactor <old_name> <new_name> --dry-run    Preview only, no changes
  refactor <old_name> <new_name> --file <f>   Only in specific file
  refactor <old_name> <new_name> --json       Machine-readable output

Uses Python AST to find exact symbol references (not substring matches).
Safer than word-boundary rename: no false positives on partial matches.
"""
import ast
import json
import os
import re
import sys

VERSION = "0.1.0"

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, OSError):
    pass


PY_SOURCE_EXT = {'.py', '.pyi', '.pyx'}
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env'}
SKIP_FILES = {'.gitignore', '.gitattributes'}


def _walk_files(root: str) -> list[str]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in sorted(filenames):
            if f in SKIP_FILES:
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in PY_SOURCE_EXT:
                files.append(os.path.join(dirpath, f))
    return files


def _read_file(filepath: str) -> str | None:
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            return f.read().replace('\r\n', '\n')
    except (OSError, UnicodeDecodeError):
        return None


def _find_name_in_line(line: str, col_start: int, symbol: str) -> int | None:
    """Find symbol in line starting from col_start. Returns col_offset or None."""
    pos = line.find(symbol, col_start)
    if pos == -1:
        return None
    # Verify word boundary before
    if pos > 0 and (line[pos - 1].isalnum() or line[pos - 1] == '_'):
        return None
    # Verify word boundary after
    end = pos + len(symbol)
    if end < len(line) and (line[end].isalnum() or line[end] == '_'):
        return None
    return pos


def _find_ast_references(tree: ast.AST, symbol: str, source_lines: list[str]) -> list[dict]:
    """Find all AST nodes matching the symbol, using source text for exact positions."""
    refs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == symbol:
            refs.append({
                'lineno': node.lineno,
                'col_offset': node.col_offset,
                'end_col_offset': node.end_col_offset,
                'kind': 'definition' if isinstance(node.ctx, ast.Store) else 'reference',
            })
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                line = source_lines[node.lineno - 1] if node.lineno <= len(source_lines) else ''
                col = _find_name_in_line(line, node.col_offset, symbol)
                if col is not None:
                    refs.append({
                        'lineno': node.lineno,
                        'col_offset': col,
                        'end_col_offset': col + len(symbol),
                        'kind': 'definition',
                    })
        if isinstance(node, ast.alias):
            parts = node.name.split('.')
            local_name = node.asname or parts[-1]
            lineno = getattr(node, 'lineno', 1)
            line = source_lines[lineno - 1] if lineno <= len(source_lines) else ''
            if local_name == symbol:
                col = _find_name_in_line(line, 0, symbol)
                if col is not None:
                    refs.append({
                        'lineno': lineno,
                        'col_offset': col,
                        'end_col_offset': col + len(symbol),
                        'kind': 'definition',
                    })
    return refs


def _find_refs_in_file(filepath: str, symbol: str) -> tuple[str | None, list[dict]]:
    content = _read_file(filepath)
    if content is None:
        return None, []
    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError:
        return content, []
    source_lines = content.split('\n')
    refs = _find_ast_references(tree, symbol, source_lines)
    return content, refs


def _apply_rename(content: str, refs: list[dict], old_name: str, new_name: str) -> str:
    """Apply renames in reverse line order to preserve positions."""
    lines = content.split('\n')
    by_line: dict[int, list[dict]] = {}
    for r in refs:
        by_line.setdefault(r['lineno'], []).append(r)

    old_len = len(old_name)
    for line_no in sorted(by_line.keys(), reverse=True):
        refs_on_line = sorted(by_line[line_no], key=lambda x: x['col_offset'], reverse=True)
        line = lines[line_no - 1]
        for r in refs_on_line:
            start = r['col_offset']
            end = r.get('end_col_offset', start + old_len)
            if end <= start:
                end = start + old_len
            span = end - start
            line = line[:start] + new_name + line[start + span:]
        lines[line_no - 1] = line

    return '\n'.join(lines)


def format_results(occurs: list[dict], root: str) -> str:
    lines_out = []
    for item in occurs:
        kind = item['kind']
        path = os.path.relpath(item['file'], root) if root else item['file']
        lines_out.append(f"  {path}:{item['lineno']}:{item['col_offset']}  {kind}")
    return '\n'.join(lines_out)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('--help', '-h'):
        print(__doc__.strip())
        return 0 if args and args[0] in ('--help', '-h') else 1

    if args[0] == '--version':
        print(VERSION)
        return 0

    root = os.getcwd()
    dry_run = False
    use_json = False
    single_file = None
    old_name = None
    new_name = None

    raw = list(args)
    i = 0
    while i < len(raw):
        a = raw[i]
        if a == '--dry-run':
            dry_run = True; i += 1
        elif a == '--json':
            use_json = True; i += 1
        elif a == '--file' and i + 1 < len(raw):
            single_file = raw[i + 1]; i += 2
        elif a == '--root' and i + 1 < len(raw):
            root = raw[i + 1]; i += 2
        elif a.startswith('--root='):
            root = a.split('=', 1)[1]; i += 1
        elif a.startswith('-'):
            print(f"Unknown flag: {a}", file=sys.stderr); return 1
        elif old_name is None:
            old_name = a; i += 1
        elif new_name is None:
            new_name = a; i += 1
        else:
            print(f"Unexpected argument: {a}", file=sys.stderr); return 1

    if not old_name or not new_name:
        print("Usage: refactor <old_name> <new_name> [--dry-run] [--file <path>]", file=sys.stderr)
        return 1

    if old_name == new_name:
        print("Old and new names are identical", file=sys.stderr)
        return 1

    if not os.path.isdir(root) and not os.path.isfile(root):
        print(f"Path not found: {root}", file=sys.stderr)
        return 1

    if single_file:
        if not os.path.exists(single_file):
            print(f"File not found: {single_file}", file=sys.stderr)
            return 1
        files = [single_file]
    else:
        files = _walk_files(root)

    if not files:
        print("No Python files found", file=sys.stderr)
        return 1

    all_occurs = []
    renamed_files = 0
    changed_files = []

    for fp in files:
        content, refs = _find_refs_in_file(fp, old_name)
        if content is None:
            continue
        if not refs:
            continue

        relpath = os.path.relpath(fp, root) if os.path.isdir(root) else fp
        for r in refs:
            r['file'] = fp
            all_occurs.append(r)

        if not dry_run:
            new_content = _apply_rename(content, refs, old_name, new_name)
            if new_content != content:
                try:
                    with open(fp, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    renamed_files += 1
                    changed_files.append(relpath)
                except OSError as e:
                    print(f"Error writing {relpath}: {e}", file=sys.stderr)
                    return 1

    if use_json:
        result = {
            'old_name': old_name,
            'new_name': new_name,
            'dry_run': dry_run,
            'occurrences': len(all_occurs),
            'files_changed': len(changed_files) if not dry_run else 0,
            'files': changed_files if not dry_run else list(set(o['file'] for o in all_occurs)),
            'details': [
                {
                    'file': os.path.relpath(o['file'], root),
                    'line': o['lineno'],
                    'col': o['col_offset'],
                    'kind': o['kind'],
                }
                for o in all_occurs
            ],
        }
        print(json.dumps(result, indent=2))
    else:
        mode = "dry-run" if dry_run else "renamed"
        file_count = len(set(o['file'] for o in all_occurs))
        print(f"{mode} `{old_name}` -> `{new_name}` ({len(all_occurs)} occurrences in {file_count} files):")
        print()
        # Group by file
        by_file: dict[str, list[dict]] = {}
        for o in all_occurs:
            by_file.setdefault(o['file'], []).append(o)
        for fp in sorted(by_file.keys()):
            relpath = os.path.relpath(fp, root) if os.path.isdir(root) else fp
            refs_list = by_file[fp]
            print(f"  {relpath}:")
            for r in refs_list:
                print(f"    {r['lineno']}:{r['col_offset']}  {r['kind']} `{old_name}` -> `{new_name}`")
            print()

        if not dry_run:
            print(f"Updated {renamed_files} file(s)")
        else:
            print("(dry-run — no changes made)")

    return 0 if all_occurs else 1


if __name__ == '__main__':
    sys.exit(main())
