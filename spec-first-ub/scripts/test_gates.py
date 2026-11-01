"""Testes dos gates CRAP, duplicação e mutação."""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path

import crap
import dry
import gatelib as g
import mutate

SRC = textwrap.dedent('''\
    def classify(n):
        if n < 0:
            return "neg"
        if n == 0:
            return "zero"
        return "pos"

    def add(a, b):
        return a + b
''')


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.prev = Path.cwd()
        os.chdir(self.dir)

    def tearDown(self) -> None:
        os.chdir(self.prev)
        self.tmp.cleanup()

    def run_main(self, module, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = module.main(argv)
        return code, out.getvalue()


class FunctionsTest(Base):
    def test_python_complexity(self) -> None:
        (self.dir / "m.py").write_text(SRC)
        funcs = {f.name: f for f in g.find_functions(self.dir / "m.py")}
        self.assertEqual(funcs["classify"].complexity, 3)
        self.assertEqual(funcs["add"].complexity, 1)

    def test_go_and_js_detection(self) -> None:
        (self.dir / "a.go").write_text("package a\nfunc Foo(x int) int {\n\tif x > 0 && x < 9 {\n\t\treturn 1\n\t}\n\treturn 0\n}\n")
        (self.dir / "b.js").write_text("function bar(x) {\n  return x ? 1 : 0;\n}\nconst baz = (y) => {\n  return y;\n};\n")
        go = g.find_functions(self.dir / "a.go")
        js = {f.name: f for f in g.find_functions(self.dir / "b.js")}
        self.assertEqual((go[0].name, go[0].complexity, go[0].start), ("Foo", 3, 2))
        self.assertEqual(js["bar"].complexity, 2)
        self.assertIn("baz", js)


class CrapTest(Base):
    def write_cov(self, executed: list[int], missing: list[int]) -> None:
        (self.dir / "m.py").write_text(SRC)
        (self.dir / "cov.json").write_text(json.dumps(
            {"files": {"m.py": {"executed_lines": executed, "missing_lines": missing}}}))

    def test_formula(self) -> None:
        self.assertEqual(crap.crap(3, 1.0), 3)
        self.assertEqual(crap.crap(10, 0.0), 110)

    def test_pass_when_covered(self) -> None:
        self.write_cov([1, 2, 3, 4, 5, 6, 8, 9], [])
        code, out = self.run_main(crap, ["m.py", "--coverage", "cov.json"])
        self.assertEqual(code, g.EXIT_PASS, out)

    def test_fail_when_uncovered_and_complex(self) -> None:
        self.write_cov([1, 2, 8, 9], [3, 4, 5, 6])
        code, out = self.run_main(crap, ["m.py", "--coverage", "cov.json", "--threshold", "4"])
        self.assertEqual(code, g.EXIT_FAIL, out)
        self.assertIn("classify", out)

    def test_not_measured_without_coverage(self) -> None:
        (self.dir / "m.py").write_text(SRC)
        code, out = self.run_main(crap, ["m.py", "--coverage", "missing.json"])
        self.assertEqual(code, g.EXIT_NOT_MEASURED)
        self.assertIn("NOT_MEASURED", out)

    def test_not_measured_when_file_absent_from_coverage(self) -> None:
        self.write_cov([1], [])
        (self.dir / "other.py").write_text(SRC)
        code, _ = self.run_main(crap, ["other.py", "--coverage", "cov.json"])
        self.assertEqual(code, g.EXIT_NOT_MEASURED)

    def test_lcov_and_go_profiles(self) -> None:
        (self.dir / "c.lcov").write_text("SF:m.py\nDA:1,3\nDA:2,0\nend_of_record\n")
        (self.dir / "c.out").write_text("mode: set\nexample.com/p/a.go:3.2,5.3 1 1\nexample.com/p/a.go:6.2,7.3 1 0\n")
        self.assertEqual(g.load_coverage(self.dir / "c.lcov")["m.py"], ({1}, {2}))
        self.assertEqual(g.load_coverage(self.dir / "c.out")["example.com/p/a.go"], ({3, 4, 5}, {6, 7}))


class DryTest(Base):
    BODY = textwrap.dedent('''\
        def {name}(items):
            total = 0
            for item in items:
                if item.price > 0 and item.qty > 0:
                    total += item.price * item.qty
                else:
                    total -= 1
            return total
    ''')

    def test_detects_duplicate(self) -> None:
        (self.dir / "a.py").write_text(self.BODY.format(name="one") + "\n" + self.BODY.format(name="two"))
        code, out = self.run_main(dry, ["a.py"])
        self.assertEqual(code, g.EXIT_FAIL, out)

    def test_distinct_functions_pass(self) -> None:
        (self.dir / "a.py").write_text(self.BODY.format(name="one") + "\n" + textwrap.dedent('''\
            def other(path):
                with open(path) as handle:
                    data = handle.read().split(",")
                    cleaned = [piece.strip().lower() for piece in data if piece]
                return {key: len(key) for key in cleaned}
        '''))
        code, out = self.run_main(dry, ["a.py"])
        self.assertEqual(code, g.EXIT_PASS, out)


class MutateTest(Base):
    def setUp(self) -> None:
        super().setUp()
        (self.dir / "calc.py").write_text(SRC)

    def run_with_test(self, test_body: str) -> tuple[int, str]:
        (self.dir / "test_calc.py").write_text("import unittest\nfrom calc import *\nclass T(unittest.TestCase):\n"
                                              + textwrap.indent(textwrap.dedent(test_body), "    "))
        return self.run_main(mutate, ["calc.py", "--test-cmd", "python3 -m unittest test_calc", "--max", "100"])

    def test_strong_tests_kill_all(self) -> None:
        code, out = self.run_with_test('''\
            def test_all(self):
                self.assertEqual(classify(-1), "neg")
                self.assertEqual(classify(0), "zero")
                self.assertEqual(classify(1), "pos")
                self.assertEqual(add(2, 3), 5)
        ''')
        self.assertEqual(code, g.EXIT_PASS, out)

    def test_weak_tests_leave_survivors_and_source_is_restored(self) -> None:
        code, out = self.run_with_test('''\
            def test_weak(self):
                self.assertEqual(classify(-1), "neg")
        ''')
        self.assertEqual(code, g.EXIT_FAIL, out)
        self.assertIn("SOBREVIVEU", out)
        self.assertEqual((self.dir / "calc.py").read_text(), SRC)
        self.assertFalse((self.dir / ".mutate-backup").exists())

    def test_not_measured_when_suite_already_red(self) -> None:
        code, _ = self.run_with_test('''\
            def test_red(self):
                self.fail("vermelho")
        ''')
        self.assertEqual(code, g.EXIT_NOT_MEASURED)


if __name__ == "__main__":
    unittest.main()
