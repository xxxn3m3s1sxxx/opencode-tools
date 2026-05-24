#!/usr/bin/env python3
"""Test suite for verify.py — post-edit verification tool."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
from verify import (
    _read_file,
    _checksum,
    _find_line,
    _count_matches,
    cmd_summary,
    cmd_context,
    cmd_contains,
    cmd_line_check,
    cmd_replace_verify,
    format_pretty,
    main,
)


def _run(args):
    """Run main() with args, return (exit_code, stdout)."""
    old_argv = sys.argv
    old_stdout = sys.stdout
    try:
        sys.argv = ["verify"] + args
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


class TestReadFile(unittest.TestCase):
    def test_read_existing(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
        tmp.write("hello\nworld\n")
        tmp.close()
        try:
            lines, raw = _read_file(tmp.name)
            self.assertEqual(len(lines), 2)
            self.assertIn("hello", raw)
        finally:
            os.unlink(tmp.name)

    def test_read_missing(self):
        lines, raw = _read_file("/nonexistent/file")
        self.assertIsNone(lines)

    def test_read_empty(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
        tmp.write("")
        tmp.close()
        try:
            lines, raw = _read_file(tmp.name)
            self.assertEqual(len(lines), 0)  # splitlines() on empty gives []
            self.assertEqual(raw, "")
        finally:
            os.unlink(tmp.name)


class TestChecksum(unittest.TestCase):
    def test_checksum_consistent(self):
        self.assertEqual(_checksum("hello"), _checksum("hello"))

    def test_checksum_differs(self):
        self.assertNotEqual(_checksum("hello"), _checksum("world"))

    def test_checksum_length(self):
        self.assertEqual(len(_checksum("anything")), 12)


class TestFindLine(unittest.TestCase):
    def setUp(self):
        self.lines = ["hello world", "foo bar", "HELLO AGAIN", ""]

    def test_find_exact(self):
        self.assertEqual(_find_line(self.lines, "hello"), 1)

    def test_find_case_insensitive(self):
        self.assertEqual(_find_line(self.lines, "HELLO"), 1)

    def test_find_partial(self):
        self.assertEqual(_find_line(self.lines, "foo"), 2)

    def test_find_not_found(self):
        self.assertIsNone(_find_line(self.lines, "nonexistent"))

    def test_empty_file(self):
        self.assertIsNone(_find_line([], "anything"))


class TestCountMatches(unittest.TestCase):
    def test_count(self):
        lines = ["foo", "bar", "foo foo", "baz"]
        self.assertEqual(_count_matches(lines, "foo"), 2)

    def test_count_zero(self):
        self.assertEqual(_count_matches([], "foo"), 0)

    def test_count_case_insensitive(self):
        lines = ["FOO", "foo"]
        self.assertEqual(_count_matches(lines, "foo"), 2)


class TestCmdSummary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
        self.tmp.write("line1\nline2\nline3\n")
        self.tmp.close()
        self.lines, self.raw = _read_file(self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_summary_keys(self):
        r = cmd_summary(self.tmp.name, self.lines, self.raw)
        self.assertEqual(r["status"], "ok")
        self.assertIn("lines", r)
        self.assertIn("bytes", r)
        self.assertIn("checksum", r)

    def test_summary_line_count(self):
        r = cmd_summary(self.tmp.name, self.lines, self.raw)
        self.assertEqual(r["lines"], 3)

    def test_summary_checksum_format(self):
        r = cmd_summary(self.tmp.name, self.lines, self.raw)
        self.assertEqual(len(r["checksum"]), 12)


class TestCmdContext(unittest.TestCase):
    def setUp(self):
        self.lines = [f"line {i}" for i in range(1, 20)]
        self.raw = "\n".join(self.lines)

    def test_context_middle(self):
        r = cmd_context("f.txt", self.lines, self.raw, 10, context=2)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(len(r["context"]), 5)  # 8,9,10,11,12

    def test_context_target_marked(self):
        r = cmd_context("f.txt", self.lines, self.raw, 10, context=1)
        target = [c for c in r["context"] if c["is_target"]]
        self.assertEqual(len(target), 1)
        self.assertEqual(target[0]["line"], 10)

    def test_context_out_of_range(self):
        r = cmd_context("f.txt", self.lines, self.raw, 999, context=1)
        self.assertEqual(r["status"], "error")

    def test_context_zero_line(self):
        r = cmd_context("f.txt", self.lines, self.raw, 0, context=1)
        self.assertEqual(r["status"], "error")

    def test_context_beginning(self):
        r = cmd_context("f.txt", self.lines, self.raw, 1, context=2)
        self.assertEqual(r["status"], "ok")
        # Should show lines 1-3
        ctx_lines = [c["line"] for c in r["context"]]
        self.assertIn(1, ctx_lines)
        self.assertIn(3, ctx_lines)


class TestCmdContains(unittest.TestCase):
    def setUp(self):
        self.lines = ["hello world", "foo bar", ""]
        self.raw = "\n".join(self.lines)

    def test_found(self):
        r = cmd_contains("f.txt", self.lines, self.raw, "hello")
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["found"])
        self.assertEqual(r["line"], 1)

    def test_not_found(self):
        r = cmd_contains("f.txt", self.lines, self.raw, "nonexistent")
        self.assertEqual(r["status"], "fail")
        self.assertFalse(r["found"])

    def test_should_not_exist_not_found(self):
        r = cmd_contains("f.txt", self.lines, self.raw, "nonexistent", should_exist=False)
        self.assertEqual(r["status"], "ok")
        self.assertFalse(r["found"])

    def test_should_not_exist_but_found(self):
        r = cmd_contains("f.txt", self.lines, self.raw, "hello", should_exist=False)
        self.assertEqual(r["status"], "fail")
        self.assertTrue(r["found"])


class TestCmdLineCheck(unittest.TestCase):
    def setUp(self):
        self.lines = ["hello world", "foo bar", "line three"]
        self.raw = "\n".join(self.lines)

    def test_matches(self):
        r = cmd_line_check("f.txt", self.lines, self.raw, 1, "hello")
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["match"])

    def test_mismatch(self):
        r = cmd_line_check("f.txt", self.lines, self.raw, 1, "goodbye")
        self.assertEqual(r["status"], "fail")
        self.assertFalse(r["match"])

    def test_out_of_range(self):
        r = cmd_line_check("f.txt", self.lines, self.raw, 999, "x")
        self.assertEqual(r["status"], "error")

    def test_zero_line(self):
        r = cmd_line_check("f.txt", self.lines, self.raw, 0, "x")
        self.assertEqual(r["status"], "error")


class TestCmdReplaceVerify(unittest.TestCase):
    def setUp(self):
        self.lines = ["hello world", "old text here", "new text present", "more"]
        self.raw = "\n".join(self.lines)

    def test_old_gone_new_present(self):
        """Simulate successful replace: old removed, new exists."""
        new_lines = ["hello world", "new text present", "more"]
        new_raw = "\n".join(new_lines)
        r = cmd_replace_verify("f.txt", new_lines, new_raw, "old text", "new text")
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["old_removed"])
        self.assertTrue(r["new_present"])

    def test_old_still_there(self):
        r = cmd_replace_verify("f.txt", self.lines, self.raw, "old text", "new text")
        self.assertEqual(r["status"], "fail")
        self.assertFalse(r["old_removed"])

    def test_new_missing(self):
        r = cmd_replace_verify("f.txt", self.lines, self.raw, "nonexistent", "MISSING")
        self.assertEqual(r["status"], "fail")
        self.assertTrue(r["old_removed"])  # old was never there
        self.assertFalse(r["new_present"])


class TestFormatPretty(unittest.TestCase):
    def test_summary(self):
        out = format_pretty(
            {"status": "ok", "check": "summary", "file": "a.py", "lines": 10, "bytes": 42, "checksum": "abc123"}
        )
        self.assertIn("[OK]", out)
        self.assertIn("a.py", out)

    def test_fail(self):
        out = format_pretty(
            {"status": "fail", "check": "contains", "text": "x", "found": False, "line": None, "count": 0}
        )
        self.assertIn("[FAIL]", out)

    def test_error(self):
        out = format_pretty({"status": "error", "message": "file not found"})
        self.assertIn("[ERROR]", out)


class TestCLI(unittest.TestCase):
    """Test CLI argument parsing."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8")
        self.tmp.write("line one\nline two\nline three\n")
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_summary(self):
        code, out = _run([self.path])
        self.assertEqual(code, 0)
        self.assertIn("[OK]", out)
        self.assertIn("lines:", out)

    def test_contains(self):
        code, out = _run([self.path, "line one"])
        self.assertEqual(code, 0)
        self.assertIn("[OK]", out)

    def test_not_contains(self):
        code, out = _run([self.path, "--not", "nonexistent"])
        self.assertEqual(code, 0)

    def test_not_contains_fails(self):
        code, out = _run([self.path, "--not", "line one"])
        self.assertEqual(code, 1)
        self.assertIn("[FAIL]", out)

    def test_line_check(self):
        code, out = _run([f"{self.path}:2", "line two"])
        self.assertEqual(code, 0)

    def test_line_check_fails(self):
        code, out = _run([f"{self.path}:2", "WRONG"])
        self.assertEqual(code, 1)
        self.assertIn("[FAIL]", out)

    def test_context(self):
        code, out = _run([f"{self.path}:2"])
        self.assertEqual(code, 0)
        self.assertIn("2:", out)  # context shows line numbers

    def test_json(self):
        code, out = _run([self.path, "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["check"], "summary")

    def test_missing_file(self):
        code, out = _run(["/nonexistent"])
        self.assertEqual(code, 1)
        self.assertIn("[ERROR]", out)

    def test_version(self):
        code, out = _run(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("0.5.3", out)

    def test_diff(self):
        code, out = _run([self.path, "--diff"])
        # May fail if not in git repo, but should not crash
        self.assertIn(code, (0, 1))
        self.assertNotIn("[ERROR]", out)

    def test_diff_unknown_flag(self):
        code, out = _run([self.path, "--bogus_flag_x"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
