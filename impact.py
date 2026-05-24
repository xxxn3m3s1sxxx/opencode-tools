#!/usr/bin/env python3
"""impact — Change Impact Analyzer. Find definitions, references, and tests for any symbol.

Commands:
  impact def <symbol>        Find definition
  impact refs <symbol>       Find all references
  impact tests <symbol>      Find related test files
  impact graph <symbol>      Show callers + callees
  impact <file>:<line>       Infer symbol from context
  impact <symbol>            Show def + refs + tests

Options:
  --json                     JSON output (for plugin)
  --root DIR                 Project root (auto-detect)
  --lang py|cpp|ts|js|all    Filter by language
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def _read_file(filepath):
    """Read file, stripping BOM and normalizing CRLF to LF."""
    with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read().replace("\r\n", "\n")


# ─── C++ Pattern Definitions ──────────────────────────────────────────────

CPP_DEF_PATTERNS = [
    # Function: return_type func_name(args) {
    (r"(?:\w[\w:<>*&]*\s+)?(\w+)\s*\([^;{]*\)\s*(?:const|override)?\s*\{", "function"),
    # Function declaration: return_type func_name(args);
    (r"(?:\w[\w:<>*&]+\s+)(\w+)\s*\([^;{]*\)\s*(?:const|override)?\s*;", "function_decl"),
    # Variable assignment: type var = cast(...) or type var = call(...);
    (r"(?:\w[\w:<>*&]+\s+)([a-z_]\w*)\s*(?:=)", "variable"),
    # Variable declaration without init
    (r"(?:\w[\w:<>*&]+\s+)([a-z_]\w*)\s*;", "variable_decl"),
    # Method: Class::method
    (r"(\w+)\s*::\s*(\w+)\s*\(", "method"),
    # Class/struct
    (r"(?:class|struct)\s+(\w+)(?:\s*:\s*public\s+\w+)?\s*\{", "class"),
    # Macro: #define NAME
    (r"#define\s+(\w+)", "macro"),
]

# ─── TypeScript/JavaScript Pattern Definitions ─────────────────────────────

H = r"[ \t]"  # horizontal whitespace (not newline)

TS_DEF_PATTERNS = [
    # Named function / async function
    (r"(?:export" + H + r"+)?(?:async" + H + r"+)?function" + H + r"+(?:\*" + H + r"+)?(\w+)", "function"),
    # Arrow function in const/let/var: const name = (args) =>
    (
        r"(?:export"
        + H
        + r"+)?(?:const|let|var)"
        + H
        + r"+(\w+)"
        + H
        + r"*="
        + H
        + r"*(?:async"
        + H
        + r"+)?(?:\([^)]*\)|\w+)"
        + H
        + r"*=>",
        "arrow_function",
    ),
    # Class
    (r"(?:export" + H + r"+)?(?:abstract" + H + r"+)?class" + H + r"+(\w+)", "class"),
    # Interface
    (r"(?:export" + H + r"+)?interface" + H + r"+(\w+)", "interface"),
    # Type alias: type Name = ...
    (r"(?:export" + H + r"+)?type" + H + r"+(\w+)" + H + r"*=", "type_alias"),
    # Enum
    (r"(?:export" + H + r"+)?(?:const" + H + r"+)?enum" + H + r"+(\w+)", "enum"),
    # Const/let/var (not arrow functions — catch variables)
    (
        r"(?:export"
        + H
        + r"+)?(?:const|let|var)"
        + H
        + r"+(\w+)"
        + H
        + r"*(?::[^=;]+)?"
        + H
        + r"*=(?!=)"
        + H
        + r"*(?!"
        + H
        + r"*(?:\([^)]*\)|\w+)"
        + H
        + r"*=>)",
        "variable",
    ),
    # Constructor
    (r"(?:public|private|protected)?" + H + r"*(constructor)" + H + r"*\(", "constructor"),
    # Method in class (name(...) { preceded by indentation in class context)
    (
        r"^"
        + H
        + r"*(?:public|private|protected|static|readonly|async)"
        + H
        + r"+(?:get"
        + H
        + r"+|set"
        + H
        + r"+)?(\w+)"
        + H
        + r"*\([^)]*\)"
        + H
        + r"*(?::[^{]+)?"
        + H
        + r"*\{",
        "method",
    ),
    # Export default function/class
    (r"export" + H + r"+default" + H + r"+(?:function" + H + r"+(\w+)|class" + H + r"+(\w+)|(\w+))", "default_export"),
    # Decorated class/function (uses \s for newline)
    (r"@\w+" + H + r"*\n" + H + r"*(?:export" + H + r"+)?(?:class|function)" + H + r"+(\w+)", "decorated"),
]

# ─── Python AST Analysis ──────────────────────────────────────────────────


def _py_find_definitions(filepath, symbol):
    """Find all definitions in a Python file matching symbol."""
    matches = []
    try:
        source = _read_file(filepath)
        tree = ast.parse(source, filepath)
    except SyntaxError:
        return matches

    for node in ast.walk(tree):
        name = None
        line = node.lineno if hasattr(node, "lineno") else 0
        kind = None

        if isinstance(node, ast.FunctionDef):
            name = node.name
            kind = "function"
        elif isinstance(node, ast.AsyncFunctionDef):
            name = node.name
            kind = "async_function"
        elif isinstance(node, ast.ClassDef):
            name = node.name
            kind = "class"
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    name = t.id
                    kind = "variable"
                    line = t.lineno
                    break
        if name and name == symbol:
            matches.append(
                {
                    "type": kind,
                    "name": name,
                    "file": str(filepath),
                    "line": line,
                }
            )

    return matches


def _py_find_references(filepath, symbol):
    """Find all references to a symbol in a Python file."""
    matches = []
    try:
        source = _read_file(filepath)
        tree = ast.parse(source, filepath)
    except SyntaxError:
        return matches

    lines = source.split("\n")

    # Track which Name positions are part of a Call to avoid double-count,
    # and which lines are definitions for this symbol (precomputed, O(n)).
    call_name_lines = set()
    def_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == symbol and hasattr(node.func, "lineno"):
                call_name_lines.add(node.func.lineno)
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            if node.name == symbol and hasattr(node, "lineno"):
                def_lines.add(node.lineno)

    for node in ast.walk(tree):
        line = node.lineno if hasattr(node, "lineno") else 0

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == symbol:
                context = lines[line - 1][:120] if line <= len(lines) else ""
                matches.append(
                    {
                        "type": "call",
                        "file": str(filepath),
                        "line": line,
                        "context": context.strip(),
                    }
                )
        elif isinstance(node, ast.Name) and node.id == symbol and line not in call_name_lines and line not in def_lines:
            context = lines[line - 1][:120] if line <= len(lines) else ""
            matches.append(
                {
                    "type": "reference",
                    "file": str(filepath),
                    "line": line,
                    "context": context.strip(),
                }
            )
        elif isinstance(node, ast.Attribute) and node.attr == symbol:
            context = lines[line - 1][:120] if line <= len(lines) else ""
            matches.append(
                {
                    "type": "attribute",
                    "file": str(filepath),
                    "line": line,
                    "context": context.strip(),
                }
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == symbol or (alias.asname and alias.asname == symbol):
                    context = lines[line - 1][:120] if line <= len(lines) else ""
                    matches.append(
                        {
                            "type": "import",
                            "file": str(filepath),
                            "line": line,
                            "context": context.strip(),
                        }
                    )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == symbol or (alias.asname and alias.asname == symbol):
                    context = lines[line - 1][:120] if line <= len(lines) else ""
                    matches.append(
                        {
                            "type": "import",
                            "file": str(filepath),
                            "line": line,
                            "context": context.strip(),
                        }
                    )

    return matches


# ─── C++ Heuristic Analysis ───────────────────────────────────────────────


def _cpp_find_definitions(filepath, symbol):
    """Find C++ definitions matching symbol using regex patterns."""
    matches = []
    try:
        source = _read_file(filepath)
        lines = source.split("\n") if source else []
    except (UnicodeDecodeError, OSError):
        # Try binary mode for UTF-16 etc.
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            source = raw.decode("utf-8", errors="replace")
            lines = source.split("\n")
        except OSError:
            return matches

    for pattern, kind in CPP_DEF_PATTERNS:
        for m in re.finditer(pattern, source):
            # Find which capture group has the name
            name = m.group(1) if kind != "method" else m.group(2)
            if name == symbol:
                line_no = source[: m.start()].count("\n") + 1
                context = lines[line_no - 1][:120] if line_no <= len(lines) else ""
                matches.append(
                    {
                        "type": kind,
                        "name": name,
                        "file": str(filepath),
                        "line": line_no,
                        "context": context.strip(),
                    }
                )

    return matches


# ─── TypeScript/JavaScript Analysis ────────────────────────────────────────


TS_COMMENT_RE = re.compile(r"//.*$|/\*.*?\*/|^\s*\*", re.MULTILINE | re.DOTALL)
TS_STRING_RE = re.compile(r"""['"`][^'"`]*['"`]""")


def _strip_ts_comments_and_strings(source):
    """Remove comments and string literals before regex matching."""
    # Replace string literals with spaces
    result = TS_STRING_RE.sub(lambda m: " " * len(m.group(0)), source)
    # Replace comments with spaces
    result = TS_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), result)
    # Collapse runs of 3+ horizontal whitespace to prevent regex backtracking
    result = re.sub(r"[ \t]{3,}", "   ", result)
    return result


def _ts_find_definitions(filepath, symbol):
    """Find TypeScript/JS definitions matching symbol using regex patterns."""
    matches = []
    try:
        source = _read_file(filepath)
        lines = source.split("\n") if source else []
    except (UnicodeDecodeError, OSError):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            source = raw.decode("utf-8", errors="replace")
            lines = source.split("\n")
        except OSError:
            return matches

    clean = _strip_ts_comments_and_strings(source)

    for pattern, kind in TS_DEF_PATTERNS:
        for m in re.finditer(pattern, clean, re.MULTILINE):
            # Find the name capture group (smallest numbered group that has a value)
            name = ""
            for g in range(1, m.lastindex + 1):
                val = m.group(g)
                if val:
                    name = val
                    break
            if name and name == symbol:
                line_no = clean[: m.start()].count("\n") + 1
                context = lines[line_no - 1][:120] if line_no <= len(lines) else ""
                matches.append(
                    {
                        "type": kind,
                        "name": name,
                        "file": str(filepath),
                        "line": line_no,
                        "context": context.strip(),
                    }
                )

    # Deduplicate by file+line
    seen = set()
    unique = []
    for r in sorted(matches, key=lambda x: (x["file"], x["line"])):
        key = (r["file"], r["line"], r["type"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _ts_find_references(filepath, symbol):
    """Find all references to a symbol in a TS/JS file (word-boundary grep)."""
    return _grep_find_references(filepath, symbol)


# ─── Generic Reference Search (rg/grep) ──────────────────────────────────


def _grep_find_references(filepath, symbol):
    """Find all references to symbol in a file using regex."""
    matches = []
    try:
        source = _read_file(filepath)
        lines = source.split("\n") if source else []
    except (UnicodeDecodeError, OSError):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
            lines = text.split("\n")
        except OSError:
            return matches

    # Word boundary matching
    pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
    for i, line in enumerate(lines, 1):
        if pattern.search(line):
            matches.append(
                {
                    "type": "reference",
                    "file": str(filepath),
                    "line": i,
                    "context": line[:120].strip(),
                }
            )

    return matches


# ─── File Type Detection ──────────────────────────────────────────────────


def _is_python(filepath):
    return filepath.endswith(".py")


def _is_cpp(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    return ext in (".cpp", ".c", ".h", ".hpp", ".cc", ".cxx", ".hxx", ".hh")


def _is_typescript(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    return ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def _is_test_file(filepath):
    name = os.path.basename(filepath)
    fwd = filepath.replace("\\", "/")
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_test.cpp")
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".test.js")
        or name.endswith(".test.jsx")
        or "_test." in name
        or "/test_" in fwd
        or ".spec." in name
    )


def _is_source_file(filepath):
    return _is_python(filepath) or _is_cpp(filepath) or _is_typescript(filepath)


# ─── Core Analyzer ────────────────────────────────────────────────────────


class ImpactAnalyzer:
    def __init__(self, root_dir=None):
        if root_dir is None:
            root_dir = self._detect_root()
        self.root = Path(root_dir).resolve()
        self._file_cache: dict[str, list[str]] = {}

    def _detect_root(self):
        """Auto-detect project root via git."""
        try:
            result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return os.getcwd()

    def _walk_files(self, lang="all"):
        """Walk all source files in project."""
        if lang in self._file_cache:
            return self._file_cache[lang]

        files = []
        for root, dirs, names in os.walk(self.root):
            # Skip common non-source dirs
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("__pycache__", "node_modules", "build", "dist", ".git", ".eggs", "env", "venv")
            ]
            for name in names:
                fpath = os.path.join(root, name)
                if lang == "py" and _is_python(fpath):
                    files.append(fpath)
                elif lang == "cpp" and _is_cpp(fpath):
                    files.append(fpath)
                elif lang in ("ts", "js") and _is_typescript(fpath):
                    files.append(fpath)
                elif lang == "all" and _is_source_file(fpath):
                    files.append(fpath)

        self._file_cache[lang] = files
        return files

    def find_definition(self, symbol, lang="all"):
        """Find all definitions of a symbol (deduplicated by file+line)."""
        results = []
        for fp in self._walk_files(lang):
            if _is_python(fp):
                results.extend(_py_find_definitions(fp, symbol))
            elif _is_cpp(fp):
                results.extend(_cpp_find_definitions(fp, symbol))
            elif _is_typescript(fp):
                results.extend(_ts_find_definitions(fp, symbol))
        # Deduplicate by file+line
        seen = set()
        unique = []
        for r in sorted(results, key=lambda x: (x["file"], x["line"])):
            key = (r["file"], r["line"], r["type"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def find_references(self, symbol, lang="all"):
        """Find all references to a symbol (deduplicated by file+line)."""
        results = []
        for fp in self._walk_files(lang):
            if _is_python(fp):
                results.extend(_py_find_references(fp, symbol))
            elif _is_cpp(fp):
                results.extend(_grep_find_references(fp, symbol))
            elif _is_typescript(fp):
                results.extend(_ts_find_references(fp, symbol))
        seen = set()
        unique = []
        for r in sorted(results, key=lambda x: (x["file"], x["line"])):
            key = (r["file"], r["line"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def find_tests(self, symbol, lang="all"):
        """Find test files referencing a symbol (deduplicated)."""
        results = []
        for fp in self._walk_files(lang):
            if not _is_test_file(fp):
                continue
            if _is_python(fp):
                results.extend(_py_find_references(fp, symbol))
            elif _is_cpp(fp):
                results.extend(_grep_find_references(fp, symbol))
            elif _is_typescript(fp):
                results.extend(_ts_find_references(fp, symbol))
        seen = set()
        unique = []
        for r in sorted(results, key=lambda x: (x["file"], x["line"])):
            key = (r["file"], r["line"])
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def find_all_defs_in_file(self, filepath):
        """Find all symbol definitions in a single file."""
        if not os.path.exists(filepath):
            return []
        if _is_python(filepath):
            matches = []
            try:
                source = _read_file(filepath)
                tree = ast.parse(source, filepath)
            except (SyntaxError, OSError):
                return matches
            for node in ast.walk(tree):
                name = None
                line = getattr(node, "lineno", 0)
                kind = None
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name
                    kind = "function"
                elif isinstance(node, ast.ClassDef):
                    name = node.name
                    kind = "class"
                elif isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            name = t.id
                            kind = "variable"
                            line = t.lineno
                            break
                elif isinstance(node, (ast.ImportFrom, ast.Import)):
                    for alias in node.names:
                        aname = alias.asname or alias.name.split(".")[0]
                        matches.append({"name": aname, "type": "import", "line": node.lineno})
                    continue
                if name:
                    matches.append({"name": name, "type": kind, "line": line})
            return sorted(matches, key=lambda x: x["line"])
        elif _is_cpp(filepath):
            matches = []
            try:
                source = _read_file(filepath)
            except OSError:
                return matches
            for pattern, kind in CPP_DEF_PATTERNS:
                for m in re.finditer(pattern, source):
                    name = m.group(1) if kind != "method" else m.group(2)
                    line_no = source[: m.start()].count("\n") + 1
                    matches.append({"name": name, "type": kind, "line": line_no})
            seen = set()
            unique = []
            for m in sorted(matches, key=lambda x: x["line"]):
                key = (m["name"], m["line"])
                if key not in seen:
                    seen.add(key)
                    unique.append(m)
            return unique
        elif _is_typescript(filepath):
            matches = []
            try:
                source = _read_file(filepath)
            except OSError:
                return matches
            clean = _strip_ts_comments_and_strings(source)
            for pattern, kind in TS_DEF_PATTERNS:
                for m in re.finditer(pattern, clean, re.MULTILINE):
                    name = ""
                    for g in range(1, m.lastindex + 1):
                        val = m.group(g)
                        if val:
                            name = val
                            break
                    line_no = source[: m.start()].count("\n") + 1
                    matches.append({"name": name, "type": kind, "line": line_no})
            seen = set()
            unique = []
            for m in sorted(matches, key=lambda x: x["line"]):
                key = (m["name"], m["line"])
                if key not in seen:
                    seen.add(key)
                    unique.append(m)
            return unique
        return []

    def find_callees(self, symbol, lang="all"):
        """Find what functions/methods are called by a definition (Python only)."""
        # Find the definition first
        defs = self.find_definition(symbol, lang)
        if not defs:
            return []

        # Only Python AST can do this
        callees = []
        for d in defs:
            if not _is_python(d["file"]):
                continue
            try:
                source = _read_file(d["file"])
                tree = ast.parse(source, d["file"])
            except SyntaxError:
                continue

            # Find the function/class node
            for node in ast.walk(tree):
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                    and node.name == symbol
                    and hasattr(node, "lineno")
                    and node.lineno == d["line"]
                ):
                    # Single walk: collect nested def ranges AND direct calls
                    children = list(ast.walk(node))
                    nested_ranges = []
                    callee_nodes = []
                    for child in children:
                        if child is node:
                            continue
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            if hasattr(child, "lineno") and hasattr(child, "end_lineno"):
                                nested_ranges.append((child.lineno, child.end_lineno))
                        elif isinstance(child, ast.Call):
                            callee_nodes.append(child)
                    for child in callee_nodes:
                        in_nested = any(start <= child.lineno <= end for start, end in nested_ranges)
                        if in_nested:
                            continue
                        if isinstance(child.func, ast.Name):
                            callees.append(
                                {
                                    "name": child.func.id,
                                    "file": d["file"],
                                    "line": child.lineno,
                                }
                            )
                        elif isinstance(child.func, ast.Attribute):
                            callees.append(
                                {
                                    "name": f"{child.func.value.id}.{child.func.attr}"
                                    if isinstance(child.func.value, ast.Name)
                                    else child.func.attr,
                                    "file": d["file"],
                                    "line": child.lineno,
                                }
                            )
                    break

        return sorted(callees, key=lambda r: r["line"])

    def infer_symbol(self, filepath, line_no):
        """Infer symbol name at a given file:line.

        Priority: function/method call > class/function def > identifier.
        """
        try:
            source = _read_file(filepath)
            lines = source.split("\n") if source else []
        except OSError:
            return None

        if line_no < 1 or line_no > len(lines):
            return None

        line = lines[line_no - 1]

        # 1. Function call pattern: identifier(args)
        _KEYWORDS = frozenset(
            {
                "if",
                "for",
                "while",
                "return",
                "switch",
                "catch",
                "elif",
                "except",
                "with",
                "yield",
                "raise",
                "del",
                "assert",
                "try",
                "typeof",
                "instanceof",
                "void",
                "delete",
            }
        )
        call_match = re.search(r"([A-Za-z_]\w*)\s*\(", line)
        if call_match and call_match.group(1) not in _KEYWORDS:
            return call_match.group(1)

        # 2. Class/function def pattern: def/class/function/interface/type identifier
        def_match = re.match(r"\s*(?:def|class|function|interface|type|enum)\s+(\w+)", line)
        if def_match:
            return def_match.group(1)

        # 3. Assignment: target = (const/let/var or just name)
        assign_match = re.match(r"\s*(?:const|let|var)?\s*(\w+)\s*(?::[^=;]+)?\s*=", line)
        if assign_match:
            return assign_match.group(1)

        # 4. First enclosing function/class name (walking upward for context)
        for check_line in range(line_no - 2, -1, -1):
            ctx_match = re.match(
                r"^\s*(?:def|class|function|interface|type|enum|async\s+def|export\s+default)\s+(\w+)",
                lines[check_line],
            )
            if ctx_match:
                return ctx_match.group(1)
        # 5. Generic: first non-keyword identifier
        # use built-in set of Python keywords
        _keywords = {
            "False",
            "None",
            "True",
            "and",
            "as",
            "assert",
            "async",
            "await",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
        }
        ident = re.search(r"(\w+)", line)
        if ident and ident.group(1) not in _keywords:
            return ident.group(1)

        return None


# ─── Formatters ───────────────────────────────────────────────────────────


def _fmt_line_count(count):
    s = "s" if count != 1 else ""
    return f"{count} occurrence{s}"


def format_pretty(symbol, defs, refs, tests, callees, root):
    """Human-readable output."""
    lines = []
    lines.append(f"impact: `{symbol}`")
    lines.append(f"  project: {root}")
    lines.append("")

    # Definitions
    lines.append(f"  [def] {_fmt_line_count(len(defs))}")
    for d in defs:
        rel = os.path.relpath(d["file"], root)
        ctx = d.get("context", "")
        tc = f"  -- {ctx}" if ctx else ""
        lines.append(f"    {rel}:{d['line']}  ({d['type']}){tc}")
    if not defs:
        lines.append("    (not found)")

    # References (excluding definitions)
    def_lines = {(d["file"], d["line"]) for d in defs}
    refs_only = [r for r in refs if (r["file"], r["line"]) not in def_lines]
    lines.append("")
    lines.append(f"  [ref] {_fmt_line_count(len(refs_only))}")
    for r in refs_only[:20]:
        rel = os.path.relpath(r["file"], root)
        ctx = r.get("context", "")
        tc = f"  -- {ctx}" if ctx else ""
        lines.append(f"    {rel}:{r['line']}{tc}")
    if len(refs_only) > 20:
        lines.append(f"    ... and {len(refs_only) - 20} more")

    # Tests
    lines.append("")
    lines.append(f"  [test] {_fmt_line_count(len(tests))}")
    for t in tests[:10]:
        rel = os.path.relpath(t["file"], root)
        ctx = t.get("context", "")
        tc = f"  -- {ctx}" if ctx else ""
        lines.append(f"    {rel}:{t['line']}{tc}")
    if len(tests) > 10:
        lines.append(f"    ... and {len(tests) - 10} more")

    # Callees
    if callees:
        lines.append("")
        lines.append(f"  [calls] {_fmt_line_count(len(callees))}")
        for c in callees[:10]:
            rel = os.path.relpath(c["file"], root)
            lines.append(f"    {rel}:{c['line']}  -> {c['name']}")
        if len(callees) > 10:
            lines.append(f"    ... and {len(callees) - 10} more")

    return "\n".join(lines)


def format_json(symbol, defs, refs, tests, callees, root):
    """JSON output for plugin."""
    return json.dumps(
        {
            "symbol": symbol,
            "project": str(root),
            "definitions": defs,
            "references": refs,
            "tests": tests,
            "callees": callees,
        },
        indent=2,
    )


# ─── CLI ──────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        return 0

    args = sys.argv[1:]

    # Parse flags first (before extracting cmd)
    use_json = "--json" in args
    lang = "all"
    root_dir = None
    next_is_root = False
    next_is_lang = False
    clean_args = []
    for a in args:
        if next_is_root:
            root_dir = a
            next_is_root = False
            continue
        if next_is_lang:
            lang = a
            next_is_lang = False
            continue
        if a == "--json":
            continue
        if a == "--root" and not next_is_root:
            next_is_root = True
            continue
        if a.startswith("--root="):
            root_dir = a.split("=", 1)[1]
            continue
        if a == "--lang" and not next_is_lang:
            next_is_lang = True
            continue
        if a.startswith("--lang="):
            lang = a.split("=", 1)[1]
            continue
        if a == "--py":
            lang = "py"
            continue
        if a == "--cpp":
            lang = "cpp"
            continue
        clean_args.append(a)

    if not clean_args:
        print(__doc__.strip())
        return 0

    cmd = clean_args[0]

    # Handle --version
    if cmd == "--version":
        print("impact.py 0.1.1")
        return 0

    analyzer = ImpactAnalyzer(root_dir)
    symbol = None

    # Parse command
    if cmd in ("def", "definition"):
        if len(clean_args) < 2:
            print("usage: impact def <symbol>")
            return 1
        symbol = clean_args[1]
        defs = analyzer.find_definition(symbol, lang)
        if use_json:
            print(format_json(symbol, defs, [], [], [], analyzer.root))
        else:
            print(format_pretty(symbol, defs, [], [], [], analyzer.root))
        return 0 if defs else 1

    elif cmd in ("ref", "refs", "references"):
        if len(clean_args) < 2:
            print("usage: impact refs <symbol>")
            return 1
        symbol = clean_args[1]
        refs = analyzer.find_references(symbol, lang)
        if use_json:
            print(format_json(symbol, [], refs, [], [], analyzer.root))
        else:
            print(format_pretty(symbol, [], refs, [], [], analyzer.root))
        return 0 if refs else 1

    elif cmd in ("test", "tests"):
        if len(clean_args) < 2:
            print("usage: impact tests <symbol>")
            return 1
        symbol = clean_args[1]
        tests = analyzer.find_tests(symbol, lang)
        if use_json:
            print(format_json(symbol, [], [], tests, [], analyzer.root))
        else:
            print(format_pretty(symbol, [], [], tests, [], analyzer.root))
        return 0 if tests else 1

    elif cmd in ("file",):
        if len(clean_args) < 2:
            print("usage: impact file <path>")
            return 1
        filepath = clean_args[1]
        resolved = filepath if os.path.exists(filepath) else os.path.join(analyzer.root, filepath)
        if not os.path.exists(resolved):
            print(f"File not found: {filepath}")
            return 1
        defs = analyzer.find_all_defs_in_file(resolved)
        if use_json:
            print(json.dumps({"file": str(resolved), "symbols": defs}, indent=2))
        else:
            lines = [f"impact file: {os.path.relpath(resolved, analyzer.root)}"]
            lines.append(f"  {len(defs)} symbols defined")
            for d in defs:
                lines.append(f"    {d['line']:4d}  ({d['type']:<10s}) {d['name']}")
            print("\n".join(lines))
        return 0

    elif cmd in ("graph", "callees"):
        if len(clean_args) < 2:
            print("usage: impact graph <symbol>")
            return 1
        symbol = clean_args[1]
        defs = analyzer.find_definition(symbol, lang)
        refs = analyzer.find_references(symbol, lang)
        tests = analyzer.find_tests(symbol, lang)
        callees = analyzer.find_callees(symbol, lang)
        if use_json:
            print(format_json(symbol, defs, refs, tests, callees, analyzer.root))
        else:
            print(format_pretty(symbol, defs, refs, tests, callees, analyzer.root))
        return 0 if (defs or refs or tests or callees) else 1

    else:
        # Default: show everything for a symbol
        symbol = cmd

        # Check if it's a file:line reference
        if ":" in cmd:
            parts = cmd.rsplit(":", 1)
            if len(parts) >= 2 and parts[1].isdigit():
                maybe_file, maybe_line = parts[0], parts[1]
                resolved_file = maybe_file
                if not os.path.exists(maybe_file):
                    joined = os.path.join(analyzer.root, maybe_file)
                    if os.path.exists(joined):
                        resolved_file = joined
                if os.path.exists(resolved_file):
                    inferred = analyzer.infer_symbol(resolved_file, int(maybe_line))
                    if inferred:
                        symbol = inferred
                    else:
                        print(f"Cannot infer symbol at {cmd}")
                        return 1

        defs = analyzer.find_definition(symbol, lang)
        refs = analyzer.find_references(symbol, lang)
        tests = analyzer.find_tests(symbol, lang)
        callees = analyzer.find_callees(symbol, lang)

        if use_json:
            print(format_json(symbol, defs, refs, tests, callees, analyzer.root))
        else:
            print(format_pretty(symbol, defs, refs, tests, callees, analyzer.root))

        return 0 if (defs or refs or tests or callees) else 1


if __name__ == "__main__":
    sys.exit(main())
