#!/usr/bin/env python3
"""Test suite for search.py — grep wrapper with rich output formatting."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from search import main, _match_glob


TEST_FILES = {
    "main.py": """\
def greet(name):
    print(f"Hello, {name}!")
    return True

def main():
    greet("world")

class Runner:
    def run(self):
        return main()
""",
    "utils.py": """\
import os
import sys

def helper():
    return 42

# TODO: optimize this
""",
    "data.json": """\
{"key": "value", "hello": "world"}
""",
    "sub/mod.py": """\
def sub_func():
    pass
""",
}


def _run(args):
    old_argv = sys.argv
    old_stdout = sys.stdout
    try:
        sys.argv = ["search"] + args
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


class TestMatchGlob(unittest.TestCase):
    def test_exact_extension(self):
        self.assertTrue(_match_glob("main.py", "*.py"))
        self.assertFalse(_match_glob("main.ts", "*.py"))

    def test_wildcard(self):
        self.assertTrue(_match_glob("test_main.py", "test_*"))
        self.assertTrue(_match_glob("test_main.py", "*main*"))

    def test_no_wildcard(self):
        self.assertTrue(_match_glob("main.py", ".py"))
        self.assertFalse(_match_glob("main.ts", ".py"))


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        for name, content in TEST_FILES.items():
            fpath = os.path.join(self.tmpdir, name)
            os.makedirs(os.path.dirname(fpath), exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_simple_pattern(self):
        code, out = _run(["def", self.tmpdir])
        self.assertEqual(code, 0)
        self.assertIn("match", out.lower())

    def test_nonexistent_path(self):
        code, out = _run(["foo", "/nonexistent/path"])
        self.assertEqual(code, 1)

    def test_no_matches(self):
        code, out = _run(["XYZZYX_NONEXISTENT_12345", self.tmpdir])
        self.assertEqual(code, 1)

    def test_json(self):
        code, out = _run(["--json", "def", self.tmpdir])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("results", data)
        self.assertGreaterEqual(data["count"], 1)

    def test_json_no_matches(self):
        code, out = _run(["--json", "XYZZYX_NONEXISTENT", self.tmpdir])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["count"], 0)

    def test_include_filter(self):
        code, out = _run(["--include", "*.py", "def", self.tmpdir])
        self.assertEqual(code, 0)
        self.assertNotIn("data.json", out)

    def test_multiple_matches(self):
        code, out = _run(["def", self.tmpdir])
        self.assertEqual(code, 0)
        # Should find def in main.py and sub/mod.py
        self.assertIn("main.py", out)

    def test_help(self):
        code, out = _run(["--help"])
        self.assertIn("search", out.lower())

    def test_version(self):
        code, out = _run(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("0.5.1", out)

    def test_unknown_flag(self):
        code, out = _run(["--bogus"])
        self.assertEqual(code, 1)

    def test_no_args(self):
        code, out = _run([])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
