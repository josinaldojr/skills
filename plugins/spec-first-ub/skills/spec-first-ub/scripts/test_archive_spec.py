"""Testes do arquivamento de mudanças concluídas."""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import archive_spec
from archive_spec import plan_archive

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "002-exportar-pedidos-csv"
DATE = dt.date(2026, 11, 8)
GATES = ("Testes", "Lint/compilação", "CRAP", "Duplicação", "Mutação", "Revisão")


class ArchiveSpecTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.specs = Path(self.tmp.name) / "specs"
        self.feature = self.specs / "002-exportar-pedidos-csv"
        shutil.copytree(EXAMPLE, self.feature)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def converge(self) -> None:
        for name in ("spec.md", "plan.md", "tasks.md"):
            file = self.feature / name
            text = file.read_text(encoding="utf-8").replace("status: draft", "status: approved")
            file.write_text(text.replace("- [ ]", "- [x]"), encoding="utf-8")
        rows = "\n".join(f"| {g} | ferramenta | PASS | evidência registrada |" for g in GATES)
        (self.feature / "verification.md").write_text(
            "---\nfeature: x\nstatus: converged\n---\n\n# Verification\n\nAC-001 AC-002 AC-003 ok\n\n"
            "| Gate | Ferramenta | Status | Evidência |\n|---|---|---|---|\n" + rows + "\n", encoding="utf-8")

    def run_main(self, *args: str) -> int:
        argv = ["archive_spec.py", str(self.feature), "--date", DATE.isoformat(), *args]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return archive_spec.main()

    @property
    def target(self) -> Path:
        return self.specs / "archive" / "2026-11-08-002-exportar-pedidos-csv"

    def test_refuses_change_that_did_not_converge(self) -> None:
        _, errors = plan_archive(self.feature, DATE)
        self.assertTrue(any(e.startswith("verify:") for e in errors))
        self.assertEqual(1, self.run_main())
        self.assertTrue(self.feature.is_dir())

    def test_moves_converged_change_to_dated_archive(self) -> None:
        self.converge()
        self.assertEqual(0, self.run_main())
        self.assertFalse(self.feature.exists())
        self.assertTrue((self.target / "spec.md").is_file())
        self.assertTrue((self.target / "verification.md").is_file())

    def test_dry_run_does_not_move(self) -> None:
        self.converge()
        self.assertEqual(0, self.run_main("--dry-run"))
        self.assertTrue(self.feature.is_dir())
        self.assertFalse(self.target.exists())

    def test_refuses_to_overwrite_existing_destination(self) -> None:
        self.converge()
        self.target.mkdir(parents=True)
        _, errors = plan_archive(self.feature, DATE)
        self.assertTrue(any("destino já existe" in e for e in errors))
        self.assertEqual(1, self.run_main())
        self.assertTrue(self.feature.is_dir())

    def test_refuses_already_archived_change(self) -> None:
        self.converge()
        self.assertEqual(0, self.run_main())
        _, errors = plan_archive(self.target, DATE)
        self.assertTrue(any("já está arquivada" in e for e in errors))

    def test_missing_directory_is_usage_error(self) -> None:
        shutil.rmtree(self.feature)
        self.assertEqual(2, self.run_main())


if __name__ == "__main__":
    unittest.main()
