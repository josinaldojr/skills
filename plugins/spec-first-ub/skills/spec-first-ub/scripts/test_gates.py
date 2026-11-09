"""Testes dos gates CRAP, duplicação e mutação."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
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


class LexerTest(Base):
    def test_strings_comments_and_regex_do_not_leak_tokens(self) -> None:
        src = 'const a = "if (x) { }"; // while (y) {\nconst r = /[}{]\\/if/g; /* for { */ let b = `${a}`;\n'
        toks = [(t.kind, t.text) for t in g.lex(src, ".js")]
        self.assertIn(("str", '"if (x) { }"'), toks)
        self.assertIn(("str", "/[}{]\\/if/g"), toks)
        self.assertEqual([t for t in toks if t[0] == "id" and t[1] in ("if", "while", "for")], [])

    def test_division_is_not_regex(self) -> None:
        self.assertNotIn("str", [t.kind for t in g.lex("x = a / b / c", ".js")])

    def test_go_raw_string_ends_at_backtick(self) -> None:
        toks = g.lex("s := `C:\\`\nx := 1\n", ".go")
        self.assertEqual([t.text for t in toks if t.kind == "num"], ["1"])

    def test_java_text_block_and_generic_method(self) -> None:
        src = ('class A {\n  String s = """\n  if { \n  """;\n'
               '  <T> List<T> pick(List<T> xs, int n) throws Exception {\n    return n > 0 ? xs : null;\n  }\n}\n')
        (self.dir / "A.java").write_text(src)
        funcs = {f.name: f for f in g.find_functions(self.dir / "A.java")}
        self.assertEqual(list(funcs), ["pick"])
        self.assertEqual(funcs["pick"].complexity, 2)


class BraceFunctionsTest(Base):
    def test_js_methods_and_arrows_but_not_control_flow(self) -> None:
        (self.dir / "c.ts").write_text(
            "class C {\n  async load(id: string): Promise<void> {\n    if (id) { run(); }\n    for (const x of y) {}\n  }\n}\n"
            "const f = async (a: number) => {\n  return a && 1;\n};\nconst g2 = h => { return h; };\n")
        funcs = {f.name: f for f in g.find_functions(self.dir / "c.ts")}
        self.assertEqual(set(funcs), {"load", "f", "g2"})
        self.assertEqual(funcs["load"].complexity, 3)
        self.assertEqual(funcs["f"].complexity, 2)

    def test_java_skips_anonymous_classes_and_control_statements(self) -> None:
        (self.dir / "B.java").write_text(
            "class B {\n  public B(int x) { this.x = x; }\n  void run() {\n"
            "    new Thread() { public void tick() { go(); } };\n"
            "    if (a) { b(); } else if (c) { d(); }\n    synchronized (this) { e(); }\n  }\n}\n")
        funcs = {f.name: f for f in g.find_functions(self.dir / "B.java")}
        self.assertEqual(set(funcs), {"B", "run", "tick"})
        self.assertEqual(funcs["run"].complexity, 3)

    def test_go_methods_anonymous_and_bodyless(self) -> None:
        (self.dir / "d.go").write_text(
            "package d\ntype I interface{ M() }\n"
            "func (s *S) Get(k string) (int, error) {\n\tf := func() { }\n\tfor _, v := range s.m {\n\t\tswitch v {\n"
            "\t\tcase 1:\n\t\t}\n\t}\n\treturn 0, nil\n}\n"
            "func External(x int) int\nfunc Next() struct{} { return struct{}{} }\n")
        funcs = {f.name: f for f in g.find_functions(self.dir / "d.go")}
        self.assertEqual(set(funcs), {"Get", "Next"})
        self.assertEqual(funcs["Get"].complexity, 3)


class CollectFilesTest(Base):
    def test_skip_dirs_apply_only_below_target_and_missing_target_raises(self) -> None:
        src = self.dir / "build" / "proj" / "src"
        (src / "node_modules").mkdir(parents=True)
        (src / "a.py").write_text("x = 1\n")
        (src / "test_a.py").write_text("x = 1\n")
        (src / "node_modules" / "b.py").write_text("x = 1\n")
        self.assertEqual([f.name for f in g.collect_files([str(src)])], ["a.py"])
        with self.assertRaises(FileNotFoundError):
            g.collect_files(["nope"])


class DiffParsingTest(unittest.TestCase):
    def test_hunk_range(self) -> None:
        self.assertEqual(g.parse_hunk_range("@@ -1,2 +10,3 @@ def f():"), (10, 3))
        self.assertEqual(g.parse_hunk_range("@@ -5 +7 @@"), (7, 1))
        self.assertIsNone(g.parse_hunk_range("@@ garbage @@"))


class CoverageMatchTest(Base):
    def test_longest_suffix_wins(self) -> None:
        cov = {"a/util.py": ({1}, set()), "b/a/util.py": ({2}, set())}
        (self.dir / "b" / "a").mkdir(parents=True)
        (self.dir / "b" / "a" / "util.py").write_text("")
        self.assertEqual(g.coverage_for(cov, self.dir / "b" / "a" / "util.py"), ({2}, set()))

    def test_istanbul_json(self) -> None:
        stmt = {"0": {"start": {"line": 1}, "end": {"line": 1}}, "1": {"start": {"line": 2}, "end": {"line": 3}}}
        (self.dir / "cov.json").write_text(json.dumps(
            {"/p/a.js": {"path": "/p/a.js", "s": {"0": 1, "1": 0}, "statementMap": stmt}}))
        self.assertEqual(g.load_coverage(self.dir / "cov.json")["/p/a.js"], ({1}, {2, 3}))


class XmlCoverageTest(Base):
    def test_jacoco(self) -> None:
        (self.dir / "jacoco.xml").write_text(
            '<report name="x"><package name="com/acme"><sourcefile name="A.java">'
            '<line nr="3" mi="0" ci="2"/><line nr="4" mi="1" ci="0"/><line nr="5" mi="1" ci="1"/>'
            '</sourcefile></package></report>')
        cov = g.load_coverage(self.dir / "jacoco.xml")
        self.assertEqual(cov["com/acme/A.java"], ({3, 5}, {4}))
        target = self.dir / "src" / "main" / "java" / "com" / "acme" / "A.java"
        target.parent.mkdir(parents=True)
        target.write_text("")
        self.assertEqual(g.coverage_for(cov, target), ({3, 5}, {4}))

    def test_cobertura(self) -> None:
        (self.dir / "cobertura.xml").write_text(
            '<coverage><packages><package name="p"><classes><class filename="p/a.py"><lines>'
            '<line number="1" hits="4"/><line number="2" hits="0"/></lines></class></classes></package></packages></coverage>')
        self.assertEqual(g.load_coverage(self.dir / "cobertura.xml")["p/a.py"], ({1}, {2}))


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

    def test_normalize_catches_renamed_variables(self) -> None:
        renamed = (self.BODY.format(name="two").replace("total", "acc").replace("items", "rows")
                   .replace("item", "row").replace("price", "cost").replace("qty", "n"))
        (self.dir / "a.py").write_text(self.BODY.format(name="one") + "\n" + renamed)
        self.assertEqual(self.run_main(dry, ["a.py", "--threshold", "0.95"])[0], g.EXIT_PASS)
        self.assertEqual(self.run_main(dry, ["a.py", "--threshold", "0.95", "--normalize"])[0], g.EXIT_FAIL)

    def test_missing_target_is_not_measured(self) -> None:
        self.assertEqual(self.run_main(dry, ["nope"])[0], g.EXIT_NOT_MEASURED)

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
        return self.run_main(mutate, ["calc.py", "--test-cmd", f'"{sys.executable}" -m unittest test_calc', "--max", "100"])

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

    def test_crlf_source_is_restored_byte_for_byte(self) -> None:
        original = SRC.replace("\n", "\r\n").encode()
        (self.dir / "calc.py").write_bytes(original)
        self.run_with_test('''\
            def test_weak(self):
                self.assertEqual(classify(-1), "neg")
        ''')
        self.assertEqual((self.dir / "calc.py").read_bytes(), original)

    def test_leftover_backup_dir_blocks_run(self) -> None:
        (self.dir / ".mutate-backup").mkdir()
        code, out = self.run_with_test("def test_ok(self):\n    pass\n")
        self.assertEqual(code, g.EXIT_NOT_MEASURED)
        self.assertIn("interrompida", out)

    def test_same_size_mutant_is_not_masked_by_stale_bytecode(self) -> None:
        # `==` -> `!=` mantém o tamanho do arquivo: sem tratar o .pyc, o mutante rodaria o código original
        code, out = self.run_with_test('''\
            def test_zero(self):
                self.assertEqual(classify(0), "zero")
        ''')
        self.assertEqual(code, g.EXIT_FAIL, out)
        self.assertNotIn("== -> !=", out)

    def test_js_token_mutants_only_inside_functions(self) -> None:
        (self.dir / "m.js").write_text(
            'const LIMIT = 1;\nfunction ok(a, b) {\n  const s = "a == b"; // x == y\n  return a == b && true;\n}\n')
        found = {m.desc for m in mutate.generate(self.dir / "m.js", None)}
        self.assertEqual(found, {"== -> !=", "&& -> ||", "true -> false"})

    def test_python_ast_mutants_cover_not_and_constants(self) -> None:
        (self.dir / "p.py").write_text(
            "LIMIT = 1\ndef f(x):\n    if not x or x is None:\n        return 0\n    return True\n")
        mutants = mutate.generate(self.dir / "p.py", None)
        self.assertEqual(sorted(m.desc for m in mutants),
                         sorted(["not x -> x", "or -> and", "is -> is not", "0 -> 1", "True -> False"]))
        for m in mutants:
            compile(m.build(), "p.py", "exec")

    def test_not_measured_when_suite_already_red(self) -> None:
        code, _ = self.run_with_test('''\
            def test_red(self):
                self.fail("vermelho")
        ''')
        self.assertEqual(code, g.EXIT_NOT_MEASURED)


if __name__ == "__main__":
    unittest.main()
