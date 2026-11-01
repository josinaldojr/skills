#!/usr/bin/env python3
"""Gate de mutação (equivalente ao `mutator`): altera o código, roda os testes, lista sobreviventes.

Uso:
  mutate.py src/ --test-cmd "python3 -m unittest" [--changed] [--max 60] [--timeout 120]

ATENÇÃO: reescreve os arquivos-fonte NO LUGAR, um mutante por vez, e restaura o
original ao fim (inclusive em Ctrl-C/SIGTERM). Uma cópia de segurança fica em
`.mutate-backup/` durante a execução. Rode com a árvore de trabalho commitada ou
com `git stash` à mão. Antes dos mutantes, a suite precisa passar sem alteração.

Mutantes sobreviventes = comportamento que nenhum teste protege (ou código morto).
Cada sobrevivente deve ser morto com um teste novo ou removido. Limitações: mutação
textual por linha; em linguagens que não são Python um mutante que não compila
conta como "morto" (falso positivo possível).
Exit: 0 PASS (nenhum sobrevivente), 1 FAIL, 2 NOT_MEASURED.
"""
from __future__ import annotations

import argparse
import ast
import atexit
import random
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import gatelib as g

# (padrão, substituição); só em código, nunca em strings/comentários.
OPERATORS: list[tuple[str, str]] = [
    (r"==", "!="), (r"!=", "=="),
    (r"(?<![<>=!])<=(?!=)", "<"), (r"(?<![<>=!-])>=(?!=)", ">"),
    (r" < ", " <= "), (r" > ", " >= "),
    (r"&&", "||"), (r"\|\|", "&&"),
    (r"\band\b", "or"), (r"\bor\b", "and"),
    (r"\bTrue\b", "False"), (r"\bFalse\b", "True"),
    (r"\btrue\b", "false"), (r"\bfalse\b", "true"),
    (r" \+ ", " - "), (r" - ", " + "), (r" \* ", " / "),
    (r"(?<![\w.])0(?![\w.])", "1"), (r"(?<![\w.])1(?![\w.])", "0"),
]


def generate(path: Path, lines: set[int] | None) -> list[tuple[int, str, str]]:
    """(linha, descrição, novo conteúdo do arquivo) para cada mutante candidato."""
    original = path.read_text(encoding="utf-8")
    clean = g._blank_strings_and_comments(original, path.suffix).splitlines()
    raw = original.splitlines(keepends=True)
    ranges = [(f.start, f.end) for f in g.find_functions(path)]
    out = []
    for i, code in enumerate(clean, start=1):
        if lines is not None and i not in lines:
            continue
        if ranges and not any(a <= i <= b for a, b in ranges):
            continue  # só dentro de funções: evita mutar imports e constantes
        if not code.strip():
            continue
        for pattern, repl in OPERATORS:
            for m in re.finditer(pattern, code):
                # a coluna é a mesma no texto original, pois strings/comentários foram trocados por espaços
                new_line = raw[i - 1][:m.start()] + repl + raw[i - 1][m.end():]
                mutated = "".join(raw[:i - 1]) + new_line + "".join(raw[i:])
                if path.suffix == ".py":
                    try:
                        ast.parse(mutated)
                    except SyntaxError:
                        continue
                out.append((i, f"{m.group(0).strip()} -> {repl.strip()}", mutated))
    return out


def run_tests(cmd: str, timeout: int) -> bool:
    """True se a suite passou. Timeout conta como falha (mutante morto: laço infinito)."""
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--test-cmd", required=True, help="comando que sai com 0 se a suite passa")
    ap.add_argument("--changed", action="store_true", help="só linhas tocadas pelo `git diff HEAD`")
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--max", type=int, default=60, help="máximo de mutantes (amostra aleatória reprodutível)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=120, help="segundos por execução da suite")
    args = ap.parse_args(argv)

    changes = g.changed_lines(args.base) if args.changed else None
    if args.changed and changes is None:
        print(g.verdict_line("Mutação", "NOT_MEASURED", "--changed exige repositório git"))
        return g.EXIT_NOT_MEASURED

    if not run_tests(args.test_cmd, args.timeout):
        print(g.verdict_line("Mutação", "NOT_MEASURED", "a suite não passa sem mutação; corrija antes"))
        return g.EXIT_NOT_MEASURED

    candidates: list[tuple[Path, int, str, str]] = []
    for f in g.collect_files(args.paths):
        if args.changed and f.resolve() not in changes:
            continue
        lines = changes[f.resolve()] if args.changed else None
        candidates += [(f, n, d, m) for n, d, m in generate(f, lines)]
    if not candidates:
        print(g.verdict_line("Mutação", "NOT_MEASURED", "nenhum mutante gerado (linguagem ou escopo sem alvos)"))
        return g.EXIT_NOT_MEASURED
    total = len(candidates)
    if total > args.max:
        candidates = random.Random(args.seed).sample(candidates, args.max)
    candidates.sort(key=lambda c: (str(c[0]), c[1]))

    backup_dir = Path(".mutate-backup").resolve()
    originals = {f.resolve(): f.read_text(encoding="utf-8") for f, *_ in candidates}
    backup_dir.mkdir(exist_ok=True)
    for i, (f, text) in enumerate(originals.items()):
        (backup_dir / f"{i}.bak").write_text(f"{f}\n{text}", encoding="utf-8")

    def restore() -> None:
        for f, text in originals.items():
            f.write_text(text, encoding="utf-8")

    atexit.register(restore)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sys.exit(130))

    survivors = []
    try:
        for f, line, desc, mutated in candidates:
            target = f.resolve()
            target.write_text(mutated, encoding="utf-8")
            if run_tests(args.test_cmd, args.timeout):
                survivors.append((f, line, desc))
            target.write_text(originals[target], encoding="utf-8")
    finally:
        restore()
        atexit.unregister(restore)
        shutil.rmtree(backup_dir, ignore_errors=True)

    killed = len(candidates) - len(survivors)
    for f, line, desc in survivors:
        print(f"SOBREVIVEU  {f}:{line}  {desc}")
    sample = f" (amostra de {len(candidates)} entre {total})" if total > len(candidates) else ""
    summary = f"{killed}/{len(candidates)} mutantes mortos{sample}"
    if survivors:
        print(g.verdict_line("Mutação", "FAIL", f"{summary}; {len(survivors)} sobrevivente(s)"))
        return g.EXIT_FAIL
    print(g.verdict_line("Mutação", "PASS", summary))
    return g.EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
