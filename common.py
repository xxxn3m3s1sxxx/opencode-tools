"""Shared utilities for opencode-tools."""

import os
import sys


VERSION = "0.4.0"

EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".env",
    "build", "dist", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".eggs", ".idea", ".vscode", "target", ".next", ".nuxt",
}

SOURCE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".cpp", ".c", ".h", ".hpp", ".cc", ".cxx", ".hxx", ".hh",
    ".rs", ".go", ".java", ".kt", ".swift",
}

PY_SOURCE_EXTS = {".py"}
TS_SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
CPP_SOURCE_EXTS = {".cpp", ".c", ".h", ".hpp", ".cc", ".cxx", ".hxx", ".hh"}

LANGUAGE_EXTS = {
    "all": SOURCE_EXTS,
    "py": PY_SOURCE_EXTS,
    "python": PY_SOURCE_EXTS,
    "ts": TS_SOURCE_EXTS | {".ts", ".tsx"},
    "js": {".js", ".jsx", ".mjs", ".cjs"},
    "cpp": CPP_SOURCE_EXTS,
    "c": {".c", ".h"},
}


def reconfigure_stdout_stderr():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


def _read_file(filepath):
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            raw = f.read()
        if raw.startswith("\ufeff"):
            raw = raw[1:]
        return raw.replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, UnicodeDecodeError):
        return None


def _read_file_lines(filepath):
    raw = _read_file(filepath)
    if raw is None:
        return None
    return raw.split("\n")


def _is_python(filepath):
    return filepath.endswith(".py")


def _is_cpp(filepath):
    _, ext = os.path.splitext(filepath)
    return ext.lower() in CPP_SOURCE_EXTS


def _is_typescript(filepath):
    _, ext = os.path.splitext(filepath)
    return ext.lower() in TS_SOURCE_EXTS


def _is_source_file(filepath):
    _, ext = os.path.splitext(filepath)
    return ext.lower() in SOURCE_EXTS


def _walk_files(root, exts=None, exclude_dirs=None):
    if exts is None:
        exts = SOURCE_EXTS
    if exclude_dirs is None:
        exclude_dirs = EXCLUDE_DIRS
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        if any(d.startswith(".") for d in dirnames):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            _, ext = os.path.splitext(f)
            if ext.lower() in exts:
                files.append(os.path.join(dirpath, f))
    return sorted(files)


def line_count(filepath):
    raw = _read_file(filepath)
    if raw is None:
        return 0
    return len(raw.split("\n"))


def checksum(filepath):
    import hashlib
    raw = _read_file(filepath)
    if raw is None:
        return None
    return hashlib.sha256(raw.encode()).hexdigest()[:12]
