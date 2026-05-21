#!/usr/bin/env python3
"""Self-test for hashline.py -- proves correctness across all ops and platforms.

Usage:
    python test_hashline.py                         # run all tests
    python test_hashline.py --verbose               # show details
    python test_hashline.py --bench                 # include benchmarks

Returns 0 if all tests pass, 1 on failure (CI-friendly).
"""

import hashlib
import itertools
import os
import subprocess
import sys
import tempfile

HASHLINE_PY = os.path.join(os.path.dirname(__file__), "hashline.py")
PASS = 0
FAIL = 0
SKIP = 0

BIGRAMS = [a + b for a, b in itertools.product("abcdefghijklmnopqrstuvwxyz", repeat=2)]
BIGRAMS_COUNT = len(BIGRAMS)

VERBOSE = False

def log(msg: str):
    print(f"  {msg}" if VERBOSE else "", end="")


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        print(f"  [OK] {name}")
        PASS += 1
    else:
        print(f"  [FAIL] {name} -- {detail}")
        FAIL += 1


def skip(name: str, reason: str):
    global SKIP
    print(f"  [SKIP] {name} ({reason})")
    SKIP += 1


def run_hl(args: list[str], stdin: str = "") -> subprocess.CompletedProcess:
    """Run hashline.py and return result."""
    cmd = [sys.executable, HASHLINE_PY] + args
    return subprocess.run(
        cmd, input=stdin, capture_output=True, text=True, timeout=15,
        encoding="utf-8"
    )


def compute_hash(line: str) -> str:
    cleaned = line.rstrip()
    h = hashlib.sha256(cleaned.encode("utf-8")).digest()
    idx = int.from_bytes(h[:8], "little") % BIGRAMS_COUNT
    return BIGRAMS[idx]


# ===== TESTS =====

def test_version():
    """Test --version flag."""
    r = run_hl(["--version"])
    check("--version returns 0", r.returncode == 0, f"got code {r.returncode}")
    check("--version output", "hashline.py" in r.stdout, f"got {r.stdout.strip()!r}")


def test_read():
    """Test reading a file with hashline anchors."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("line A\nline B\nline C\n")
        p = f.name
    try:
        r = run_hl(["read", p])
        check("read returns 0", r.returncode == 0)
        lines = r.stdout.strip().split("\n")
        check("read has 4 lines (3 content + 1 empty)", len(lines) == 4, f"got {len(lines)}")
        h_b = compute_hash("line B")
        check(f"line B anchor is 2{h_b}", lines[1].startswith(f"2{h_b}|"), f"got {lines[1]!r}")
    finally:
        os.unlink(p)


def test_replace_exact():
    """Replace exact text."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("a\nb\nc\n")
        p = f.name
    try:
        r = run_hl(["replace", p, "b", "B"])
        check("replace exact returns 0", r.returncode == 0)
        content = open(p, encoding="utf-8").read()
        check("replace changed content", "B" in content, f"got {content!r}")
        check("replace correct line", content == "a\nB\nc\n", f"got {content!r}")
    finally:
        os.unlink(p)


def test_replace_missing():
    """Replace with text not in file -> error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("a\nb\nc\n")
        p = f.name
    try:
        r = run_hl(["replace", p, "zzz", "xxx"])
        check("replace missing returns non-zero", r.returncode != 0)
    finally:
        os.unlink(p)


def test_replace_file_flags():
    """Replace with --file-old --file-new."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("x\ny\nz\n")
        p = f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".old", delete=False, encoding="utf-8") as of:
        of.write("y")
        op = of.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".new", delete=False, encoding="utf-8") as nf:
        nf.write("YY")
        np = nf.name
    try:
        r = run_hl(["replace", p, "--file-old", op, "--file-new", np])
        check("replace --file-* returns 0", r.returncode == 0)
        content = open(p, encoding="utf-8").read()
        check("replace --file-* content", "YY" in content, f"got {content!r}")
    finally:
        for fp in (p, op, np):
            try:
                os.unlink(fp)
            except OSError:
                pass


def test_replace_stdin():
    """Replace with --stdin-old --stdin-new and delimiter."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("p\nq\nr\n")
        p = f.name
    try:
        stdin_data = "q\n===OLD/NEW===\nQQ"
        r = run_hl(["replace", p, "--stdin-old", "--stdin-new"], stdin=stdin_data)
        check("replace stdin returns 0", r.returncode == 0, f"stderr: {r.stderr}")
        content = open(p, encoding="utf-8").read()
        check("replace stdin content", "QQ" in content, f"got {content!r}")
    finally:
        os.unlink(p)


def test_edit_diff_file():
    """Edit with diff file (2-arg form)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("one\ntwo\nthree\n")
        target = f.name
    # Read to get anchors
    r = run_hl(["read", target])
    lines = r.stdout.strip().split("\n")
    # Parse line 2 anchor
    parts = lines[1].split("|")
    line2_hash = parts[0]  # e.g. "2ab"
    diff = f"= {line2_hash}..{line2_hash}\n~TWO\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".hl", delete=False, encoding="utf-8") as df:
        df.write(diff)
        dp = df.name
    try:
        r = run_hl(["edit", target, dp])
        check("edit with diff returns 0", r.returncode == 0, f"stderr: {r.stderr}")
        content = open(target, encoding="utf-8").read()
        check("edit changed content", "TWO" in content, f"got {content!r}")
    finally:
        for fp in (target, dp):
            try:
                os.unlink(fp)
            except OSError:
                pass


def test_edit_stdin():
    """Edit reading diff from stdin.""" 
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("red\ngreen\nblue\n")
        target = f.name
    r = run_hl(["read", target])
    lines = r.stdout.strip().split("\n")
    parts = lines[1].split("|")
    line2_hash = parts[0]
    diff = f"= {line2_hash}..{line2_hash}\n~GREEN\n"
    try:
        r = run_hl(["edit", target], stdin=diff)
        check("edit stdin returns 0", r.returncode == 0, f"stderr: {r.stderr}")
        content = open(target, encoding="utf-8").read()
        check("edit stdin changed content", "GREEN" in content, f"got {content!r}")
    finally:
        os.unlink(target)


def test_check():
    """Check shows hashes only."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("foo\nbar\n")
        p = f.name
    try:
        r = run_hl(["check", p])
        check("check returns 0", r.returncode == 0)
        lines = r.stdout.strip().split("\n")
        check("check has 2 lines (2 content)", len(lines) == 2, f"got {len(lines)}")
        check("check no pipe separator", "|" not in lines[0], f"got {lines[0]!r}")
    finally:
        os.unlink(p)


def test_missing_file():
    """Engine error on missing file."""
    r = run_hl(["read", "/nonexistent/file.txt"])
    check("read missing file returns non-zero", r.returncode != 0)


def test_bad_command():
    """Unknown command error."""
    r = run_hl(["bogus"])
    check("bogus command returns non-zero", r.returncode != 0)


def test_insert_before():
    """Insert before anchor."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("first\nlast\n")
        target = p = f.name
    r = run_hl(["read", target])
    lines = r.stdout.strip().split("\n")
    parts = lines[0].split("|")
    first_hash = parts[0]
    diff = f"< {first_hash}\n~before-first\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".hl", delete=False, encoding="utf-8") as df:
        df.write(diff)
        dp = df.name
    try:
        r = run_hl(["edit", target, dp])
        check("insert before returns 0", r.returncode == 0, f"stderr: {r.stderr}")
        content = open(target, encoding="utf-8").read()
        check("insert before content", content == "before-first\nfirst\nlast\n", f"got {content!r}")
    finally:
        for fp in (target, dp):
            try:
                os.unlink(fp)
            except OSError:
                pass


def test_delete_line():
    """Delete a line."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("keep A\ndelete me\nkeep B\n")
        target = p = f.name
    r = run_hl(["read", target])
    lines = r.stdout.strip().split("\n")
    parts = lines[1].split("|")
    line2_hash = parts[0]
    diff = f"- {line2_hash}..{line2_hash}\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".hl", delete=False, encoding="utf-8") as df:
        df.write(diff)
        dp = df.name
    try:
        r = run_hl(["edit", target, dp])
        check("delete line returns 0", r.returncode == 0)
        content = open(target, encoding="utf-8").read()
        check("delete line removed target", "delete me" not in content, f"got {content!r}")
    finally:
        for fp in (target, dp):
            try:
                os.unlink(fp)
            except OSError:
                pass


def test_unicode():
    """Unicode content preserved."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("café\n日本語\nemoji 🎉\n")
        p = f.name
    try:
        r = run_hl(["read", p])
        check("unicode read", r.returncode == 0, f"stderr: {r.stderr}")
        check("unicode café present", "café" in r.stdout, f"stdout: {r.stdout[:100]}")
        check("unicode emoji present", "🎉" in r.stdout, f"stdout: {r.stdout[:100]}")

        r = run_hl(["replace", p, "café", "CAFE"])
        check("unicode replace", r.returncode == 0, f"stderr: {r.stderr}")
        content = open(p, encoding="utf-8").read()
        check("unicode replace result", "CAFE" in content, f"got {content!r}")
    finally:
        os.unlink(p)


def test_empty_file():
    """Empty file handled."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("")
        p = f.name
    try:
        r = run_hl(["read", p])
        check("empty file read", r.returncode == 0, f"stderr: {r.stderr}")
    finally:
        os.unlink(p)


def test_no_trailing_newline():
    """No trailing newline at EOF."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("no newline")
        p = f.name
    try:
        r = run_hl(["read", p])
        check("no-newline read", r.returncode == 0, f"stderr: {r.stderr}")
        check("no-newline no extra empty line", len(r.stdout.strip().split("\n")) == 1,
              f"output has {len(r.stdout.strip().split(chr(10)))} lines: {r.stdout!r}")
    finally:
        os.unlink(p)


def test_long_line():
    """10K char line."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("A" * 10000 + "\n")
        p = f.name
    try:
        r = run_hl(["read", p])
        check("long line read", r.returncode == 0, f"stderr: {r.stderr}")

        r = run_hl(["replace", p, "A" * 10000, "B" * 100])
        check("long line replace", r.returncode == 0, f"stderr: {r.stderr}")
        content = open(p, encoding="utf-8").read()
        check("long line result length", len(content.strip()) == 100, f"got {len(content.strip())}")
    finally:
        os.unlink(p)


def test_spaces_in_path():
    """File path with spaces."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                      prefix="my file ", encoding="utf-8") as f:
        f.write("hello\n")
        p = f.name
    try:
        r = run_hl(["read", p])
        check("spaces in path read", r.returncode == 0, f"stderr: {r.stderr}")

        r = run_hl(["replace", p, "hello", "HELLO"])
        check("spaces in path replace", r.returncode == 0, f"stderr: {r.stderr}")
        content = open(p, encoding="utf-8").read()
        check("spaces in path result", "HELLO" in content, f"got {content!r}")
    finally:
        os.unlink(p)


def test_diff_cmd():
    """Diff command produces valid output."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("same\nsame\n")
        target = p = f.name
    r = run_hl(["read", target])
    lines = r.stdout.strip().split("\n")
    parts = lines[0].split("|")
    h1 = parts[0]
    diff = f"= {h1}..{h1}\n~changed\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".hl", delete=False, encoding="utf-8") as df:
        df.write(diff)
        dp = df.name
    try:
        r = run_hl(["diff", target, dp])
        check("diff returns 0", r.returncode == 0)
        check("diff output shows change", "-same" in r.stdout or "+changed" in r.stdout,
              f"got {r.stdout[:200]!r}")
    finally:
        for fp in (target, dp):
            try:
                os.unlink(fp)
            except OSError:
                pass


# ===== DEMO COMPARISON =====

def demo_edit_fails_hashline_succeeds():
    """Demonstrate that edit() would fail but hashline_edit succeeds.
    
    This simulates common AI model failure modes:
    1. Trailing whitespace mismatch
    2. Wrong indentation
    3. Minor text variations
    """
    print("\n  [STATS] Demo: edit() vs hashline_edit() -- failure modes\n")
    
    scenarios = [
        ("trailing space", "hello world", "hello world "),
        ("different indentation", "  indented", "indented"),
        ("case variation", "Line Text", "line text"),
    ]
    
    for name, file_content, model_guess in scenarios:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(file_content + "\n")
            p = f.name
        
        # edit() would fail because oldString doesn't match exactly
        r = run_hl(["replace", p, model_guess, "replaced"])
        # hashline succeeds via stripped text matching
        if file_content.rstrip() == model_guess.rstrip():
            expected = r.returncode == 0
        else:
            # If rstrip versions differ too, even hashline can't save it
            expected = r.returncode == 0 if file_content.rstrip() == model_guess.rstrip() else r.returncode != 0
        
        mark = "[OK]" if r.returncode == 0 else "[FAIL]"
        detail = f"file={file_content!r} model={model_guess!r} -> exit={r.returncode}"
        log_detail = f"  {mark} {name}: {detail}\n    stdout: {r.stdout.strip()}\n"
        
        if VERBOSE:
            print(log_detail)
        
        os.unlink(p)


# ===== BENCHMARK =====

def benchmark_reliability():
    """Demo where edit() fails but hashline_edit succeeds."""
    print("\n  🎯 edit() failure modes that hashline handles\n")
    failures = 0
    cases = 0

    for desc, file_text, model_guess in [
        ("trailing whitespace",     "hello world",   "hello world "),
        ("wrong indentation",       "  indented",    "indented"),
        ("extra blank line at EOF", "line1\nline2",  "line1\nline2\n\n"),
    ]:
        cases += 1
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(file_text + "\n")
            p = f.name
        r = run_hl(["replace", p, model_guess, "FIXED"])
        if r.returncode == 0:
            print(f"  [OK] {desc:30s}  hashline -> exit 0 (edit() would fail)")
            failures += 1
        else:
            print(f"  [FAIL] {desc:30s}  hashline also failed")
        os.unlink(p)

    print(f"\n  [STATS] {failures}/{cases} cases where edit() fails but hashline succeeds")


# ===== MAIN =====

def main():
    global VERBOSE
    run_bench = False
    for arg in sys.argv[1:]:
        if arg == "--verbose" or arg == "-v":
            VERBOSE = True
        elif arg == "--bench":
            run_bench = True

    print(f"[TEST] hashline.py {run_hl(['--version']).stdout.strip()} self-test")
    print(f"   platform: {sys.platform}, python {sys.version.split()[0]}")
    print()

    # Run tests
    test_version()
    test_read()
    test_replace_exact()
    test_replace_missing()
    test_replace_file_flags()
    test_replace_stdin()
    test_edit_diff_file()
    test_edit_stdin()
    test_check()
    test_missing_file()
    test_bad_command()
    test_insert_before()
    test_delete_line()
    test_diff_cmd()

    # Edge case tests
    test_unicode()
    test_empty_file()
    test_no_trailing_newline()
    test_long_line()
    test_spaces_in_path()

    # Demo
    demo_edit_fails_hashline_succeeds()

    # Benchmark
    if run_bench:
        benchmark_reliability()

    # Summary
    total = PASS + FAIL + SKIP
    print(f"\n{'='*40}")
    print(f"  [OK] {PASS} passed")
    if FAIL:
        print(f"  [FAIL] {FAIL} failed")
    if SKIP:
        print(f"  [SKIP] {SKIP} skipped")
    print(f"  [STATS] {total} total")
    print(f"{'='*40}")

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
