#!/usr/bin/env python3
"""Test suite for check, audit, fmt, churn, report, ghost — new tools."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def _run(tool: str, *args: str) -> subprocess.CompletedProcess[str]:
    py = os.path.join(TOOLS_DIR, f"{tool}.py")
    return subprocess.run(
        [sys.executable, py, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=TOOLS_DIR,
        timeout=60,
    )


class TestCheck(unittest.TestCase):
    def test_version(self):
        r = _run("check", "--version")
        self.assertIn("0.5.1", r.stdout)

    def test_help(self):
        r = _run("check", "-h")
        self.assertEqual(0, r.returncode)
        self.assertIn("lint", r.stdout.lower())

    def test_json(self):
        r = _run("check", "--quick", "--json")
        out = json.loads(r.stdout)
        self.assertIsInstance(out, list)


class TestAudit(unittest.TestCase):
    def test_version(self):
        r = _run("audit", "--version")
        self.assertIn("0.5.1", r.stdout)

    def test_help(self):
        r = _run("audit", "-h")
        self.assertEqual(0, r.returncode)
        self.assertIn("scanner", r.stdout.lower())

    def test_scan_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("audit", "--root", tmp)
            self.assertIn("No secrets found", r.stdout)

    def test_json(self):
        r = _run("audit", "--json", ".")
        try:
            data = json.loads(r.stdout)
            self.assertIn("status", data)
            self.assertIn("findings", data)
            self.assertIn("total", data)
        except json.JSONDecodeError:
            self.fail("invalid json")

    def test_quiet(self):
        r = _run("audit", "--quiet", ".")
        self.assertIn("!!!", r.stdout + "!!")

    def test_missing_root(self):
        r = _run("audit", "--root", "__nonexistent__")
        self.assertNotEqual(0, r.returncode)


class TestFmt(unittest.TestCase):
    def test_version(self):
        r = _run("fmt", "--version")
        self.assertIn("0.5.1", r.stdout)

    def test_help(self):
        r = _run("fmt", "-h")
        self.assertEqual(0, r.returncode)
        self.assertIn("format", r.stdout.lower())

    def test_json(self):
        r = _run("fmt", "--ruff", "--check", "--json")
        try:
            data = json.loads(r.stdout)
            self.assertIsInstance(data, list)
        except json.JSONDecodeError:
            self.fail("invalid json")

    def test_prettier_not_required(self):
        r = _run("fmt", "--ruff")
        self.assertIn("ruff", r.stdout.lower())

    def test_missing_root(self):
        r = _run("fmt", "--root", "__nonexistent__")
        self.assertNotEqual(0, r.returncode)


class TestChurn(unittest.TestCase):
    def test_version(self):
        r = _run("churn", "--version")
        self.assertIn("0.5.1", r.stdout)

    def test_help(self):
        r = _run("churn", "-h")
        self.assertEqual(0, r.returncode)
        self.assertIn("churn", r.stdout.lower())

    def test_not_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("churn", "--root", tmp)
            self.assertNotEqual(0, r.returncode)
            self.assertIn("Not a git", r.stderr)

    def test_json(self):
        r = _run("churn", "-n", "3", "--json")
        try:
            data = json.loads(r.stdout)
            self.assertIn("files", data)
            self.assertIn("count", data)
        except json.JSONDecodeError:
            self.fail("invalid json")

    def test_invalid_n(self):
        r = _run("churn", "-n", "-1")
        self.assertIn("churn:", r.stdout)

    def test_missing_root(self):
        r = _run("churn", "--root", "__nonexistent__")
        self.assertNotEqual(0, r.returncode)


class TestReport(unittest.TestCase):
    def test_version(self):
        r = _run("report", "--version")
        self.assertIn("0.5.1", r.stdout)

    def test_help(self):
        r = _run("report", "-h")
        self.assertEqual(0, r.returncode)
        self.assertIn("report", r.stdout.lower())

    def test_quick(self):
        r = _run("report", "--quick")
        self.assertIn("Health Report", r.stdout)

    def test_json(self):
        r = _run("report", "--quick", "--json")
        try:
            data = json.loads(r.stdout)
            self.assertIn("results", data)
            self.assertIn("count", data)
        except json.JSONDecodeError:
            self.fail("invalid json")

    def test_missing_root(self):
        r = _run("report", "--root", "__nonexistent__")
        self.assertNotEqual(0, r.returncode)


    def test_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "report.md")
            r = _run("report", "--quick", "--output", out)
            self.assertIn("report written", r.stdout)
            self.assertTrue(os.path.exists(out))


class TestGhost(unittest.TestCase):
    def test_version(self):
        r = _run("ghost", "--version")
        self.assertIn("0.5.1", r.stdout)

    def test_help(self):
        r = _run("ghost", "-h")
        self.assertEqual(0, r.returncode)
        self.assertIn("dead", r.stdout.lower())

    def test_lang_py(self):
        r = _run("ghost", "--lang", "py")
        self.assertEqual(0, r.returncode)
        self.assertIn("Dead Code", r.stdout)

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("ghost", "--root", tmp)
            self.assertEqual(0, r.returncode)
            self.assertIn("No dead code", r.stdout)

    def test_json(self):
        r = _run("ghost", "--json", "--root", TOOLS_DIR)
        try:
            data = json.loads(r.stdout)
            self.assertIn("total", data)
            self.assertIn("unused", data)
        except json.JSONDecodeError:
            self.fail("invalid json")

    def test_missing_root(self):
        r = _run("ghost", "--root", "__nonexistent__")
        self.assertNotEqual(0, r.returncode)


if __name__ == "__main__":
    unittest.main()
