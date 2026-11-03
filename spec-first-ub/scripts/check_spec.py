#!/usr/bin/env python3
"""Preflight estrutural para artefatos spec-first-ub; não faz revisão semântica.

Sem regex: o markdown é lido por um cursor linear (`Cursor`) e por varreduras simples.
Blocos de código cercados e código inline são ignorados ao procurar IDs e placeholders.

Gates, alinhados às ações da skill (explore → propose → apply):
  propose  fim do PROPOSE: artefatos consistentes e rastreáveis, prontos para revisão (alias: check)
  apply    início do APPLY: exige status: approved nos documentos (alias: implement)
  verify   fim do APPLY: tasks fechadas, gates de qualidade e status: converged
`explore` não tem gate: não produz artefato obrigatório.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ID_DIGITS = 3
GATE_ALIASES = {"check": "propose", "implement": "apply"}
GATES = ("propose", "apply", "verify")
PLACEHOLDER_WORDS = {"TBD", "TODO", "FIXME"}
URL_PREFIXES = ("http://", "https://", "mailto:")


# ---------------------------------------------------------------- markdown

def _word_at(text: str, i: int) -> bool:
    return 0 <= i < len(text) and (text[i].isalnum() or text[i] == "_")


class Cursor:
    """Leitor linear sobre uma linha; cada método só avança em caso de sucesso."""

    def __init__(self, text: str, pos: int = 0) -> None:
        self.text, self.pos = text, pos

    def ws(self, required: bool = False) -> bool:
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1
        return self.pos > start or not required

    def eat(self, literal: str) -> bool:
        if self.text.startswith(literal, self.pos):
            self.pos += len(literal)
            return True
        return False

    def ident(self, prefix: str) -> str | None:
        """`PREFIX-ddd` exato: três dígitos ASCII e nenhuma letra/dígito colado depois."""
        end = self.pos + len(prefix) + 1 + ID_DIGITS
        candidate = self.text[self.pos:end]
        digits = candidate[len(prefix) + 1:]
        if (candidate.startswith(prefix + "-") and len(digits) == ID_DIGITS and digits.isascii()
                and digits.isdigit() and not _word_at(self.text, end)):
            self.pos = end
            return candidate
        return None


def find_ids(text: str, prefix: str) -> list[str]:
    """Todas as ocorrências de `PREFIX-ddd` como palavra inteira."""
    found, start, needle = [], 0, prefix + "-"
    while (i := text.find(needle, start)) >= 0:
        start = i + 1
        if _word_at(text, i - 1):
            continue
        ident = Cursor(text, i).ident(prefix)
        if ident:
            found.append(ident)
    return found


def _list_item(line: str) -> Cursor | None:
    """Cursor logo após o marcador `- ` de um item de lista (com indentação), ou None."""
    cursor = Cursor(line)
    cursor.ws()
    if cursor.eat("-") and cursor.ws(required=True):
        return cursor
    return None


def parse_requirement(line: str) -> str | None:
    """`- **REQ-001:** texto` ou `- **REQ-001** : texto`."""
    c = _list_item(line)
    if c is None or not c.eat("**"):
        return None
    ident = c.ident("REQ")
    if ident is None:
        return None
    if c.eat(":**"):
        return ident
    if c.eat("**") and c.ws() and c.eat(":"):
        return ident
    return None


def parse_acceptance(line: str) -> tuple[str, str] | None:
    """`- **AC-001** (REQ-001): texto` -> (AC, REQ)."""
    c = _list_item(line)
    if c is None or not c.eat("**"):
        return None
    ac = c.ident("AC")
    if ac is None or not c.eat("**") or not c.ws() or not c.eat("("):
        return None
    req = c.ident("REQ")
    if req is None or not c.eat(")") or not c.ws() or not c.eat(":"):
        return None
    return ac, req


def parse_task(line: str) -> tuple[str, str, str, str] | None:
    """`- [ ] **TASK-001** [REQ-001] [AC-001] texto` -> (marca, TASK, REQ, AC)."""
    c = _list_item(line)
    if c is None or not c.eat("["):
        return None
    mark = c.text[c.pos:c.pos + 1]
    if mark not in (" ", "x", "X"):
        return None
    c.pos += 1
    if not (c.eat("]") and c.ws(required=True) and c.eat("**")):
        return None
    task = c.ident("TASK")
    if task is None or not c.eat("**") or not c.ws(required=True) or not c.eat("["):
        return None
    req = c.ident("REQ")
    if req is None or not c.eat("]") or not c.ws(required=True) or not c.eat("["):
        return None
    ac = c.ident("AC")
    if ac is None or not c.eat("]"):
        return None
    return mark, task, req, ac


def _blank_inline_code(line: str) -> str:
    """Troca spans `código` (com qualquer número de crases) por espaços."""
    out, i, n = [], 0, len(line)
    while i < n:
        if line[i] != "`":
            out.append(line[i])
            i += 1
            continue
        run = i
        while run < n and line[run] == "`":
            run += 1
        ticks = line[i:run]
        close = line.find(ticks, run)
        # o fecho precisa ter exatamente o mesmo número de crases
        while close >= 0 and close + len(ticks) < n and line[close + len(ticks)] == "`":
            skip = close
            while skip < n and line[skip] == "`":
                skip += 1
            close = line.find(ticks, skip)
        if close < 0:
            out.append(ticks)  # crase sem par: literal
            i = run
        else:
            out.append(" " * (close + len(ticks) - i))
            i = close + len(ticks)
    return "".join(out)


def strip_code(text: str) -> str:
    """Remove blocos cercados (``` ou ~~~) e código inline, preservando a numeração de linhas."""
    out, fence = [], ""
    for line in text.splitlines():
        marker = line.lstrip()[:3]
        if fence:
            if marker == fence:
                fence = ""
            out.append("")
        elif marker in ("```", "~~~"):
            fence = marker
            out.append("")
        else:
            out.append(_blank_inline_code(line))
    return "\n".join(out)


def split_frontmatter(content: str) -> list[str] | None:
    """Linhas do frontmatter YAML (entre dois `---`) ou None se o arquivo não começa com ele."""
    lines = content.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return None


def _words(line: str) -> list[str]:
    words, current = [], []
    for ch in line + " ":
        if ch.isalnum() or ch == "_":
            current.append(ch)
        elif current:
            words.append("".join(current))
            current = []
    return words


def _has_angle_placeholder(line: str) -> bool:
    """`<texto>` de 1 a 100 caracteres sem espaço após `<`; exclui `a < b`, `</tag>`, `<!-- -->` e URLs."""
    start = 0
    while (i := line.find("<", start)) >= 0:
        start = i + 1
        close = line.find(">", i + 1)
        if close < 0:
            return False
        inner = line[i + 1:close]
        if (1 <= len(inner) <= 100 and "<" not in inner and not inner[0].isspace() and inner[0] not in "=/!"
                and not inner.endswith("/") and not inner.startswith(URL_PREFIXES)):
            return True
    return False


def has_placeholder(text: str) -> bool:
    for line in strip_code(text).splitlines():
        if any(w.upper() in PLACEHOLDER_WORDS for w in _words(line)) or _has_angle_placeholder(line):
            return True
    return False


def has_heading(line: str, title: str) -> bool:
    """`## Título` exato (nível 2)."""
    return line.startswith("##") and line[2:3].isspace() and line[2:].strip() == title


def load_doc(path: Path, errors: list[str]) -> tuple[str, dict[str, str]]:
    if not path.is_file():
        errors.append(f"Arquivo ausente: {path.name}")
        return "", {}
    content = path.read_text(encoding="utf-8")
    front = split_frontmatter(content)
    if front is None:
        errors.append(f"{path.name}: frontmatter YAML ausente")
        return content, {}
    metadata: dict[str, str] = {}
    for line in front:
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("\"'").lower()
    if not metadata.get("status"):
        errors.append(f"{path.name}: status não informado")
    if has_placeholder(content):
        errors.append(f"{path.name}: placeholder ou TODO não resolvido")
    return content, metadata


# ---------------------------------------------------------------- gates de qualidade

QUALITY_GATES = (("Testes", "testes"), ("Lint/compilação", "lint"), ("CRAP", "crap"),
                 ("Duplicação", "duplica"), ("Mutação", "muta"), ("Revisão", "revis"))
ACCEPTED_STATUS = {"PASS", "WAIVED"}
FIX_REQUIRED = {"Testes", "Lint/compilação", "Revisão"}


def check_quality_gates(text: str, label: str, errors: list[str], required: set[str] | None = None) -> None:
    """Exige os gates obrigatórios como PASS ou WAIVED (com justificativa); os demais, se presentes, não podem estar FAIL."""
    rows: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.strip().startswith("|") or len(cells) < 4:
            continue
        name = cells[0].lower()
        for title, prefix in QUALITY_GATES:
            if name.startswith(prefix):
                if title in rows:
                    errors.append(f"{label}: gate {title} aparece mais de uma vez")
                rows[title] = (cells[2].strip("` ").upper(), cells[3])
    for title, _ in QUALITY_GATES:
        mandatory = required is None or title in required
        if title not in rows:
            if mandatory:
                errors.append(f"{label}: gate de qualidade ausente: {title}")
            continue
        status, evidence = rows[title]
        if not mandatory:
            if status == "FAIL":
                errors.append(f"{label}: gate {title} com status FAIL")
            continue
        if status not in ACCEPTED_STATUS:
            errors.append(f"{label}: gate {title} com status {status or 'vazio'} (requer PASS ou WAIVED)")
        elif status == "WAIVED" and len(evidence.strip()) < 10:
            errors.append(f"{label}: gate {title} WAIVED sem justificativa na evidência")
        elif status == "PASS" and not evidence.strip():
            errors.append(f"{label}: gate {title} PASS sem evidência")


def duplicates(items: list[str], kind: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for item in items:
        if item in seen:
            errors.append(f"{kind} duplicado: {item}")
        seen.add(item)


# ---------------------------------------------------------------- verificação

def check_directory(feature_dir: Path, gate: str) -> list[str]:
    gate = GATE_ALIASES.get(gate, gate)
    errors: list[str] = []
    single_file = (feature_dir / "brief.md").is_file() and not (feature_dir / "spec.md").is_file()
    if single_file:
        # Trilha fix: brief.md concentra spec, plan, tasks e verificação.
        brief, brief_meta = load_doc(feature_dir / "brief.md", errors)
        spec = plan = tasks = brief
        spec_meta = plan_meta = tasks_meta = brief_meta
    else:
        docs = {name: load_doc(feature_dir / f"{name}.md", errors) for name in ("spec", "plan", "tasks")}
        spec, spec_meta = docs["spec"]
        plan, plan_meta = docs["plan"]
        tasks, tasks_meta = docs["tasks"]

    spec_lines = strip_code(spec).splitlines()
    req = [r for r in map(parse_requirement, spec_lines) if r]
    ac = [a for a in map(parse_acceptance, spec_lines) if a]
    task = [t for t in map(parse_task, strip_code(tasks).splitlines()) if t]
    req_ids = set(req)
    ac_ids = {a for a, _ in ac}
    duplicates(req, "REQ", errors)
    duplicates([a for a, _ in ac], "AC", errors)
    duplicates([t for _, t, _, _ in task], "TASK", errors)
    if not req: errors.append("spec.md: nenhum REQ-### declarado no formato esperado")
    if not ac: errors.append("spec.md: nenhum AC-### vinculado ao REQ no formato esperado")
    if not task: errors.append("tasks.md: nenhuma TASK-### com referência a REQ/AC")

    # Toda menção a REQ/AC em qualquer documento precisa ter declaração na spec.
    documents = {"spec.md": spec} if single_file else {"spec.md": spec, "plan.md": plan, "tasks.md": tasks}
    for name, text in documents.items():
        plain = strip_code(text)
        for ident in sorted(set(find_ids(plain, "REQ")) - req_ids):
            errors.append(f"{name}: referência a requisito sem declaração: {ident}")
        for ident in sorted(set(find_ids(plain, "AC")) - ac_ids):
            errors.append(f"{name}: referência a aceite sem declaração: {ident}")

    for a, r in ac:
        if r not in req_ids: errors.append(f"{a} aponta para requisito ausente {r}")
    covered_req = {r for _, _, r, _ in task}
    covered_ac = {a for _, _, _, a in task}
    for _, task_id, r, a in task:
        if r not in req_ids: errors.append(f"{task_id}: REQ ausente {r}")
        if a not in ac_ids: errors.append(f"{task_id}: AC ausente {a}")
        if (a, r) not in ac: errors.append(f"{task_id}: {a} não pertence a {r}")
    for r in sorted(req_ids - covered_req): errors.append(f"REQ sem task: {r}")
    for a in sorted(ac_ids - covered_ac): errors.append(f"AC sem task: {a}")
    for r in sorted(req_ids - {r for _, r in ac}): errors.append(f"REQ sem AC: {r}")

    if gate in ("apply", "verify"):
        metas = {"brief": brief_meta} if single_file else {"spec": spec_meta, "plan": plan_meta, "tasks": tasks_meta}
        for name, meta in metas.items():
            if single_file and gate == "verify":
                continue  # o status exigido no verify é converged, checado abaixo
            if meta.get("status") != "approved":
                errors.append(f"{name}.md: requer status: approved para o gate {gate}")
    if gate == "verify":
        label = "brief.md" if single_file else "verification.md"
        if single_file:
            vmeta = brief_meta
            brief_lines = brief.splitlines()
            marker = next((i for i, line in enumerate(brief_lines) if has_heading(line, "Verificação")), None)
            verification = "\n".join(brief_lines[marker + 1:]) if marker is not None else ""
            if marker is None:
                errors.append("brief.md: seção '## Verificação' ausente")
        else:
            verification, vmeta = load_doc(feature_dir / "verification.md", errors)
        if vmeta.get("status") != "converged":
            errors.append(f"{label}: requer status: converged")
        check_quality_gates(verification, label, errors, FIX_REQUIRED if single_file else None)
        for checked, task_id, _, _ in task:
            if checked == " ": errors.append(f"Task ainda aberta: {task_id}")
        evidenced = set(find_ids(verification, "AC"))
        for a in sorted(ac_ids - evidenced):
            errors.append(f"{label}: sem evidência referenciada para {a}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature_dir", type=Path, help="Diretório com spec.md, plan.md e tasks.md (ou só brief.md na trilha fix)")
    parser.add_argument(
        "--gate",
        choices=GATES + tuple(GATE_ALIASES),
        default="propose",
        help="propose (alias check), apply (alias implement) ou verify",
    )
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    if not args.feature_dir.is_dir():
        print(f"FAIL: diretório inexistente: {args.feature_dir}", file=sys.stderr)
        return 2
    gate = GATE_ALIASES.get(args.gate, args.gate)
    errors = check_directory(args.feature_dir, gate)
    if errors:
        print(f"FAIL [{gate}] — {len(errors)} erro(s) estrutural(is):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"PASS [{gate}] — rastreabilidade estrutural consistente em {args.feature_dir}")
    print("AVISO: não valida semântica, autorização real, teste executado ou qualidade de código.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
