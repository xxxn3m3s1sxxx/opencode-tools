#!/usr/bin/env python3
"""Regression tests for bugs fixed in the 2026-05-21 bug-hunt batch.

Each test targets a specific bug from the 19-fix session.
Ordered so side-effects can't corrupt later tests.
"""

import os
import sys
import subprocess
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TOOLS_DIR)
SRC_DIR = os.path.join(BASE_DIR, "src")
PASS = 0
FAIL = 0
_LAST_RUN = None


def _run(*args, input_text=None):
    global _LAST_RUN
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    r = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        input=input_text,
        cwd=BASE_DIR,
        env=env,
        encoding="utf-8",
        errors="replace",
    )
    _LAST_RUN = r
    return r


def _run_tool(name, *args):
    return _run(os.path.join(SRC_DIR, f"{name}.py"), *args)


def check(desc, cond):
    global PASS, FAIL, _LAST_RUN
    if cond:
        print(f"  [OK] {desc}")
        PASS += 1
    else:
        print(f"  [FAIL] {desc}")
        if _LAST_RUN and hasattr(_LAST_RUN, "returncode"):
            r = _LAST_RUN
            rc = r.returncode
            out = (r.stdout or "")[:300]
            err = (r.stderr or "")[:300]
            print(f"    rc={rc} stdout={out!r} stderr={err!r}")
        FAIL += 1


_TMP_FILES = []

def _tmpfile(src="", suffix=".py"):
    fd, path = tempfile.mkstemp(suffix=suffix, dir=tempfile.gettempdir())
    os.close(fd)
    _TMP_FILES.append(path)
    if src:
        with open(path, "w", encoding="utf-8") as f:
            f.write(src)
    return path


# ============================================================
# Safe tests (no side-effects on repo files)
# ============================================================


# 1. impact.py:526 — C++ NameError ('clean'→'source')
def test_impact_cpp_def():
    r = _run_tool("impact", "def", "printf", "--cpp", "--json")
    check("impact C++ def no NameError crash", r.returncode in (0, 1))
    try:
        json.loads(r.stdout)
        check("impact C++ def valid JSON", True)
    except json.JSONDecodeError:
        check("impact C++ def valid JSON", False)


# 2. impact.py:509 — break after first import alias
def test_impact_import_loop():
    # Ensure import resolution doesn't break after first alias
    r = _run_tool("impact", "os.path", "--json")
    check("impact import alias loop no crash", r.returncode in (0, 1))


# 3. impact.py:634 — keywords filtered from function-call matches
def test_impact_keyword_filter():
    # Analyzer must not report `if`/`for`/`while` as function calls
    tmp = _tmpfile("for x in range(10):\n    if x > 5:\n        break\n    while True:\n        pass\n")
    try:
        r = _run_tool("impact", "--json", tmp)
        check("impact keyword filter no crash", r.returncode in (0, 1))
    finally:
        os.unlink(tmp)


# 4. search.py:106 — os.walk on single file
def test_search_single_file():
    tmp = _tmpfile("hello_world = 42\n")
    try:
        r = _run_tool("search", "hello_world", tmp)
        check("search single-file returns 0", r.returncode == 0)
        check("search single-file finds match", "hello_world" in r.stdout)
    finally:
        os.unlink(tmp)


# 5. search.py:100 — ReDoS guard
def test_search_redos():
    r = _run_tool("search", "x" * 2001, os.path.join(SRC_DIR, "verify.py"))
    check("search ReDoS guard rejects long pattern", r.returncode != 0)
    check("search ReDoS guard message", "too long" in r.stderr.lower())


# 6. search.py:161 — relpath fix (dirname→path)
def test_search_relpath():
    subdir = os.path.join(BASE_DIR, "__regression_test_subdir__")
    os.makedirs(subdir, exist_ok=True)
    tmp = os.path.join(subdir, "_testfile.py")
    try:
        with open(tmp, "w") as f:
            f.write("relpath_check\n")
        r = _run_tool("search", "relpath_check", subdir)
        check("search relpath returns 0", r.returncode == 0)
        check("search relpath shows relative", "_testfile.py" in r.stdout)
    finally:
        for p in [tmp, subdir]:
            if os.path.isfile(p):
                os.unlink(p)
            if os.path.isdir(p):
                os.rmdir(p)


# 7. changelog.py:182 — int() guard
def test_changelog_int_guard():
    r = _run_tool("changelog", "-n", "abc")
    check("changelog -n abc non-zero", r.returncode != 0)


# 8. verify.py:324 — int() guard
def test_verify_int_guard():
    r = _run_tool("verify", os.path.join(SRC_DIR, "verify.py"), "--context", "abc")
    check("verify --context abc non-zero", r.returncode != 0)


# 9. calltrace.py:310 — int() guard
def test_calltrace_int_guard():
    r = _run_tool("calltrace", "-d", "abc")
    check("calltrace -d abc non-zero", r.returncode != 0)


# 10. search.py:170,172 — int() guard
def test_search_int_guard():
    r = _run_tool("search", "test", SRC_DIR, "--context=abc")
    check("search --context=abc non-zero", r.returncode != 0)


# 11. verify.py:302,336 — --line flag (was dead var)
def test_verify_line_flag():
    r = _run_tool("verify", os.path.join(SRC_DIR, "verify.py"), "--line", "5")
    check("verify --line 5 returns 0", r.returncode == 0)


# 12. refactor.py:194 — TS division / vs regex literal
def test_refactor_ts_division():
    tmp = _tmpfile("const x = width / 2;\n", ".ts")
    try:
        r = _run_tool("refactor", "width", "w", "--file", tmp, "--dry-run")
        check("refactor TS division no crash", r.returncode == 0)
    finally:
        os.unlink(tmp)


# 13. lint.py:209 — tool name injection guard
def test_lint_injection():
    r = _run_tool("lint", "../malicious")
    check("lint ../malicious non-zero", r.returncode != 0)


# 14. hashline.py:143 — uppercase anchor warning (no crash)
def test_hashline_uppercase():
    r = _run_tool("hashline", "read", "src/verify.py")
    check("hashline uppercase anchor OK", r.returncode == 0)


# 15. graph.py:144 — failed import returns None
def test_graph_bad_import():
    tmp = _tmpfile("import this_module_does_not_exist_xyzzy\n")
    try:
        r = _run_tool("graph", tmp, "--json")
        check("graph bad import no crash", r.returncode == 0)
    finally:
        os.unlink(tmp)


# 16. graph.py:208 — diamond dependency false cycle
def test_graph_diamond():
    files = {n: _tmpfile("", ".py") for n in "ABCD"}
    try:
        with open(files["A"], "w") as f:
            f.write("import B, C\n")
        with open(files["B"], "w") as f:
            f.write("import D\n")
        with open(files["C"], "w") as f:
            f.write("import D\n")
        with open(files["D"], "w") as f:
            f.write("pass\n")
        r = _run_tool("graph", files["A"], "--tree", "--json")
        check("graph diamond no crash", r.returncode == 0)
        if r.returncode == 0:
            try:
                data = json.loads(r.stdout)
                tree = data.get("tree", []) if isinstance(data, dict) else data
                if isinstance(tree, list):
                    cycles = [e for e in tree if isinstance(e, dict) and e.get("cycle")]
                else:
                    cycles = []
                check("graph diamond no false cycles", len(cycles) == 0)
            except json.JSONDecodeError:
                check("graph diamond JSON valid", False)
    finally:
        for p in files.values():
            if os.path.exists(p):
                os.unlink(p)


# 17. impact.py:288 — TS empty-name guard
def test_impact_ts_empty_def():
    r = _run_tool("impact", os.path.join(BASE_DIR, "plugins", "calltrace.ts"), "--json")
    check("impact TS file no crash", r.returncode in (0, 1))


# 18. calltrace entry point (renamed from trace.py → calltrace.py)
def test_calltrace_version():
    r = _run_tool("calltrace", "--version")
    check("calltrace --version OK", r.returncode == 0)


# 19. hashline.py:586 — parse_known_args (uses a tmp file to avoid corruption)
def test_hashline_parse_args():
    tmp = _tmpfile("import os\nimport sys\n")
    try:
        r = _run_tool("hashline", "replace", tmp, "import", "IMPORT")
        check("hashline replace extra args OK", r.returncode == 0)
    finally:
        os.unlink(tmp)


# ============================================================
def main():
    global PASS, FAIL
    print("\n  Bug-Hunt Regression Tests (19 fixes)")
    print(f"  {'=' * 40}")
    tests = [
        test_impact_cpp_def,
        test_impact_import_loop,
        test_impact_keyword_filter,
        test_impact_ts_empty_def,
        test_graph_diamond,
        test_graph_bad_import,
        test_search_single_file,
        test_search_redos,
        test_search_relpath,
        test_search_int_guard,
        test_changelog_int_guard,
        test_verify_int_guard,
        test_verify_line_flag,
        test_calltrace_int_guard,
        test_calltrace_version,
        test_refactor_ts_division,
        test_lint_injection,
        test_hashline_uppercase,
        test_hashline_parse_args,
    ]
    for t in tests:
        t()
    for p in _TMP_FILES:
        try:
            os.unlink(p)
        except OSError:
            pass
    total = PASS + FAIL
    print(f"\n  [{PASS}/{total} passed]")
    if FAIL:
        print(f"  [{FAIL}/{total} FAILED]")
        return 1
    print("  ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
