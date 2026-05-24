"""Integration test: run all tools on the codebase itself."""

import os
import subprocess
import sys
import json

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TOOLS_DIR)
SRC_DIR = os.path.join(BASE_DIR, "src")
PASS = 0
FAIL = 0


def _run(*args):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=BASE_DIR,
    )


def _tool(name, *args):
    return _run(os.path.join(SRC_DIR, f"{name}.py"), *args)


def check(desc, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK] {desc}")
    else:
        FAIL += 1
        print(f"  [FAIL] {desc}")


def test_impact():
    print("\n--- impact ---")
    r = _tool("impact", "def", "format_pretty")
    check("def finds format_pretty", r.returncode == 0 and "3 occurrences" in r.stdout)

    r = _tool("impact", "refs", "format_pretty")
    check("refs finds references", r.returncode == 0 and "occurrences" in r.stdout)

    r = _tool("impact", "tests", "format_pretty")
    check("tests finds test usages", r.returncode == 0 and "occurrences" in r.stdout)

    r = _tool("impact", "graph", "_walk_files")
    check("graph shows callers/callees", r.returncode == 0 and "calls" in r.stdout)

    r = _tool("impact", "IMPACT_N0N3X1ST3NT")
    check("missing symbol returns 1", r.returncode == 1)

    r = _tool("impact", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("impact", "--json", "def", "format_pretty")
    check("--json output is valid", r.returncode == 0)
    try:
        json.loads(r.stdout)
        check("--json is parseable", True)
    except json.JSONDecodeError:
        check("--json is parseable", False)


def test_graph():
    print("\n--- graph ---")
    r = _tool("graph", "--circular")
    check("no circular deps", r.returncode == 0 and "(none found)" in r.stdout)

    r = _tool("graph", "src/impact.py")
    check("graph file works", r.returncode == 0)

    r = _tool("graph", "src/impact.py", "--in")
    check("--in shows importers", r.returncode == 0)

    r = _tool("graph", "src/impact.py", "--out")
    check("--out shows imports", r.returncode == 0)

    r = _tool("graph", "--stats")
    check("--stats works", r.returncode == 0)

    r = _tool("graph", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)


def test_calltrace():
    print("\n--- calltrace ---")
    r = _tool("calltrace", "_walk_files", "--down", "-d", "2")
    check("trace down works", r.returncode == 0 and "_walk_files" in r.stdout)

    r = _tool("calltrace", "format_pretty", "--up")
    check("trace up works", r.returncode == 0)

    r = _tool("calltrace", "TRACE_N0N3X1ST3NT")
    check("missing symbol shows 0 callers", r.returncode == 0 and "callers]" in r.stdout)

    r = _tool("calltrace", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)


def test_changelog():
    print("\n--- changelog ---")
    r = _tool("changelog", "-n", "5")
    check("changelog -n 5 works", r.returncode == 0 and len(r.stdout) > 50)

    r = _tool("changelog", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("changelog", "-n", "abc")
    check("invalid -n returns 1", r.returncode == 1)


def test_refactor():
    print("\n--- refactor ---")
    r = _tool("refactor", "format_pretty", "format_pretty2", "--dry-run")
    check("dry-run finds occurrences", r.returncode == 0 and "occurrences" in r.stdout)

    r = _tool("refactor", "REFACTOR_N0N3X1ST3NT", "newname", "--dry-run")
    check("missing symbol returns 1", r.returncode == 1)

    r = _tool("refactor", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)


def test_verify():
    print("\n--- verify ---")
    r = _tool("verify", "src/impact.py")
    check("file summary works", r.returncode == 0 and "src/impact.py" in r.stdout)

    r = _tool("verify", "src/impact.py:2")
    check("file:line works", r.returncode == 0 and "impact" in r.stdout)

    r = _tool("verify", "src/impact.py", "--contains", "def format_pretty")
    check("--contains finds text", r.returncode == 0 and "found" in r.stdout)

    r = _tool("verify", "src/impact.py", "--not", "VERIFY_N0N3X1ST3NT")
    check("--not absent text", r.returncode == 0 and "[OK]" in r.stdout)

    r = _tool("verify", "tests/nonexistent_file.py")
    check("missing file returns 1", r.returncode == 1)

    r = _tool("verify", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)


def test_search():
    print("\n--- search ---")
    r = _tool("search", "--json", "def _walk_files")
    check("search finds pattern", r.returncode == 0)
    try:
        data = json.loads(r.stdout)
        check("search returns results", "results" in data and len(data["results"]) > 0)
    except json.JSONDecodeError:
        check("search returns results", False)

    r = _tool("search", "--json", "XYZZY_N0N3X1ST3NT_PLUGH", "src/impact.py")
    check("no match returns empty", r.returncode == 0)
    try:
        data = json.loads(r.stdout)
        check("empty results is valid", "results" in data and len(data["results"]) == 0)
    except json.JSONDecodeError:
        check("empty results is valid", False)

    r = _tool("search", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)


def test_lint():
    print("\n--- lint ---")
    r = _tool("lint", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("lint", "--help")
    check("--help works", r.returncode == 0)


def test_hashline():
    print("\n--- hashline ---")
    r = _tool("hashline", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("hashline", "check", "src/impact.py")
    check("hashline check works", r.returncode == 0)


def test_health():
    print("\n--- health ---")
    r = _tool("health", "--quick")
    check("health quick shows metrics", r.returncode == 0 and "files:" in r.stdout)

    r = _tool("health", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("health", "--check", "--quick")
    check("--check mode works", r.returncode in (0, 1))


def test_snapshot():
    print("\n--- snapshot ---")
    r = _tool("snapshot", "--show")
    check("snapshot shows git info", r.returncode == 0 and "Git" in r.stdout)

    r = _tool("snapshot", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("snapshot")
    check("snapshot saves file", r.returncode == 0 and "Snapshot saved" in r.stdout)


def test_todo():
    print("\n--- todo ---")
    r = _tool("todo")
    check("todo finds markers", r.returncode == 0)

    r = _tool("todo", "--count")
    check("todo --count works", r.returncode == 0 and "Total:" in r.stdout)

    r = _tool("todo", "--json")
    check("todo --json works", r.returncode == 0)
    try:
        json.loads(r.stdout)
        check("todo --json is valid", True)
    except json.JSONDecodeError:
        check("todo --json is valid", False)

    r = _tool("todo", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)


def test_tags():
    print("\n--- tags ---")
    r = _tool("tags", "--stats")
    check("tags --stats works", r.returncode == 0 and "tags" in r.stdout)

    r = _tool("tags", "ImpactAnalyzer")
    check("tags lookup works", r.returncode == 0 and "ImpactAnalyzer" in r.stdout)

    r = _tool("tags", "N0N3X1STENT_SYM")
    check("tags missing symbol returns 1", r.returncode == 1)

    r = _tool("tags", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)


def test_check():
    print("\n--- check ---")
    r = _tool("check", "--quick")
    check("check quick passes", r.returncode == 0 and "All checks passed" in r.stdout)

    r = _tool("check", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("check", "-h")
    check("--help shows usage", r.returncode == 0 and "lint" in r.stdout.lower())


def test_audit():
    print("\n--- audit ---")
    r = _tool("audit", ".")
    check("audit scans directory", r.returncode in (0, 1))
    check("audit finds secrets in self-test", "Findings:" in r.stdout)

    r = _tool("audit", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("audit", "-h")
    check("--help shows usage", r.returncode == 0 and "scanner" in r.stdout.lower())

    r = _tool("audit", "--json", ".")
    import json

    if r.returncode in (0, 1) and r.stdout.strip():
        try:
            data = json.loads(r.stdout)
            check("--json output is valid", "status" in data and "findings" in data)
        except json.JSONDecodeError:
            check("--json output is valid", False)
    else:
        check("--json output is valid", False)


def test_fmt():
    print("\n--- fmt ---")
    r = _tool("fmt", "--ruff", "--check")
    check("fmt runs (ruff available)", r.returncode in (0, 1))

    r = _tool("fmt", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("fmt", "-h")
    check("--help shows usage", r.returncode == 0 and "format" in r.stdout.lower())


def test_churn():
    print("\n--- churn ---")
    r = _tool("churn", "-n", "5")
    check("churn top 5 works", r.returncode == 0 and "x" in r.stdout)

    r = _tool("churn", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("churn", "-h")
    check("--help shows usage", r.returncode == 0 and "churn" in r.stdout.lower())


def test_report():
    print("\n--- report ---")
    r = _tool("report", "--quick")
    check("report quick works", r.returncode in (0, 1) and "Health Report" in r.stdout)

    r = _tool("report", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("report", "-h")
    check("--help shows usage", r.returncode == 0 and "report" in r.stdout.lower())


def test_ghost():
    print("\n--- ghost ---")
    r = _tool("ghost", "--lang", "py")
    check("ghost scans python", r.returncode == 0)

    r = _tool("ghost", "--version")
    check("--version shows 0.5.0", "0.5.2" in r.stdout)

    r = _tool("ghost", "-h")
    check("--help shows usage", r.returncode == 0 and "dead" in r.stdout.lower())


def main():
    print(f"Smoke test: opencode-tools v0.5.2 self-test")
    print(f"Tools dir: {SRC_DIR}")
    print(f"Python: {sys.executable}")

    tests = [
        test_impact,
        test_graph,
        test_calltrace,
        test_changelog,
        test_refactor,
        test_verify,
        test_search,
        test_lint,
        test_hashline,
        test_health,
        test_snapshot,
        test_todo,
        test_tags,
        test_check,
        test_audit,
        test_fmt,
        test_churn,
        test_report,
        test_ghost,
    ]
    for t in tests:
        t()

    total = PASS + FAIL
    print(f"\n{'=' * 40}")
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
