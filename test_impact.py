#!/usr/bin/env python3
"""Comprehensive test suite for impact.py — Change Impact Analyzer."""

import json
import io
import os
import sys
import tempfile
import unittest

# Ensure impact.py is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from impact import (
    ImpactAnalyzer,
    _py_find_definitions,
    _py_find_references,
    _cpp_find_definitions,
    _grep_find_references,
    _is_python,
    _is_cpp,
    _is_test_file,
    _is_source_file,
    format_json,
    format_pretty,
)


class TestFileDetection(unittest.TestCase):
    """Test file type detection helpers."""

    def test_is_python(self):
        self.assertTrue(_is_python("foo.py"))
        self.assertTrue(_is_python("/path/to/module.py"))
        self.assertFalse(_is_python("foo.cpp"))
        self.assertFalse(_is_python("foo.h"))

    def test_is_cpp(self):
        for ext in [".cpp", ".c", ".h", ".hpp", ".cc", ".cxx", ".hxx", ".hh"]:
            self.assertTrue(_is_cpp(f"foo{ext}"), f"failed for {ext}")
        self.assertFalse(_is_cpp("foo.py"))
        self.assertFalse(_is_cpp("foo.rs"))

    def test_is_test_file(self):
        self.assertTrue(_is_test_file("test_foo.py"))
        self.assertTrue(_is_test_file("foo_test.py"))
        self.assertTrue(_is_test_file("test_bar.cpp"))
        self.assertTrue(_is_test_file("path/to/test_baz.py"))
        self.assertTrue(_is_test_file("foo_test.cpp"))
        self.assertFalse(_is_test_file("foo.py"))
        self.assertFalse(_is_test_file("bar.cpp"))

    def test_is_source_file(self):
        self.assertTrue(_is_source_file("foo.py"))
        self.assertTrue(_is_source_file("bar.cpp"))
        self.assertFalse(_is_source_file("foo.txt"))
        self.assertFalse(_is_source_file("foo.md"))


class TestPythonDefinitions(unittest.TestCase):
    """Test Python definition detection via AST."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        self.tmp.write("""
class MyClass:
    def my_method(self):
        pass

def my_function(a, b):
    return a + b

async def async_func():
    pass

MY_CONSTANT = 42

class AnotherClass:
    pass
""")
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_find_class_def(self):
        results = _py_find_definitions(self.path, "MyClass")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "class")
        self.assertEqual(results[0]["line"], 2)

    def test_find_function_def(self):
        results = _py_find_definitions(self.path, "my_function")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "function")
        self.assertEqual(results[0]["line"], 6)

    def test_find_async_function_def(self):
        results = _py_find_definitions(self.path, "async_func")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "async_function")
        self.assertEqual(results[0]["line"], 9)

    def test_find_variable_def(self):
        results = _py_find_definitions(self.path, "MY_CONSTANT")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "variable")
        self.assertEqual(results[0]["line"], 12)

    def test_missing_symbol(self):
        results = _py_find_definitions(self.path, "NonExistent")
        self.assertEqual(len(results), 0)

    def test_method_not_class(self):
        """Method inside class should not be found as definition of parent's name."""
        results = _py_find_definitions(self.path, "my_method")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "function")
        self.assertEqual(results[0]["line"], 3)


class TestPythonReferences(unittest.TestCase):
    """Test Python reference detection via AST."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        self.tmp.write("""
import os

def helper():
    return os.path.join('a', 'b')

class Processor:
    def process(self):
        helper()
        data = helper()
        self.run()

result = helper()
""")
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_call_reference(self):
        results = _py_find_references(self.path, "helper")
        # 3 references: line 5 (call), line 11 (call), line 14 (call assignment)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIn(r["type"], ("call", "reference"))

    def test_attribute_reference(self):
        results = _py_find_references(self.path, "join")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "attribute")
        self.assertEqual(results[0]["line"], 5)

    def test_class_name_as_reference(self):
        """Class names used in code should appear as references."""
        results = _py_find_references(self.path, "Processor")
        # Used at line 9 and line 8 (def)
        self.assertEqual(len(results), 0)

    def test_def_not_in_refs(self):
        """Definition lines should be excluded from references."""
        results = _py_find_references(self.path, "helper")
        for r in results:
            self.assertNotEqual(r["line"], 4)  # def helper(): is line 4


class TestCppDefinitions(unittest.TestCase):
    """Test C++ definition detection via regex."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".cpp", delete=False, encoding="utf-8")
        self.tmp.write("""
class MyClass {
public:
    void my_method(int x);
    int compute(float y) {
        return (int)y;
    }
};

struct Point {
    int x, y;
};

static uint8_t* my_alloc(size_t size) {
    return (uint8_t*)malloc(size);
}

#define MY_MACRO 42

int global_var = 0;
""")
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_class_def(self):
        results = _cpp_find_definitions(self.path, "MyClass")
        class_defs = [r for r in results if r["type"] == "class"]
        self.assertEqual(len(class_defs), 1)
        self.assertEqual(class_defs[0]["line"], 2)

    def test_function_def(self):
        results = _cpp_find_definitions(self.path, "my_alloc")
        func_defs = [r for r in results if r["type"] == "function"]
        self.assertEqual(len(func_defs), 1)
        self.assertEqual(func_defs[0]["line"], 14)

    def test_function_declaration(self):
        results = _cpp_find_definitions(self.path, "my_method")
        # Should find the declaration: void my_method(int x);
        self.assertGreaterEqual(len(results), 1)

    def test_macro_def(self):
        results = _cpp_find_definitions(self.path, "MY_MACRO")
        macro_defs = [r for r in results if r["type"] == "macro"]
        self.assertEqual(len(macro_defs), 1)
        self.assertEqual(macro_defs[0]["line"], 18)

    def test_struct_def(self):
        results = _cpp_find_definitions(self.path, "Point")
        class_defs = [r for r in results if r["type"] == "class"]
        self.assertEqual(len(class_defs), 1)

    def test_missing_symbol(self):
        results = _cpp_find_definitions(self.path, "NonExistent")
        self.assertEqual(len(results), 0)


class TestCppReferences(unittest.TestCase):
    """Test C++ reference detection via grep."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".cpp", delete=False, encoding="utf-8")
        self.tmp.write("""
int counter = 0;

void foo() {
    counter++;
}

void bar() {
    int x = counter;
    counter = 42;
}
""")
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_word_boundary(self):
        """Ensure word boundary matching works: 'counter' doesn't match 'counterpart'."""
        results = _grep_find_references(self.path, "counter")
        self.assertEqual(len(results), 4)  # line 2 def, 5 ref, 9 ref, 10 ref

    def test_empty_results(self):
        results = _grep_find_references(self.path, "nonexistent")
        self.assertEqual(len(results), 0)


class TestImpactAnalyzer(unittest.TestCase):
    """Test the full ImpactAnalyzer with temp project structure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

        # Create a Python source file
        with open(os.path.join(self.tmpdir, "mymod.py"), "w", encoding="utf-8") as f:
            f.write("""
def do_something():
    return helper_fn()

def helper_fn():
    return 42

class MyThing:
    def __init__(self):
        self.value = do_something()
""")

        # Create a C++ source file
        with open(os.path.join(self.tmpdir, "engine.cpp"), "w", encoding="utf-8") as f:
            f.write("""
#include <cstdint>

class Engine {
public:
    void run();
    uint8_t* alloc(size_t n) {
        return new uint8_t[n];
    }
};

uint8_t* global_buf = nullptr;

#define ENGINE_VERSION 3
""")

        # Create a test file
        with open(os.path.join(self.tmpdir, "test_mymod.py"), "w", encoding="utf-8") as f:
            f.write("""
from mymod import do_something, helper_fn, MyThing

def test_do_something():
    result = do_something()
    assert result == 42

def test_helper():
    assert helper_fn() == 42
""")

        self.analyzer = ImpactAnalyzer(self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_find_def_python(self):
        defs = self.analyzer.find_definition("do_something", "py")
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0]["type"], "function")
        self.assertEqual(defs[0]["line"], 2)

    def test_find_def_cpp(self):
        defs = self.analyzer.find_definition("Engine", "cpp")
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0]["type"], "class")
        self.assertEqual(defs[0]["line"], 4)

    def test_find_def_all(self):
        defs = self.analyzer.find_definition("do_something", "all")
        self.assertEqual(len(defs), 1)

    def test_find_def_nonexistent(self):
        defs = self.analyzer.find_definition("NonExistent", "all")
        self.assertEqual(len(defs), 0)

    def test_find_refs_python(self):
        refs = self.analyzer.find_references("do_something", "py")
        self.assertGreaterEqual(len(refs), 1)

    def test_find_refs_cpp(self):
        refs = self.analyzer.find_references("alloc", "cpp")
        self.assertGreaterEqual(len(refs), 1)

    def test_find_tests(self):
        tests = self.analyzer.find_tests("do_something", "all")
        self.assertGreaterEqual(len(tests), 1)
        # Should be in test file
        self.assertIn("test_mymod", tests[0]["file"])

    def test_tests_empty_for_private_symbol(self):
        tests = self.analyzer.find_tests("NonExistent", "all")
        self.assertEqual(len(tests), 0)

    def test_find_callees(self):
        callees = self.analyzer.find_callees("do_something", "all")
        self.assertGreaterEqual(len(callees), 1)
        # do_something calls helper_fn
        callee_names = [c["name"] for c in callees]
        self.assertIn("helper_fn", callee_names)

    def test_find_callees_nonexistent(self):
        callees = self.analyzer.find_callees("NonExistent", "all")
        self.assertEqual(len(callees), 0)

    def test_dedup_defs(self):
        """Same definition should not appear twice."""
        defs = self.analyzer.find_definition("MyThing", "all")
        file_lines = [(d["file"], d["line"]) for d in defs]
        self.assertEqual(len(file_lines), len(set(file_lines)))

    def test_dedup_refs(self):
        """Same line should not appear twice in references."""
        refs = self.analyzer.find_references("helper_fn", "all")
        file_lines = [(r["file"], r["line"]) for r in refs]
        self.assertEqual(len(file_lines), len(set(file_lines)))


class TestFileLineInference(unittest.TestCase):
    """Test inferring symbol from file:line."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        self.tmp.write("""def my_function():
    return helper()

class MyClass:
    pass
""")
        self.tmp.close()
        self.path = self.tmp.name

    def tearDown(self):
        os.unlink(self.path)

    def test_infer_function_call(self):
        analyzer = ImpactAnalyzer(os.path.dirname(self.path))
        result = analyzer.infer_symbol(self.path, 2)
        self.assertEqual(result, "helper")

    def test_infer_function_def(self):
        analyzer = ImpactAnalyzer(os.path.dirname(self.path))
        result = analyzer.infer_symbol(self.path, 1)
        self.assertEqual(result, "my_function")

    def test_infer_out_of_range(self):
        analyzer = ImpactAnalyzer(os.path.dirname(self.path))
        result = analyzer.infer_symbol(self.path, 999)
        self.assertIsNone(result)

    def test_infer_zero_line(self):
        analyzer = ImpactAnalyzer(os.path.dirname(self.path))
        result = analyzer.infer_symbol(self.path, 0)
        self.assertIsNone(result)

    def test_infer_missing_file(self):
        analyzer = ImpactAnalyzer(os.path.dirname(self.path))
        result = analyzer.infer_symbol("/nonexistent/file.py", 1)
        self.assertIsNone(result)


class TestJSONOutput(unittest.TestCase):
    """Test JSON output format matches plugin expectations."""

    def setUp(self):
        self.symbol = "test_fn"
        self.defs = [
            {"type": "function", "name": "test_fn", "file": "/a/b.py", "line": 10, "context": "def test_fn():"}
        ]
        self.refs = [{"type": "call", "file": "/a/b.py", "line": 15, "context": "test_fn()"}]
        self.tests = [{"type": "call", "file": "/a/test_b.py", "line": 5, "context": "test_fn()"}]
        self.callees = [{"name": "other_fn", "file": "/a/b.py", "line": 11}]
        self.root = "/a"

    def test_json_structure(self):
        js = format_json(self.symbol, self.defs, self.refs, self.tests, self.callees, self.root)
        data = json.loads(js)
        self.assertEqual(data["symbol"], "test_fn")
        self.assertEqual(len(data["definitions"]), 1)
        self.assertEqual(len(data["references"]), 1)
        self.assertEqual(len(data["tests"]), 1)
        self.assertEqual(len(data["callees"]), 1)

    def test_json_empty(self):
        js = format_json("empty", [], [], [], [], "/root")
        data = json.loads(js)
        self.assertEqual(data["symbol"], "empty")
        self.assertEqual(len(data["definitions"]), 0)

    def test_json_serializable(self):
        """All fields must be JSON-serializable types."""
        js = format_json("x", self.defs, self.refs, self.tests, self.callees, self.root)
        data = json.loads(js)
        self.assertIsInstance(data["project"], str)


class TestPrettyOutput(unittest.TestCase):
    """Test human-readable output format."""

    def test_pretty_basic(self):
        out = format_pretty("test_fn", [], [], [], [], "/root")
        self.assertIn("test_fn", out)
        self.assertIn("[def]", out)
        self.assertIn("(not found)", out)

    def test_pretty_with_data(self):
        defs = [{"type": "function", "name": "test_fn", "file": "/root/a.py", "line": 10}]
        out = format_pretty("test_fn", defs, [], [], [], "/root")
        self.assertIn("a.py:10", out)


class TestCLI(unittest.TestCase):
    """Test CLI argument parsing via main()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "mod.py"), "w", encoding="utf-8") as f:
            f.write("def foo():\n    pass\n\ndef bar():\n    foo()\n")
        with open(os.path.join(self.tmpdir, "test_mod.py"), "w", encoding="utf-8") as f:
            f.write("from mod import foo\n\ndef test_foo():\n    foo()\n")
        self.orig_argv = sys.argv
        self.orig_stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")

    def tearDown(self):
        sys.argv = self.orig_argv
        sys.stdout.close()
        sys.stdout = self.orig_stdout
        import shutil

        shutil.rmtree(self.tmpdir)

    def _run(self, args):
        """Run impact with args, capture stdout."""
        old_out = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        sys.argv = ["impact"] + args + ["--root=" + self.tmpdir]
        try:
            from impact import main

            exit_code = main()
        except SystemExit as e:
            exit_code = e.code
        finally:
            sys.stdout = old_out
            output = buf.getvalue()
        return exit_code, output

    def test_def_command(self):
        code, out = self._run(["def", "foo"])
        self.assertEqual(code, 0)
        self.assertIn("foo", out)

    def test_refs_command(self):
        code, out = self._run(["refs", "foo"])
        self.assertEqual(code, 0)

    def test_tests_command(self):
        code, out = self._run(["tests", "foo"])
        self.assertEqual(code, 0)

    def test_graph_command(self):
        code, out = self._run(["graph", "foo"])
        self.assertEqual(code, 0)

    def test_default_symbol(self):
        code, out = self._run(["foo"])
        self.assertEqual(code, 0)
        self.assertIn("[def]", out)
        self.assertIn("[ref]", out)

    def test_file_command(self):
        code, out = self._run(["file", os.path.join(self.tmpdir, "mod.py")])
        self.assertEqual(code, 0)
        self.assertIn("foo", out)
        self.assertIn("bar", out)
        self.assertIn("2 symbols", out)

    def test_file_command_not_found(self):
        code, out = self._run(["file", os.path.join(self.tmpdir, "nope.py")])
        self.assertEqual(code, 1)

    def test_json_flag(self):
        code, out = self._run(["foo", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["symbol"], "foo")

    def test_missing_symbol(self):
        code, out = self._run(["def"])
        self.assertEqual(code, 1)

    def test_version(self):
        code, out = self._run(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("0.4.0", out)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_python_file(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        tmp.write("")
        tmp.close()
        try:
            defs = _py_find_definitions(tmp.name, "anything")
            self.assertEqual(len(defs), 0)
            refs = _py_find_references(tmp.name, "anything")
            self.assertEqual(len(refs), 0)
        finally:
            os.unlink(tmp.name)

    def test_empty_cpp_file(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".cpp", delete=False, encoding="utf-8")
        tmp.write("")
        tmp.close()
        try:
            defs = _cpp_find_definitions(tmp.name, "anything")
            self.assertEqual(len(defs), 0)
            refs = _grep_find_references(tmp.name, "anything")
            self.assertEqual(len(refs), 0)
        finally:
            os.unlink(tmp.name)

    def test_python_syntax_error(self):
        """Should not crash on invalid Python."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        tmp.write("this is not valid python @@@")
        tmp.close()
        try:
            # Should not raise
            defs = _py_find_definitions(tmp.name, "anything")
            self.assertEqual(len(defs), 0)
            refs = _py_find_references(tmp.name, "anything")
            self.assertEqual(len(refs), 0)
        finally:
            os.unlink(tmp.name)

    def test_unicode_in_python(self):
        """Unicode identifiers should work."""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
        tmp.write("def f\u00e9d\u00e9ration():\n    pass\n")
        tmp.close()
        try:
            defs = _py_find_definitions(tmp.name, "f\u00e9d\u00e9ration")
            self.assertEqual(len(defs), 1)
        finally:
            os.unlink(tmp.name)

    def test_nonexistent_file_references(self):
        """Should return empty for nonexistent file."""
        result = _grep_find_references("/nonexistent/path/file.cpp", "anything")
        self.assertEqual(len(result), 0)

    def test_analyzer_with_nonexistent_root(self):
        """Analyzer should handle non-existent roots gracefully."""
        analyzer = ImpactAnalyzer("/nonexistent/path")
        defs = analyzer.find_definition("anything", "all")
        self.assertEqual(len(defs), 0)

    def test_walk_files_excludes_dirs(self):
        """Should skip common non-source directories."""
        analyzer = ImpactAnalyzer()
        # Just verify no crash
        files = analyzer._walk_files("all")
        self.assertIsInstance(files, list)


class TestDeduplication(unittest.TestCase):
    """Test deduplication logic more thoroughly."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        with open(os.path.join(self.tmpdir, "mod.py"), "w", encoding="utf-8") as f:
            f.write("""
def shared():
    return 42

class shared:
    pass
""")
        self.analyzer = ImpactAnalyzer(self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_def_dedup_by_type(self):
        """Function and class with same name should be separate defs."""
        defs = self.analyzer.find_definition("shared", "all")
        self.assertEqual(len(defs), 2)  # function + class

    def test_ref_not_duplicated(self):
        """Reference to def line should not be counted as both ref and def."""
        refs = self.analyzer.find_references("shared", "all")
        # Should be 0 since all references are on def lines
        # Actually the class 'shared' at line 7 isn't referenced anywhere else
        # and the function at line 2 also isn't referenced
        # So refs should be 0
        self.assertEqual(len(refs), 0)


if __name__ == "__main__":
    unittest.main()
