"""Shared utilities for opencode-tools."""

from __future__ import annotations

import os
import sys
from typing import Set, Optional


VERSION: str = "0.4.0"

EXCLUDE_DIRS: Set[str] = {
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

SOURCE_EXTS: Set[str] = {
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

PY_SOURCE_EXTS: Set[str] = {".py"}
TS_SOURCE_EXTS: Set[str] = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
CPP_SOURCE_EXTS: Set[str] = {".cpp", ".c", ".h", ".hpp", ".cc", ".cxx", ".hxx", ".hh"}

LANGUAGE_EXTS: dict[str, Set[str]] = {
    "all": SOURCE_EXTS,
    "py": PY_SOURCE_EXTS,
    "python": PY_SOURCE_EXTS,
    "ts": TS_SOURCE_EXTS | {".ts", ".tsx"},
    "js": {".js", ".jsx", ".mjs", ".cjs"},
    "cpp": CPP_SOURCE_EXTS,
    "c": {".c", ".h"},
}


def reconfigure_stdout_stderr() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass


def _read_file(filepath: str) -> Optional[str]:
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            raw = f.read()
        if raw.startswith("\ufeff"):
            raw = raw[1:]
        return raw.replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, UnicodeDecodeError):
        return None


def _read_file_lines(filepath: str) -> Optional[list[str]]:
    raw = _read_file(filepath)
    if raw is None:
        return None
    return raw.split("\n")


def _is_python(filepath: str) -> bool:
    return filepath.endswith(".py")


def _is_cpp(filepath: str) -> bool:
    _, ext = os.path.splitext(filepath)
    return ext.lower() in CPP_SOURCE_EXTS


def _is_typescript(filepath: str) -> bool:
    _, ext = os.path.splitext(filepath)
    return ext.lower() in TS_SOURCE_EXTS


def _is_source_file(filepath: str) -> bool:
    _, ext = os.path.splitext(filepath)
    return ext.lower() in SOURCE_EXTS


def _walk_files(
    root: str,
    exts: Optional[Set[str]] = None,
    exclude_dirs: Optional[Set[str]] = None,
) -> list[str]:
    if exts is None:
        exts = SOURCE_EXTS
    if exclude_dirs is None:
        exclude_dirs = EXCLUDE_DIRS
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        if any(d.startswith(".") for d in dirnames):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            _, ext = os.path.splitext(f)
            if ext.lower() in exts:
                files.append(os.path.join(dirpath, f))
    return sorted(files)


def line_count(filepath: str) -> int:
    raw = _read_file(filepath)
    if raw is None:
        return 0
    return len(raw.split("\n"))


def checksum(filepath: str) -> Optional[str]:
    import hashlib

    raw = _read_file(filepath)
    if raw is None:
        return None
    return hashlib.sha256(raw.encode()).hexdigest()[:12]
