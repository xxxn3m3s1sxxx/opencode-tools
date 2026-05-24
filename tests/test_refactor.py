#!/usr/bin/env python3
"""Test suite for refactor.py — AST-based symbol renaming."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from refactor import (
    _walk_files,
    _find_ast_references,
    _find_refs_in_file,
    _apply_rename,
    SOURCE_EXTS,
    main,
)


SAMPLE_PY = """\
import os
from sys import path

VERSION = "0.5.2"

def greet(name):
    print(f"Hello, {name}!")
    return True

class Runner:
    def run(self):
        return greet("world")

def main():
    r = Runner()
    print(r.run())

if __name__ == "__main__":
    pass
"""

SAMPLE_REFACTOR = """\
import os
from sys import path

APP_VERSION = "0.5.2"

def hello(name):
    print(f"Hello, {name}!")
    return True

class Runner:
    def run(self):
        return hello("world")

def main():
    r = Runner()
    print(r.run())

if __name__ == "__main__":
    pass
"""


def _run(args):
    old_argv = sys.argv
    old_stdout = sys.stdout
    try:
        sys.argv = ["refactor"] + args
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


class TestWalkFiles(unittest.TestCase):
    def test_finds_py_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            for f in ["a.py", "b.py", "c.txt", "d.pyi"]:
                open(os.path.join(tmp, f), "w").close()
            os.makedirs(os.path.join(tmp, "__pycache__"), exist_ok=True)
            open(os.path.join(tmp, "__pycache__", "ignore.py"), "w").close()
            files = _walk_files(tmp, SOURCE_EXTS)
            names = [os.path.basename(f) for f in files]
            self.assertIn("a.py", names)
            self.assertIn("b.py", names)
            self.assertIn("d.pyi", names)
            self.assertNotIn("c.txt", names)
            self.assertNotIn("ignore.py", names)


class TestFindRefs(unittest.TestCase):
    def _get_refs(self, symbol):
        tree = __import__("ast").parse(SAMPLE_PY)
        return _find_ast_references(tree, symbol, SAMPLE_PY.split("\n"))

    def test_find_function_def(self):
        refs = self._get_refs("greet")
        self.assertGreaterEqual(len(refs), 1)
        kinds = [r["kind"] for r in refs]
        self.assertIn("definition", kinds)

    def test_find_references(self):
        refs = self._get_refs("Runner")
        self.assertGreaterEqual(len(refs), 1)
        kinds = [r["kind"] for r in refs]
        self.assertIn("definition", kinds)

    def test_no_match(self):
        refs = self._get_refs("NonExistentSymbol")
        self.assertEqual(len(refs), 0)

    def test_find_variable(self):
        refs = self._get_refs("VERSION")
        self.assertGreaterEqual(len(refs), 1)

    def test_import_refs(self):
        refs = self._get_refs("path")
        self.assertGreaterEqual(len(refs), 1)


class TestFindRefsInFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        self.tmp.write(SAMPLE_PY)
        self.tmp.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_find_greet(self):
        content, refs = _find_refs_in_file(self.tmp.name, "greet")
        self.assertIsNotNone(content)
        self.assertGreaterEqual(len(refs), 2)  # def + call

    def test_find_nonexistent(self):
        content, refs = _find_refs_in_file(self.tmp.name, "NonExistent")
        self.assertEqual(len(refs), 0)

    def test_missing_file(self):
        content, refs = _find_refs_in_file("/nonexistent/file.py", "foo")
        self.assertIsNone(content)
        self.assertEqual(len(refs), 0)


class TestApplyRename(unittest.TestCase):
    def test_rename_greet(self):
        tree = __import__("ast").parse(SAMPLE_PY)
        source_lines = SAMPLE_PY.split("\n")
        refs = _find_ast_references(tree, "greet", source_lines)
        result = _apply_rename(SAMPLE_PY, refs, "greet", "hello")
        self.assertIn("def hello", result)
        self.assertIn('hello("world")', result)
        self.assertNotIn("def greet", result)

    def test_rename_runner(self):
        tree = __import__("ast").parse(SAMPLE_PY)
        source_lines = SAMPLE_PY.split("\n")
        refs = _find_ast_references(tree, "Runner", source_lines)
        result = _apply_rename(SAMPLE_PY, refs, "Runner", "Athlete")
        self.assertIn("class Athlete", result)
        self.assertIn("r = Athlete()", result)
        self.assertNotIn("class Runner", result)
        self.assertNotIn("Runner()", result)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pyfile = os.path.join(self.tmpdir, "test.py")
        with open(self.pyfile, "w", encoding="utf-8") as f:
            f.write(SAMPLE_PY)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dry_run(self):
        code, out = _run(["--root=" + self.tmpdir, "greet", "hello", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("greet", out)
        self.assertIn("hello", out)

    def test_actual_rename(self):
        code, out = _run(["--root=" + self.tmpdir, "greet", "hello"])
        self.assertEqual(code, 0)
        self.assertIn("Updated", out) or self.assertIn("renamed", out.lower())
        # Verify file changed
        with open(self.pyfile, "r") as f:
            content = f.read()
        self.assertIn("def hello", content)
        self.assertNotIn("def greet", content)

    def test_json(self):
        code, out = _run(["--root=" + self.tmpdir, "greet", "hello", "--dry-run", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("old_name", data)
        self.assertEqual(data["old_name"], "greet")

    def test_identical_names(self):
        code, out = _run(["--root=" + self.tmpdir, "foo", "foo"])
        self.assertEqual(code, 1)

    def test_no_match(self):
        code, out = _run(["--root=" + self.tmpdir, "NonExistent", "Bar", "--dry-run"])
        self.assertEqual(code, 1)

    def test_file_flag(self):
        code, out = _run(["--root=" + self.tmpdir, "greet", "hello", "--file", self.pyfile, "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("greet", out)

    def test_help(self):
        code, out = _run(["--help"])
        self.assertIn("refactor", out.lower())

    def test_version(self):
        code, out = _run(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("0.5.2", out)

    def test_nonexistent_file(self):
        code, out = _run(["foo", "bar", "--file", "/nonexistent.py"])
        self.assertEqual(code, 1)

    def test_no_args(self):
        code, out = _run([])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
