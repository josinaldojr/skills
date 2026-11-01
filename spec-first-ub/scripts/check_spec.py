#!/usr/bin/env python3
"""Preflight estrutural para artefatos spec-first-ub; não faz revisão semântica."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIREMENT = re.compile(r"^\s*-\s+\*\*(REQ-\d{3})(?::\*\*|\*\*\s*:)", re.M)
ACCEPTANCE = re.compile(r"^\s*-\s+\*\*(AC-\d{3})\*\*\s*\((REQ-\d{3})\)\s*:", re.M)
TASK = re.compile(r"^\s*-\s+\[([ xX])\]\s+\*\*(TASK-\d{3})\*\*\s+\[(REQ-\d{3})\]\s+\[(AC-\d{3})\]", re.M)
ANY_REQUIREMENT = re.compile(r"\bREQ-\d{3}\b")
ANY_ACCEPTANCE = re.compile(r"\bAC-\d{3}\b")
ANY_TASK = re.compile(r"\bTASK-\d{3}\b")
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
PLACEHOLDERS = re.compile(r"(?i)\b(?:TBD|TODO|FIXME)\b|<[^\n>]{1,100}>")


def load_doc(path: Path, errors: list[str]) -> tuple[str, dict[str, str]]:
    if not path.is_file():
        errors.append(f"Arquivo ausente: {path.name}")
        return "", {}
    content = path.read_text(encoding="utf-8")
    match = FRONTMATTER.match(content)
    if not match:
        errors.append(f"{path.name}: frontmatter YAML ausente")
        return content, {}
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("\"'").lower()
    if not metadata.get("status"):
        errors.append(f"{path.name}: status não informado")
    if PLACEHOLDERS.search(content):
        errors.append(f"{path.name}: placeholder ou TODO não resolvido")
    return content, metadata


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


def check_directory(feature_dir: Path, gate: str) -> list[str]:
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
    req = REQUIREMENT.findall(spec)
    ac = ACCEPTANCE.findall(spec)
    task = TASK.findall(tasks)
    req_ids = set(req)
    ac_ids = {a for a, _ in ac}
    duplicates(req, "REQ", errors)
    duplicates([a for a, _ in ac], "AC", errors)
    duplicates([t for _, t, _, _ in task], "TASK", errors)
    if not req: errors.append("spec.md: nenhum REQ-### declarado no formato esperado")
    if not ac: errors.append("spec.md: nenhum AC-### vinculado ao REQ no formato esperado")
    if not task: errors.append("tasks.md: nenhuma TASK-### com referência a REQ/AC")

    declared_req_lines = {m.group(1) for m in REQUIREMENT.finditer(spec)}
    declared_ac_lines = {m.group(1) for m in ACCEPTANCE.finditer(spec)}
    for ident in set(ANY_REQUIREMENT.findall(spec)) - declared_req_lines:
        # Pode aparecer em referências textuais; referências externas à lista são válidas.
        if ident not in req_ids:
            errors.append(f"spec.md: referência a requisito sem declaração: {ident}")
    for ident in set(ANY_ACCEPTANCE.findall(spec)) - declared_ac_lines:
        if ident not in ac_ids:
            errors.append(f"spec.md: referência a aceite sem declaração: {ident}")
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
    if gate in ("implement", "verify"):
        metas = {"brief": brief_meta} if single_file else {"spec": spec_meta, "plan": plan_meta, "tasks": tasks_meta}
        for name, meta in metas.items():
            if single_file and gate == "verify":
                continue  # o status exigido no verify é converged, checado abaixo
            if meta.get("status") != "approved":
                errors.append(f"{name}.md: requer status: approved para o gate {gate}")
    if gate == "verify":
        if single_file:
            vmeta = brief_meta
            marker = re.search(r"^##\s+Verificação\s*$", brief, re.M)
            verification = brief[marker.end():] if marker else ""
            if not marker:
                errors.append("brief.md: seção '## Verificação' ausente")
        else:
            verification, vmeta = load_doc(feature_dir / "verification.md", errors)
        if vmeta.get("status") != "converged":
            errors.append(f"{'brief' if single_file else 'verification'}.md: requer status: converged")
        check_quality_gates(verification, "brief.md" if single_file else "verification.md", errors,
                            FIX_REQUIRED if single_file else None)
        for checked, task_id, _, _ in task:
            if checked == " ": errors.append(f"Task ainda aberta: {task_id}")
        for a in sorted(ac_ids):
            if a not in verification: errors.append(f"{'brief' if single_file else 'verification'}.md: sem evidência referenciada para {a}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature_dir", type=Path, help="Diretório com spec.md, plan.md e tasks.md (ou só brief.md na trilha fix)")
    parser.add_argument("--gate", choices=("check", "implement", "verify"), default="check")
    args = parser.parse_args()
    if not args.feature_dir.is_dir():
        print(f"FAIL: diretório inexistente: {args.feature_dir}", file=sys.stderr)
        return 2
    errors = check_directory(args.feature_dir, args.gate)
    if errors:
        print(f"FAIL [{args.gate}] — {len(errors)} erro(s) estrutural(is):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"PASS [{args.gate}] — rastreabilidade estrutural consistente em {args.feature_dir}")
    print("AVISO: não valida semântica, autorização real, teste executado ou qualidade de código.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
