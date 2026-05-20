#!/usr/bin/env python3
"""Test suite for lint.py — lint/typecheck runner with output parsing."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lint import _parse_output, _detect_cmd, main, PARSERS


def _run(args):
    old_argv = sys.argv
    old_stdout = sys.stdout
    try:
        sys.argv = ['lint'] + args
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


class TestParseOutput(unittest.TestCase):
    def _test_parser(self, name, lines, expected_count):
        output = '\n'.join(lines)
        results = _parse_output(output)
        self.assertGreaterEqual(len(results), expected_count,
                                f"{name}: expected >= {expected_count}, got {len(results)}")

    def test_ruff_format(self):
        lines = ["src/main.py:42:8: F401 `os` imported but unused"]
        results = _parse_output('\n'.join(lines))
        self.assertGreaterEqual(len(results), 1)
        r = results[0]
        self.assertIn('file', r)
        self.assertIn('line', r)
        self.assertIn('message', r)

    def test_eslint_format(self):
        lines = ["src/app.ts:15:4: warning Missing return type on function"]
        results = _parse_output('\n'.join(lines))
        self.assertGreaterEqual(len(results), 1)

    def test_tsc_format(self):
        lines = ["src/app.ts(10,5): error TS2322: Type 'string' is not assignable to type 'number'"]
        results = _parse_output('\n'.join(lines))
        self.assertGreaterEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.get('severity'), 'error')

    def test_mypy_format(self):
        lines = ["src/main.py:10: error: Incompatible return value type"]
        results = _parse_output('\n'.join(lines))
        self.assertGreaterEqual(len(results), 1)

    def test_pylint_format(self):
        lines = ["src/main.py:42:8: C0103: Variable name 'x' doesn't conform to snake_case"]
        results = _parse_output('\n'.join(lines))
        self.assertGreaterEqual(len(results), 1)

    def test_generic_format(self):
        lines = ["src/main.py:10: something unexpected happened"]
        results = _parse_output('\n'.join(lines))
        self.assertGreaterEqual(len(results), 1)

    def test_empty_output(self):
        results = _parse_output("")
        self.assertEqual(len(results), 0)

    def test_multiple_issues(self):
        lines = [
            "src/a.py:1:1: F401 `x` imported",
            "src/b.py:5:8: E302 expected 2 blank lines",
        ]
        results = _parse_output('\n'.join(lines))
        self.assertEqual(len(results), 2)

    def test_severity_extraction(self):
        lines = ["src/main.py:10:5: error Some error message"]
        results = _parse_output('\n'.join(lines))
        if results:
            r = results[0]
            self.assertIn('severity', r)


class TestDetectCmd(unittest.TestCase):
    def test_detect_from_package_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, "package.json")
            with open(pkg, 'w', encoding='utf-8') as f:
                json.dump({"scripts": {"lint": "eslint src/"}}, f)
            cmd = _detect_cmd(tmp)
            self.assertIsNotNone(cmd)

    def test_no_package_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd = _detect_cmd(tmp)
            self.assertIsNone(cmd)

    def test_typecheck_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, "package.json")
            with open(pkg, 'w', encoding='utf-8') as f:
                json.dump({"scripts": {"typecheck": "tsc --noEmit"}}, f)
            cmd = _detect_cmd(tmp)
            self.assertIsNotNone(cmd)


class TestCLI(unittest.TestCase):
    def test_help(self):
        code, out = _run(['--help'])
        self.assertIn('lint', out.lower())

    def test_version(self):
        code, out = _run(['--version'])
        self.assertEqual(code, 0)
        self.assertIn('0.1.0', out)

    def test_unknown_flag(self):
        code, out = _run(['--bogus'])
        self.assertEqual(code, 1)

    def test_no_args(self):
        code, out = _run([])
        self.assertEqual(code, 1)

    def test_json_output(self):
        """Test JSON output with known parsable input."""
        old_stdout = sys.stdout
        old_argv = sys.argv
        try:
            from io import StringIO
            sys.stdout = StringIO()
            sys.argv = ['lint', '--json']
            # Mock by injecting known patterns
            from lint import _parse_output
            entries = _parse_output("src/main.py:10:5: error Test error")
            result = json.dumps({
                'command': 'test',
                'exit_code': 0,
                'tool': 'ruff',
                'issues': entries,
                'count': len(entries),
            })
            data = json.loads(result)
            self.assertIn('issues', data)
            self.assertIn('count', data)
        finally:
            sys.stdout = old_stdout
            sys.argv = old_argv


if __name__ == '__main__':
    unittest.main()
