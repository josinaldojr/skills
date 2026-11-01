"""Testes de regressão do validador estrutural."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from check_spec import check_directory

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "002-exportar-pedidos-csv"
FIX_EXAMPLE = ROOT / "examples" / "001-fix-desconto-centavos"


class CheckSpecTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "feature"
        shutil.copytree(EXAMPLE, self.path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def replace(self, name: str, old: str, new: str) -> None:
        file = self.path / name
        content = file.read_text(encoding="utf-8")
        assert old in content
        file.write_text(content.replace(old, new), encoding="utf-8")

    def test_check_passes_valid_draft(self) -> None:
        self.assertEqual([], check_directory(self.path, "check"))

    def test_implement_fails_without_approval(self) -> None:
        self.assertTrue(any("requer status: approved" in x for x in check_directory(self.path, "implement")))

    def test_implement_passes_with_approval_marked(self) -> None:
        for name in ("spec.md", "plan.md", "tasks.md"):
            self.replace(name, "status: draft", "status: approved")
        self.assertEqual([], check_directory(self.path, "implement"))

    def test_orphan_acceptance_fails(self) -> None:
        self.replace("tasks.md", "[AC-002]", "[AC-099]")
        errors = check_directory(self.path, "check")
        self.assertTrue(any("AC sem task: AC-002" in x for x in errors))
        self.assertTrue(any("AC ausente AC-099" in x for x in errors))

    def test_duplicate_task_fails(self) -> None:
        self.replace("tasks.md", "**TASK-002**", "**TASK-001**")
        self.assertTrue(any("TASK duplicado" in x for x in check_directory(self.path, "check")))

    def test_verify_requires_evidence(self) -> None:
        self.assertTrue(any("verification.md" in x for x in check_directory(self.path, "verify")))

    def approve_and_close(self) -> None:
        for name in ("spec.md", "plan.md", "tasks.md"):
            self.replace(name, "status: draft", "status: approved")
        tasks = (self.path / "tasks.md").read_text(encoding="utf-8").replace("- [ ]", "- [x]")
        (self.path / "tasks.md").write_text(tasks, encoding="utf-8")

    def write_verification(self, mutation_status: str) -> None:
        rows = "\n".join(f"| {g} | ferramenta | {mutation_status if g == 'Mutação' else 'PASS'} | evidência registrada |"
                         for g in ("Testes", "Lint/compilação", "CRAP", "Duplicação", "Mutação", "Revisão"))
        (self.path / "verification.md").write_text(
            "---\nfeature: x\nstatus: converged\n---\n\n# Verification\n\nAC-001 AC-002 AC-003 ok\n\n"
            "| Gate | Ferramenta | Status | Evidência |\n|---|---|---|---|\n" + rows + "\n", encoding="utf-8")

    def test_verify_passes_with_all_gates(self) -> None:
        self.approve_and_close()
        self.write_verification("PASS")
        self.assertEqual([], check_directory(self.path, "verify"))

    def test_verify_blocks_unmeasured_gate(self) -> None:
        self.approve_and_close()
        self.write_verification("NOT_MEASURED")
        self.assertTrue(any("gate Mutação com status NOT_MEASURED" in x for x in check_directory(self.path, "verify")))


class BriefTrackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fix"
        shutil.copytree(FIX_EXAMPLE, self.path)
        self.brief = self.path / "brief.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, old: str, new: str) -> None:
        content = self.brief.read_text(encoding="utf-8")
        assert old in content
        self.brief.write_text(content.replace(old, new), encoding="utf-8")

    def test_brief_passes_check(self) -> None:
        self.assertEqual([], check_directory(self.path, "check"))

    def test_brief_implement_requires_approval(self) -> None:
        self.assertTrue(any("requer status: approved" in x for x in check_directory(self.path, "implement")))

    def test_brief_implement_passes_when_approved(self) -> None:
        self.write("status: draft", "status: approved")
        self.assertEqual([], check_directory(self.path, "implement"))

    def test_brief_orphan_acceptance_fails(self) -> None:
        self.write("[AC-001] Arredondar", "[AC-099] Arredondar")
        self.assertTrue(any("AC ausente AC-099" in x for x in check_directory(self.path, "check")))

    def test_brief_verify_requires_converged_and_open_task_closed(self) -> None:
        errors = check_directory(self.path, "verify")
        self.assertTrue(any("requer status: converged" in x for x in errors))
        self.assertTrue(any("Task ainda aberta" in x for x in errors))

    def test_brief_verify_passes_with_evidence(self) -> None:
        self.write("status: draft", "status: converged")
        self.write("- [ ] **TASK-001**", "- [x] **TASK-001**")
        self.write("| AC-001 | suíte do módulo de pedidos | NOT_RUN |", "| AC-001 | suíte do módulo de pedidos | PASS |")
        for gate in ("Testes", "Lint/compilação", "Revisão"):
            self.mark(gate, "PASS", "evidência registrada")
        self.assertEqual([], check_directory(self.path, "verify"))

    def mark(self, gate: str, status: str, evidence: str) -> None:
        lines = self.brief.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.startswith(f"| {gate} |"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                lines[i] = f"| {cells[0]} | {cells[1]} | {status} | {evidence} |"
        self.brief.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def converge(self) -> None:
        self.write("status: draft", "status: converged")
        self.write("- [ ] **TASK-001**", "- [x] **TASK-001**")
        for gate in ("Testes", "Lint/compilação", "Revisão"):
            self.mark(gate, "PASS", "evidência registrada")

    def test_brief_verify_blocks_not_measured_required_gate(self) -> None:
        self.converge()
        self.mark("Lint/compilação", "NOT_MEASURED", "linter indisponível")
        errors = check_directory(self.path, "verify")
        self.assertTrue(any("gate Lint/compilação com status NOT_MEASURED" in x for x in errors))

    def test_brief_verify_ignores_optional_gates_absent(self) -> None:
        self.converge()
        self.assertEqual([], check_directory(self.path, "verify"))

    def test_brief_verify_blocks_failed_optional_gate(self) -> None:
        self.converge()
        self.write("Log:", "| CRAP | crapper | FAIL | função com CRAP 14 |\n\nLog:")
        self.assertTrue(any("gate CRAP com status FAIL" in x for x in check_directory(self.path, "verify")))

    def test_brief_verify_waived_requires_justification(self) -> None:
        self.converge()
        self.mark("Revisão", "WAIVED", "")
        self.assertTrue(any("WAIVED sem justificativa" in x for x in check_directory(self.path, "verify")))
        self.mark("Revisão", "WAIVED", "usuário dispensou a revisão formal")
        self.assertFalse(any("Revisão" in x for x in check_directory(self.path, "verify")))

    def test_brief_verify_requires_three_mandatory_gates(self) -> None:
        self.converge()
        self.write("| Testes |", "| Outro |")
        self.assertTrue(any("gate de qualidade ausente: Testes" in x for x in check_directory(self.path, "verify")))


if __name__ == "__main__":
    unittest.main()
