#!/usr/bin/env python3
"""Test suite for graph.py — file-level dependency analyzer."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from graph import build_graph, find_tree, find_cycles, stats, main


TEST_PROJECT = {
    "main.py": "from utils import helper\nfrom models import User\n\ndef run():\n    u = User()\n    return helper(u)\n",
    "utils.py": "from models import Base\n\ndef helper(obj):\n    return str(obj)\n",
    "models.py": "class Base:\n    pass\n\nclass User(Base):\n    pass\n",
    "standalone.py": "import json\nimport os\n\ndef do_stuff():\n    return 42\n",
    "cli.py": "from main import run\n\ndef main():\n    print(run())\n",
}


def _run(args):
    old_argv = sys.argv
    old_stdout = sys.stdout
    try:
        sys.argv = ["graph"] + args
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


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestGraphBuild(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        for name, content in TEST_PROJECT.items():
            _write(os.path.join(self.tmpdir, name), content)
        self.graph = build_graph(self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_build_includes_all(self):
        names = set(self.graph["files"])
        for n in TEST_PROJECT:
            self.assertIn(n, names)

    def test_main_imports_utils_and_models(self):
        deps = self.graph["edges"].get("main.py", [])
        self.assertIn("utils.py", deps)
        self.assertIn("models.py", deps)

    def test_utils_imports_models(self):
        deps = self.graph["edges"].get("utils.py", [])
        self.assertIn("models.py", deps)

    def test_standalone_imports_none(self):
        deps = self.graph["edges"].get("standalone.py", [])
        self.assertEqual(len(deps), 0)

    def test_models_imported_by_main_and_utils(self):
        imps = self.graph["reverse"].get("models.py", [])
        self.assertIn("main.py", imps)
        self.assertIn("utils.py", imps)

    def test_no_cycles(self):
        cycles = find_cycles(self.graph)
        self.assertEqual(len(cycles), 0)

    def test_circular_detection(self):
        _write(os.path.join(self.tmpdir, "circ_a.py"), "from circ_b import bar\n")
        _write(os.path.join(self.tmpdir, "circ_b.py"), "from circ_a import foo\n")
        g2 = build_graph(self.tmpdir)
        cycles = find_cycles(g2)
        self.assertGreaterEqual(len(cycles), 1)

    def test_stats(self):
        s = stats(self.graph)
        self.assertIn("total_files", s)
        self.assertGreaterEqual(s["total_files"], 5)
        self.assertIn("total_edges", s)

    def test_tree(self):
        tree = find_tree(self.graph, "main.py")
        self.assertIsInstance(tree, list)
        self.assertGreaterEqual(len(tree), 1)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        for name, content in TEST_PROJECT.items():
            _write(os.path.join(self.tmpdir, name), content)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_stats_flag(self):
        code, out = _run(["--root=" + self.tmpdir, "--stats"])
        self.assertEqual(code, 0)
        self.assertIn("Files", out)

    def test_circular_flag(self):
        code, out = _run(["--root=" + self.tmpdir, "--circular"])
        self.assertEqual(code, 0)
        self.assertIn("none found", out)

    def test_file(self):
        code, out = _run(["--root=" + self.tmpdir, "main.py"])
        self.assertEqual(code, 0)
        self.assertIn("main.py", out)

    def test_nonexistent_file(self):
        code, out = _run(["--root=" + self.tmpdir, "nope.py"])
        self.assertEqual(code, 1)

    def test_unknown_flag(self):
        code, out = _run(["--root=" + self.tmpdir, "--bogus"])
        self.assertEqual(code, 1)

    def test_json(self):
        code, out = _run(["--root=" + self.tmpdir, "main.py", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("file", data)

    def test_tree(self):
        code, out = _run(["--root=" + self.tmpdir, "main.py", "--tree"])
        self.assertEqual(code, 0)
        self.assertIn("main.py", out)

    def test_version(self):
        code, out = _run(["--version"])
        self.assertEqual(code, 0)

    def test_help(self):
        code, out = _run(["--help"])
        self.assertIn("graph", out.lower())

    def test_out(self):
        code, out = _run(["--root=" + self.tmpdir, "main.py", "--out"])
        self.assertEqual(code, 0)
        self.assertIn("main.py", out)

    def test_in(self):
        code, out = _run(["--root=" + self.tmpdir, "models.py", "--in"])
        self.assertEqual(code, 0)
        self.assertIn("models.py", out)


if __name__ == "__main__":
    unittest.main()
