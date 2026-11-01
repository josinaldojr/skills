#!/usr/bin/env python3
"""Gate CRAP (equivalente ao `crapper`): CRAP = comp² × (1 − cobertura)³ + comp.

Uso:
  crap.py src/ --coverage coverage.json [--changed] [--threshold 10]

Cobertura aceita: coverage.py JSON (`coverage json`), lcov, perfil do Go (`-coverprofile`).
Saída: tabela e uma linha `GATE CRAP: PASS|FAIL|NOT_MEASURED`.
Exit: 0 PASS, 1 FAIL, 2 NOT_MEASURED. Sem cobertura não há CRAP: nunca assume 0% nem 100%.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import gatelib as g


def crap(complexity: int, coverage: float) -> float:
    return complexity ** 2 * (1 - coverage) ** 3 + complexity


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="arquivos ou diretórios de código")
    ap.add_argument("--coverage", required=True, help="arquivo de cobertura (json, lcov ou go cover profile)")
    ap.add_argument("--threshold", type=float, default=10.0, help="limite exclusivo (padrão 10)")
    ap.add_argument("--changed", action="store_true", help="só funções tocadas pelo `git diff HEAD`")
    ap.add_argument("--base", default="HEAD", help="base do diff para --changed")
    args = ap.parse_args(argv)

    cov_path = Path(args.coverage)
    if not cov_path.is_file():
        print(g.verdict_line("CRAP", "NOT_MEASURED", f"cobertura ausente: {cov_path}"))
        return g.EXIT_NOT_MEASURED
    cov = g.load_coverage(cov_path)

    changes = g.changed_lines(args.base) if args.changed else None
    if args.changed and changes is None:
        print(g.verdict_line("CRAP", "NOT_MEASURED", "--changed exige repositório git"))
        return g.EXIT_NOT_MEASURED

    rows, unmatched = [], set()
    for f in g.collect_files(args.paths):
        if args.changed and f.resolve() not in changes:
            continue
        file_cov = g.coverage_for(cov, f)
        if file_cov is None:
            unmatched.add(f)
            continue
        for fn in g.find_functions(f):
            if args.changed and not g.in_changes((fn.start, fn.end), changes[f.resolve()]):
                continue
            c = g.function_coverage(fn, file_cov)
            rows.append((crap(fn.complexity, c), fn, c))

    if unmatched:
        print("Sem dados de cobertura para: " + ", ".join(sorted(map(str, unmatched))), file=sys.stderr)
    if not rows:
        print(g.verdict_line("CRAP", "NOT_MEASURED", "nenhuma função medida"))
        return g.EXIT_NOT_MEASURED

    rows.sort(key=lambda r: -r[0])
    print(f"{'CRAP':>7} {'comp':>4} {'cob':>5}  função")
    for score, fn, c in rows:
        flag = " <-- acima do limite" if score >= args.threshold else ""
        print(f"{score:7.1f} {fn.complexity:4d} {c:5.0%}  {fn.path}:{fn.start} {fn.name}{flag}")

    bad = [r for r in rows if r[0] >= args.threshold]
    if bad:
        print(g.verdict_line("CRAP", "FAIL", f"{len(bad)} de {len(rows)} funções com CRAP >= {args.threshold:g}"))
        return g.EXIT_FAIL
    if unmatched:
        print(g.verdict_line("CRAP", "NOT_MEASURED", f"{len(unmatched)} arquivo(s) sem cobertura"))
        return g.EXIT_NOT_MEASURED
    print(g.verdict_line("CRAP", "PASS", f"{len(rows)} funções, maior CRAP {rows[0][0]:.1f}"))
    return g.EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
