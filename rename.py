#!/usr/bin/env python3
"""rename — word-boundary symbol rename across project files.

Usage:
  rename <old_name> <new_name>              Rename symbol in all source files
  rename <old_name> <new_name> --dry-run    Preview only, no changes
  rename <old_name> <new_name> --root DIR   Project root (default: cwd)
  rename <old_name> <new_name> --lang py    Only Python files
  rename <old_name> <new_name> --json       JSON output (for plugin)

Searches all source files (.py, .ts, .js, .cpp, .c, .h, .rs, .go, .java)
within the project tree, skipping .git, node_modules, __pycache__, etc.
Uses \\b word-boundary matching for safe renames.
"""

import json
import os
import re
import sys

VERSION = "0.1.0"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".env",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".eggs",
    ".idea",
    ".vscode",
    "target",
    ".next",
    ".nuxt",
}

SOURCE_EXTS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".cc",
    ".cxx",
    ".hxx",
    ".hh",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".swift",
}


def _find_files(root: str, lang: str = "all") -> list[str]:
    """Walk project tree and collect source files."""
    files = []
    exts = SOURCE_EXTS
    if lang == "py":
        exts = {".py"}
    elif lang == "cpp":
        exts = {".cpp", ".c", ".h", ".hpp", ".cc", ".cxx", ".hxx", ".hh"}
    elif lang == "ts":
        exts = {".ts", ".tsx"}
    elif lang == "js":
        exts = {".js", ".jsx", ".mjs", ".cjs"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in exts:
                files.append(os.path.join(dirpath, fn))
    return sorted(files)


def _read_file(filepath: str) -> str | None:
    """Read file with BOM + CRLF normalization."""
    try:
        with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read().replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError):
        return None


def _find_occurrences(content: str, symbol: str) -> list[int]:
    """Find all line numbers (1-based) where symbol appears as a word."""
    pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
    lines = content.split("\n")
    result = []
    for i, line in enumerate(lines):
        if pattern.search(line):
            result.append(i + 1)
    return result


def _rename_in_content(content: str, old: str, new: str) -> str:
    """Replace all word-boundary occurrences of old with new."""
    pattern = re.compile(r"\b" + re.escape(old) + r"\b")
    return pattern.sub(new, content)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        print(__doc__.strip())
        return 0 if args and args[0] in ("--help", "-h") else 1

    if args[0] == "--version":
        print(f"rename.py {VERSION}")
        return 0

    old_name = None
    new_name = None
    root_dir = os.getcwd()
    dry_run = False
    use_json = False
    lang = "all"

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--dry-run":
            dry_run = True
            i += 1
        elif a == "--json":
            use_json = True
            i += 1
        elif a == "--root" and i + 1 < len(args):
            root_dir = args[i + 1]
            i += 2
        elif a.startswith("--root="):
            root_dir = a.split("=", 1)[1]
            i += 1
        elif a == "--lang" and i + 1 < len(args):
            lang = args[i + 1]
            i += 2
        elif a.startswith("--"):
            print(f"Unknown flag: {a}", file=sys.stderr)
            return 1
        elif old_name is None:
            old_name = a
            i += 1
        elif new_name is None:
            new_name = a
            i += 1
        else:
            print(f"Unexpected argument: {a}", file=sys.stderr)
            return 1

    if not old_name or not new_name:
        print(
            "Usage: rename <old_name> <new_name> [--dry-run] [--root DIR] [--lang py|cpp|ts|js|all] [--json]",
            file=sys.stderr,
        )
        return 1

    if old_name == new_name:
        print(f"renamed `{old_name}` -> `{new_name}`: (no change — names are identical)", file=sys.stderr)
        return 0

    if not os.path.isdir(root_dir):
        print(f"Root directory not found: {root_dir}", file=sys.stderr)
        return 1

    files = _find_files(root_dir, lang)
    results = []

    for fp in files:
        content = _read_file(fp)
        if content is None:
            continue
        occs = _find_occurrences(content, old_name)
        if not occs:
            continue
        new_content = _rename_in_content(content, old_name, new_name)
        if not dry_run:
            try:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(new_content)
            except OSError as e:
                print(f"Error writing {fp}: {e}", file=sys.stderr)
                continue
        results.append(
            {
                "file": fp,
                "occurrences": occs,
                "count": len(occs),
            }
        )

    total_occ = sum(r["count"] for r in results)

    if use_json:
        print(
            json.dumps(
                {
                    "old": old_name,
                    "new": new_name,
                    "files": results,
                    "total_occurrences": total_occ,
                    "total_files": len(results),
                    "dry_run": dry_run,
                    "root": root_dir,
                },
                indent=2,
            )
        )
    else:
        mode = " (dry-run)" if dry_run else ""
        print(f"renamed `{old_name}` -> `{new_name}`{mode}:")
        if not results:
            print("  (no occurrences found)")
            return 0
        for r in results:
            lines_str = ",".join(str(line) for line in r["occurrences"][:10])
            if len(r["occurrences"]) > 10:
                lines_str += f",...({r['count']} total)"
            rel = os.path.relpath(r["file"], root_dir)
            print(f"  {rel}:{lines_str}")
        print(f"  {total_occ} occurrences in {len(results)} files")
        if dry_run:
            print("  (no files were modified)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
