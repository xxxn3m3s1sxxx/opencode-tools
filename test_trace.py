#!/usr/bin/env python3
"""Test suite for calltrace.py — recursive call chain analyzer."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calltrace import (
    _find_enclosing_function,
    _grep_occurrences,
    _find_callers,
    _find_call_chain,
    format_pretty,
    format_json,
    main,
)


def _run(args):
    """Run main() with args, return (exit_code, stdout)."""
    old_argv = sys.argv
    old_stdout = sys.stdout
    try:
        sys.argv = ["calltrace"] + args
        from io import StringIO

        sys.stdout = StringIO()
        try:
            exit_code = main()
        except SystemExit as e:
            exit_code = e.code or 0
        output = sys.stdout.getvalue()
        return exit_code, output
    finally:
        sys.stdout = old_stdout
        sys.argv = old_argv


TEST_PY = """
def top():
    return middle()

def middle():
    return bottom()

def bottom():
    return 42

def standalone():
    pass

class Runner:
    def run(self):
        return top()
"""


class TestFindEnclosingFunction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        self.tmp.write(TEST_PY)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_encloses_middle(self):
        """Line in middle() body should return 'middle'."""
        result = _find_enclosing_function(self.path, 6)
        self.assertEqual(result, "middle")

    def test_encloses_top(self):
        """Line in top() body should return 'top'."""
        result = _find_enclosing_function(self.path, 2)
        self.assertEqual(result, "top")

    def test_encloses_standalone(self):
        result = _find_enclosing_function(self.path, 11)
        self.assertEqual(result, "standalone")

    def test_encloses_class_method(self):
        """Line inside Runner.run should return 'run'."""
        result = _find_enclosing_function(self.path, 16)
        self.assertEqual(result, "run")

    def test_module_level(self):
        """Line at module level (not in any function) should return None."""
        result = _find_enclosing_function(self.path, 1)
        self.assertIsNone(result)


class TestGrepOccurrences(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        self.tmp.write(TEST_PY)
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_find_top(self):
        occs = _grep_occurrences(self.path, "top")
        self.assertGreaterEqual(len(occs), 2)  # defined + called

    def test_find_standalone(self):
        occs = _grep_occurrences(self.path, "standalone")
        self.assertEqual(len(occs), 1)  # defined only

    def test_not_found(self):
        occs = _grep_occurrences(self.path, "nonexistent")
        self.assertEqual(len(occs), 0)


class TestCallChain(unittest.TestCase):
    """Integration test using a temp project with known call relationships."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "mod.py"), "w", encoding="utf-8") as f:
            f.write("""
def top():
    return middle()

def middle():
    return bottom()

def bottom():
    return 42

def standalone():
    pass

class Runner:
    def run(self):
        return top()
""")
        with open(os.path.join(self.tmpdir, "test_mod.py"), "w", encoding="utf-8") as f:
            f.write("""
from mod import top

def test_it():
    result = top()
    assert result == 42
""")
        sys.path.insert(0, self.tmpdir)
        from impact import ImpactAnalyzer

        self.analyzer = ImpactAnalyzer(self.tmpdir)

    def tearDown(self):
        import shutil

        sys.path.pop(0)
        shutil.rmtree(self.tmpdir)

    def test_callers_of_bottom(self):
        """bottom is called by middle."""
        callers = _find_callers(self.analyzer, "bottom", 1, "all")
        caller_names = set(c["caller"] for c in callers)
        self.assertIn("middle", caller_names)

    def test_callers_of_middle(self):
        """middle is called by top."""
        callers = _find_callers(self.analyzer, "middle", 1, "all")
        caller_names = set(c["caller"] for c in callers)
        self.assertIn("top", caller_names)

    def test_callers_of_top(self):
        """top is called by Runner.run and test_it."""
        callers = _find_callers(self.analyzer, "top", 1, "all")
        caller_names = set(c["caller"] for c in callers)
        self.assertIn("run", caller_names)
        self.assertIn("test_it", caller_names)

    def test_no_callers_for_standalone(self):
        callers = _find_callers(self.analyzer, "standalone", 1, "all")
        self.assertEqual(len(callers), 0)

    def test_callees_of_top(self):
        """top calls middle."""
        chain = _find_call_chain(self.analyzer, "top", 1, "all")
        if chain:
            top_entry = chain[0]
            self.assertIn("middle", top_entry.get("callees", []))

    def test_callees_of_standalone(self):
        """standalone calls nothing."""
        chain = _find_call_chain(self.analyzer, "standalone", 1, "all")
        self.assertEqual(len(chain), 0)

    def test_depth_2(self):
        """With depth 2, trace from top should find top->middle->bottom."""
        chain = _find_call_chain(self.analyzer, "top", 2, "all")
        symbols_in_chain = [entry["symbol"] for entry in chain]
        self.assertIn("top", symbols_in_chain)
        self.assertIn("middle", symbols_in_chain)

    def test_depth_2_callers(self):
        """With depth 2, callers of bottom should include middle AND top."""
        callers = _find_callers(self.analyzer, "bottom", 2, "all")
        caller_names = set(c["caller"] for c in callers)
        self.assertIn("middle", caller_names)
        self.assertIn("top", caller_names)


class TestFormatters(unittest.TestCase):
    def test_pretty_found(self):
        out = format_pretty(
            "test_fn",
            [{"caller": "caller1", "callee": "test_fn", "file": "/a/b.py", "line": 10, "context": ""}],
            [],
            "/root",
            1,
        )
        self.assertIn("test_fn", out)
        self.assertIn("[callers]", out)

    def test_pretty_not_found(self):
        out = format_pretty("nope", [], [], "/root", 2)
        self.assertIn("no call chain found", out)

    def test_json(self):
        js = format_json(
            "test_fn",
            [{"caller": "caller1", "callee": "test_fn", "file": "/a/b.py", "line": 10, "context": ""}],
            [],
            "/root",
            2,
        )
        data = json.loads(js)
        self.assertEqual(data["symbol"], "test_fn")
        self.assertEqual(len(data["callers"]), 1)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "mod.py"), "w", encoding="utf-8") as f:
            f.write("""
def foo():
    return bar()

def bar():
    return baz()

def baz():
    return 42
""")
        with open(os.path.join(self.tmpdir, "test_mod.py"), "w", encoding="utf-8") as f:
            f.write("""
from mod import bar

def test_bar():
    assert bar() == 42
""")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_default(self):
        code, out = _run(["--root=" + self.tmpdir, "bar"])
        self.assertEqual(code, 0)

    def test_viz(self):
        code, out = _run(["--root=" + self.tmpdir, "bar", "--viz"])
        self.assertEqual(code, 0)
        self.assertIn("└──", out)

    def test_up(self):
        code, out = _run(["--root=" + self.tmpdir, "bar", "--up"])
        self.assertEqual(code, 0)
        self.assertIn("[callers]", out)

    def test_down(self):
        code, out = _run(["--root=" + self.tmpdir, "bar", "--down"])
        self.assertEqual(code, 0)
        self.assertIn("[chain]", out)

    def test_depth_flag(self):
        code, out = _run(["--root=" + self.tmpdir, "foo", "-d", "2"])
        self.assertEqual(code, 0)

    def test_json(self):
        code, out = _run(["--root=" + self.tmpdir, "bar", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("symbol", data)

    def test_version(self):
        code, out = _run(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("0.5.1", out)

    def test_nonexistent_symbol(self):
        code, out = _run(["--root=" + self.tmpdir, "nonexistent"])
        self.assertEqual(code, 1)

    def test_unknown_flag(self):
        code, out = _run(["--root=" + self.tmpdir, "bar", "--bogus"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown flag", out)


if __name__ == "__main__":
    unittest.main()
