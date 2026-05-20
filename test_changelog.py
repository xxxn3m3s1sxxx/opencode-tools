#!/usr/bin/env python3
"""Test suite for changelog.py — formatted git log with category grouping."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from changelog import _parse_line, format_log, CATEGORIES


class TestParseLine(unittest.TestCase):
    def test_feat(self):
        e = _parse_line("abc1234 feat: add new feature")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'Features')
        self.assertEqual(e['hash'], 'abc1234')

    def test_fix(self):
        e = _parse_line("abc1234 fix: resolve crash on startup")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'Bug Fixes')

    def test_breaking(self):
        e = _parse_line("abc1234 feat!: breaking change")
        self.assertIsNotNone(e)
        self.assertTrue(e['breaking'])

    def test_scope(self):
        e = _parse_line("abc1234 fix(core): handle edge case")
        self.assertIsNotNone(e)
        self.assertEqual(e['scope'], 'core')
        self.assertEqual(e['category'], 'Bug Fixes')

    def test_docs(self):
        e = _parse_line("abc1234 docs: update readme")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'Documentation')

    def test_refactor(self):
        e = _parse_line("abc1234 refactor: simplify logic")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'Refactoring')

    def test_test(self):
        e = _parse_line("abc1234 test: add unit tests")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'Tests')

    def test_ci(self):
        e = _parse_line("abc1234 ci: fix pipeline")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'CI')

    def test_chore(self):
        e = _parse_line("abc1234 chore: bump version")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'Chores')

    def test_perf(self):
        e = _parse_line("abc1234 perf: optimize query")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'Performance')

    def test_unknown_type(self):
        e = _parse_line("abc1234 random: something weird")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'Random')

    def test_non_conventional(self):
        e = _parse_line("abc1234 just a regular commit message")
        self.assertIsNotNone(e)
        self.assertEqual(e['category'], 'Other')
        self.assertEqual(e['hash'], 'abc1234')

    def test_invalid_line(self):
        e = _parse_line("")
        self.assertIsNone(e)

    def test_multi_scope(self):
        e = _parse_line("abc1234 feat(auth,api): add login")
        self.assertIsNotNone(e)
        self.assertEqual(e['scope'], 'auth,api')


class TestFormatLog(unittest.TestCase):
    def test_empty(self):
        out = format_log([])
        self.assertEqual(out.strip(), '')

    def test_single_category(self):
        entries = [
            {'hash': 'aaa', 'category': 'Features', 'scope': '', 'breaking': False, 'subject': 'add thing', 'raw': 'add thing'},
        ]
        out = format_log(entries)
        self.assertIn('Features', out)
        self.assertIn('add thing', out)

    def test_breaking_prefix(self):
        entries = [
            {'hash': 'bbb', 'category': 'Bug Fixes', 'scope': '', 'breaking': True, 'subject': 'big change', 'raw': 'big change'},
        ]
        out = format_log(entries)
        self.assertIn(':boom:', out)

    def test_scope_prefix(self):
        entries = [
            {'hash': 'ccc', 'category': 'Features', 'scope': 'core', 'breaking': False, 'subject': 'new core', 'raw': 'new core'},
        ]
        out = format_log(entries)
        self.assertIn('**core:**', out)

    def test_multiple_categories_ordered(self):
        entries = [
            {'hash': 'a', 'category': 'Other', 'scope': '', 'breaking': False, 'subject': 'other', 'raw': 'other'},
            {'hash': 'b', 'category': 'Features', 'scope': '', 'breaking': False, 'subject': 'feat', 'raw': 'feat'},
        ]
        out = format_log(entries)
        feat_pos = out.index('Features')
        other_pos = out.index('Other')
        self.assertGreater(other_pos, feat_pos)


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        subprocess.run(['git', 'init'], cwd=self.tmpdir, capture_output=True, text=True, timeout=10)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=self.tmpdir, capture_output=True, text=True, timeout=10)
        subprocess.run(['git', 'config', 'user.name', 'Tester'], cwd=self.tmpdir, capture_output=True, text=True, timeout=10)
        # Make initial commit
        with open(os.path.join(self.tmpdir, 'readme.md'), 'w') as f:
            f.write('# test')
        subprocess.run(['git', 'add', '.'], cwd=self.tmpdir, capture_output=True, text=True, timeout=10)
        subprocess.run(['git', 'commit', '-m', 'chore: initial commit'], cwd=self.tmpdir, capture_output=True, text=True, timeout=10)
        # Make feature commit
        with open(os.path.join(self.tmpdir, 'main.py'), 'w') as f:
            f.write('print("hello")')
        subprocess.run(['git', 'add', '.'], cwd=self.tmpdir, capture_output=True, text=True, timeout=10)
        subprocess.run(['git', 'commit', '-m', 'feat: add main script'], cwd=self.tmpdir, capture_output=True, text=True, timeout=10)
        # Make fix commit
        with open(os.path.join(self.tmpdir, 'main.py'), 'w') as f:
            f.write('print("hello world")')
        subprocess.run(['git', 'add', '.'], cwd=self.tmpdir, capture_output=True, text=True, timeout=10)
        subprocess.run(['git', 'commit', '-m', 'fix: handle edge case'], cwd=self.tmpdir, capture_output=True, text=True, timeout=10)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, args):
        old_argv = sys.argv
        old_stdout = sys.stdout
        try:
            sys.argv = ['changelog'] + args
            from io import StringIO
            sys.stdout = StringIO()
            from changelog import main
            try:
                exit_code = main()
            except SystemExit as e:
                exit_code = e.code or 0
            output = sys.stdout.getvalue()
            return exit_code, output
        finally:
            sys.stdout = old_stdout
            sys.argv = old_argv

    def test_default_count(self):
        code, out = self._run(['--root=' + self.tmpdir])
        self.assertEqual(code, 0)
        self.assertIn('Features', out)
        self.assertIn('Bug Fixes', out)

    def test_n_flag(self):
        code, out = self._run(['--root=' + self.tmpdir, '-n', '1'])
        self.assertEqual(code, 0)
        # Should show only 1 commit
        lines = [l for l in out.split('\n') if l.strip().startswith('- ')]
        self.assertLessEqual(len(lines), 1)

    def test_json(self):
        code, out = self._run(['--root=' + self.tmpdir, '--json'])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn('entries', data)
        self.assertGreaterEqual(data['count'], 2)

    def test_since(self):
        code, out = self._run(['--root=' + self.tmpdir, '--since', '2000-01-01'])
        self.assertEqual(code, 0)
        self.assertIn('Features', out)

    def test_version(self):
        code, out = self._run(['--version'])
        self.assertEqual(code, 0)
        self.assertIn('0.1.0', out)

    def test_help(self):
        code, out = self._run(['--help'])
        self.assertIn('changelog', out.lower())


if __name__ == '__main__':
    unittest.main()
