#!/usr/bin/env python3
"""Arquiva uma mudança spec-first-ub concluída: move `specs/<slug>/` para `specs/archive/<data>-<slug>/`.

Só arquiva o que passa no `--gate verify` de `check_spec.py` (tasks fechadas, gates de qualidade
em PASS/WAIVED e `status: converged`). Não apaga nada, não faz commit e recusa sobrescrever destino.

Saída: `ARCHIVE: PASS|FAIL ...`; códigos 0 (arquivado ou dry-run ok), 1 (recusado), 2 (uso inválido).
"""
from __future__ import annotations

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

from check_spec import check_directory

ARCHIVE_DIR = "archive"


def archive_target(feature_dir: Path, date: dt.date) -> Path:
    """`<pai>/archive/<AAAA-MM-DD>-<nome>`; o diretório `archive` fica ao lado das specs ativas."""
    return feature_dir.parent / ARCHIVE_DIR / f"{date.isoformat()}-{feature_dir.name}"


def plan_archive(feature_dir: Path, date: dt.date) -> tuple[Path | None, list[str]]:
    """Destino do arquivamento e a lista de motivos para recusar (vazia se pode arquivar)."""
    feature_dir = feature_dir.resolve()
    if feature_dir.parent.name == ARCHIVE_DIR:
        return None, [f"{feature_dir.name} já está arquivada em {feature_dir.parent}"]
    errors = [f"verify: {e}" for e in check_directory(feature_dir, "verify")]
    target = archive_target(feature_dir, date)
    if target.exists():
        errors.append(f"destino já existe: {target}")
    return target, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature_dir", type=Path, help="Diretório da mudança, ex.: specs/002-exportar-pedidos-csv")
    parser.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today(),
                        help="Data do prefixo (AAAA-MM-DD); padrão: hoje")
    parser.add_argument("--dry-run", action="store_true", help="Só verifica e mostra o destino, sem mover")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if not args.feature_dir.is_dir():
        print(f"ARCHIVE: FAIL diretório inexistente: {args.feature_dir}", file=sys.stderr)
        return 2
    target, errors = plan_archive(args.feature_dir, args.date)
    if errors:
        print(f"ARCHIVE: FAIL — {len(errors)} motivo(s) para não arquivar:")
        for error in errors:
            print(f"  - {error}")
        return 1
    if args.dry_run:
        print(f"ARCHIVE: PASS (dry-run) {args.feature_dir} -> {target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(args.feature_dir.resolve()), str(target))
    print(f"ARCHIVE: PASS {args.feature_dir} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
