#!/usr/bin/env python3
"""Stress and edge-case tests for all tools.

Tests things that could go wrong: huge inputs, encoding issues,
pathological code patterns, concurrency trouble, and weird OS edge cases.
"""

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

P = sys.executable
failed = 0
total = 0


def _run(*args, cwd=None, timeout=120):
    return subprocess.run(
        [P] + list(args),
        capture_output=True,
        text=True,
        cwd=cwd or TOOLS_DIR,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _rt(name, *args, **kw):
    return _run(os.path.join(TOOLS_DIR, f"{name}.py"), *args, **kw)


def _tmp(src="", suffix=".py", binary=False):
    fd, path = tempfile.mkstemp(suffix=suffix, dir=tempfile.gettempdir())
    os.close(fd)
    if src:
        mode = "wb" if binary else "w"
        enc = {} if binary else {"encoding": "utf-8"}
        with open(path, mode, **enc) as f:
            f.write(src)
    return path


def check(desc, cond, detail=""):
    global total, failed
    total += 1
    if cond:
        print(f"  [OK] {desc}")
    else:
        print(f"  [FAIL] {desc}  {detail}")
        failed += 1


# ====================================================================
# IMPACT — stress
# ====================================================================
def stress_impact_huge_file():
    lines = [f"def func_{i}(): return {i}\n" for i in range(10000)]
    lines.append("x = func_0() + func_9999()\n")
    tmp = _tmp("".join(lines))
    try:
        r = _rt("impact", "--json", tmp)
        check("impact huge file no crash", r.returncode in (0, 1))
        check("impact huge file output < 5MB", len(r.stdout) < 5_000_000)
    finally:
        os.unlink(tmp)


def stress_impact_empty_file():
    tmp = _tmp("")
    try:
        r = _rt("impact", "--json", tmp)
        # exit 1 is OK — it means "no results" in impact
        check("impact empty file no crash", r.returncode in (0, 1))
        if r.returncode == 0:
            try:
                json.loads(r.stdout)
                check("impact empty file valid JSON", True)
            except json.JSONDecodeError:
                check("impact empty file valid JSON", False)
    finally:
        os.unlink(tmp)


def stress_impact_binary_file():
    tmp = _tmp("\x00\x01\x02\xff\xfe")
    try:
        r = _rt("impact", "--json", tmp)
        check("impact binary file no crash", r.returncode in (0, 1))
    finally:
        os.unlink(tmp)


def stress_impact_unicode_file():
    src = "# coding: utf-8\nüber = 1\nnaïve = 2\nπ = 3.14\n"
    tmp = _tmp(src)
    try:
        r = _rt("impact", "--json", tmp)
        # may fail on Python identifying unicode defs — that's OK, no crash
        check("impact unicode file no crash", r.returncode in (0, 1))
    finally:
        os.unlink(tmp)


def stress_impact_nested_depth():
    src = "def outer():\n"
    for i in range(100):
        src += "    " * (i + 1) + f"def inner_{i}():\n"
        src += "    " * (i + 2) + "pass\n"
        if i > 0:
            src += "    " * (i + 1) + f"inner_{i}()\n"
    src += "    pass\n"
    tmp = _tmp(src)
    try:
        r = _rt("impact", "--json", tmp)
        check("impact deep nesting no crash", r.returncode in (0, 1))
    finally:
        os.unlink(tmp)


# ====================================================================
# GRAPH — stress
# ====================================================================
def stress_graph_chain_100():
    files = {}
    prev = None
    for ch in [chr(ord("A") + i) for i in range(26)] * 4:
        tmp = _tmp(f"import {prev}\n" if prev else "pass\n")
        files[ch] = tmp
        prev = ch
    try:
        r = _rt("graph", files["A"], "--json")
        check("graph chain-100 no crash", r.returncode == 0)
    finally:
        for p in files.values():
            if os.path.exists(p):
                os.unlink(p)


def stress_graph_bad_import_syntaxes():
    srcs = [
        "import \n",
        "from import os\n",
        "import 123invalid\n",
        "from .. import something\n",
        "import os, sys,, re\n",
        "import (os, sys)\n",
    ]
    for i, src in enumerate(srcs):
        tmp = _tmp(src)
        try:
            r = _rt("graph", tmp, "--json")
            # Bad syntax may cause exit 1 — that's OK
            check(f"graph bad syntax #{i} no crash", r.returncode in (0, 1))
        finally:
            os.unlink(tmp)


def stress_graph_empty_file():
    tmp = _tmp("")
    try:
        r = _rt("graph", tmp, "--json")
        check("graph empty file returns 0", r.returncode == 0)
    finally:
        os.unlink(tmp)


# ====================================================================
# SEARCH — stress
# ====================================================================
def stress_search_unicode():
    r = _rt("search", "übersicht|naïve|π", os.path.join(TOOLS_DIR, "stress_tools.py"))
    check("search unicode returns 0", r.returncode == 0)
    check("search unicode finds match", "übersicht" in r.stdout or "match" in r.stdout.lower())


def stress_search_10k_matches():
    src = "\n".join(f"MATCH_{i}" for i in range(10000))
    tmp = _tmp(src)
    try:
        r = _rt("search", r"MATCH_\d+", tmp)
        check("search 10k matches returns 0", r.returncode == 0)
        # Count matches in stdout
        n = r.stdout.count("MATCH_")
        check("search 10k matches >= 9900", n >= 9900, f"got {n}")
    finally:
        os.unlink(tmp)


def stress_search_special_path():
    sp = os.path.join(TOOLS_DIR, "weird [path] (test) {money}.py")
    try:
        with open(sp, "w", encoding="utf-8") as f:
            f.write("weird_path_test_var = 1\n")
        r = _rt("search", "weird_path_test_var", sp)
        check("search special path returns 0", r.returncode == 0)
        check("search special path finds match", "weird_path_test_var" in r.stdout)
    finally:
        if os.path.exists(sp):
            os.unlink(sp)


def stress_search_no_match_large():
    src = "\n".join(f"no_match_line_{i}" for i in range(5000))
    tmp = _tmp(src)
    try:
        r = _rt("search", "does_not_exist_ZZZZ", tmp)
        check("search no-match large no crash", r.returncode in (0, 1))
    finally:
        os.unlink(tmp)


# ====================================================================
# LINT — stress
# ====================================================================
def stress_lint_all_parsers():
    for fmt_name in ["ruff", "eslint", "tsc", "mypy", "pylint"]:
        r = _rt("lint", fmt_name, "--json")
        check(f"lint parser {fmt_name} no crash", r.returncode in (0, 1))


def stress_lint_bad_tool():
    r = _rt("lint", "nonexistent_tool_name_xyz")
    check("lint bad tool non-zero", r.returncode != 0)


# ====================================================================
# VERIFY — stress
# ====================================================================
def stress_verify_binary_checksum():
    tmp = _tmp(b"\x00\x01\x02" * 1000 + b"\xff" * 1000, ".bin", binary=True)
    try:
        r = _rt("verify", tmp)
        check("verify binary file returns 0", r.returncode == 0)
        check("verify binary sha256 shown", "sha256" in r.stdout.lower() or "sha" in r.stdout.lower())
    finally:
        os.unlink(tmp)


def stress_verify_huge_context():
    r = _rt("verify", os.path.join(TOOLS_DIR, "verify.py"), "--line", "100", "--context", "500")
    check("verify huge context no crash", r.returncode == 0)


def stress_verify_binary_not_contains():
    tmp = _tmp(b"\x00\x01\x02\xff", ".bin", binary=True)
    try:
        r = _rt("verify", tmp, "--not", "PASS")
        check("verify binary --not no crash", r.returncode == 0)
    finally:
        os.unlink(tmp)


# ====================================================================
# REFACTOR — stress
# ====================================================================
def stress_refactor_collision():
    src = "x = 1\ny = 2\nz = x + y\n"
    tmp = _tmp(src)
    try:
        r = _rt("refactor", "x", "y", "--file", tmp, "--dry-run")
        check("refactor name collision no crash", r.returncode == 0)
    finally:
        os.unlink(tmp)


def stress_refactor_to_keyword():
    src = "klass = 42\nprint(klass)\n"
    tmp = _tmp(src)
    try:
        r = _rt("refactor", "klass", "class", "--file", tmp, "--dry-run")
        check("refactor to keyword no crash", r.returncode == 0)
    finally:
        os.unlink(tmp)


def stress_refactor_ts_slash():
    src = """const a = x / 2;
const re = /abc/;
const b = x / y / z;
const d = (x: number) => x / 2;
"""
    tmp = _tmp(src, ".ts")
    try:
        r = _rt("refactor", "x", "renamed_x", "--file", tmp, "--dry-run")
        check("refactor TS slash no crash", r.returncode == 0)
    finally:
        os.unlink(tmp)


# ====================================================================
# CALLTRACE — stress
# ====================================================================
def stress_calltrace_deep():
    """Calltrace on a deep chain — exit 1 is OK (symbol not found in tools dir)."""
    r = _rt("calltrace", "top", "--down", "-d", "100")
    check("calltrace deep chain no crash", r.returncode in (0, 1))


# ====================================================================
# CHANGELOG — stress
# ====================================================================
def stress_changelog_huge_n():
    r = _rt("changelog", "-n", "999999")
    check("changelog huge -n no crash", r.returncode in (0, 1))


def stress_changelog_zero_n():
    r = _rt("changelog", "-n", "0")
    check("changelog -n 0 no crash", r.returncode in (0, 1))


# ====================================================================
def main():
    print("\n  Stress & Edge-Case Tests — all tools")
    print(f"  {'=' * 42}")
    tests = [
        stress_impact_huge_file,
        stress_impact_empty_file,
        stress_impact_binary_file,
        stress_impact_unicode_file,
        stress_impact_nested_depth,
        stress_graph_chain_100,
        stress_graph_bad_import_syntaxes,
        stress_graph_empty_file,
        stress_search_unicode,
        stress_search_10k_matches,
        stress_search_special_path,
        stress_search_no_match_large,
        stress_lint_all_parsers,
        stress_lint_bad_tool,
        stress_verify_binary_checksum,
        stress_verify_huge_context,
        stress_verify_binary_not_contains,
        stress_refactor_collision,
        stress_refactor_to_keyword,
        stress_refactor_ts_slash,
        stress_calltrace_deep,
        stress_changelog_huge_n,
        stress_changelog_zero_n,
    ]
    for t in tests:
        t()
    pct = round((total - failed) / total * 100) if total else 0
    print(f"\n  [{total - failed}/{total} passed] ({pct}%)")
    if failed:
        print(f"  [{failed}/{total} FAILED]")
        return 1
    print("  ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
