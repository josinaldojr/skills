#!/usr/bin/env python3
"""Gate de duplicação (equivalente ao `dryer`): pares de funções com similaridade >= 0,8.

Uso:
  dry.py src/ [--threshold 0.8] [--min-tokens 30] [--changed]

Similaridade: razão de difflib sobre os tokens da função (comentários ignorados,
strings viram um token único). Por padrão identificadores NÃO são normalizados:
copiar e renomear ainda conta como similar pelo restante da estrutura. Com
--normalize, nomes e números viram tokens genéricos e só a estrutura é comparada
(clones com variáveis renomeadas). Com --changed, ao menos um lado do par deve ter
sido tocado pelo `git diff HEAD`. Função aninhada em outra do mesmo arquivo não é
comparada com a que a contém.
Exit: 0 PASS, 1 FAIL, 2 NOT_MEASURED.
"""
from __future__ import annotations

import argparse
import difflib
import sys

import gatelib as g


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--threshold", type=float, default=0.8)
    ap.add_argument("--min-tokens", type=int, default=30, help="ignora funções menores que isso")
    ap.add_argument("--normalize", action="store_true", help="compara só a estrutura: identificadores e números viram tokens genéricos")
    ap.add_argument("--changed", action="store_true")
    ap.add_argument("--base", default="HEAD")
    args = ap.parse_args(argv)
    g.force_utf8_output()

    changes = g.changed_lines(args.base) if args.changed else None
    if args.changed and changes is None:
        print(g.verdict_line("Duplicação", "NOT_MEASURED", "--changed exige repositório git"))
        return g.EXIT_NOT_MEASURED

    try:
        files = g.collect_files(args.paths)
    except FileNotFoundError as missing:
        print(g.verdict_line("Duplicação", "NOT_MEASURED", f"alvo inexistente: {missing}"))
        return g.EXIT_NOT_MEASURED

    funcs = [fn for f in files for fn in g.find_functions(f) if len(fn.tokens) >= args.min_tokens]
    if not funcs:
        print(g.verdict_line("Duplicação", "NOT_MEASURED", "nenhuma função com tamanho mínimo encontrada"))
        return g.EXIT_NOT_MEASURED

    def comparable(fn: g.Func) -> list[str]:
        if not args.normalize:
            return fn.tokens
        return ["<id>" if kind == "id" and tok not in g.KEYWORDS else "<num>" if kind == "num" else tok
                for tok, kind in zip(fn.tokens, fn.kinds)]

    def nested(a: g.Func, b: g.Func) -> bool:
        if a.path != b.path:
            return False
        return (a.start <= b.start and b.end <= a.end) or (b.start <= a.start and a.end <= b.end)

    def touched(fn: g.Func) -> bool:
        if changes is None:
            return True
        key = fn.path.resolve()
        return key in changes and g.in_changes((fn.start, fn.end), changes[key])

    tokens = {id(fn): comparable(fn) for fn in funcs}
    pairs = []
    for i, a in enumerate(funcs):
        for b in funcs[i + 1:]:
            if not (touched(a) or touched(b)) or nested(a, b):
                continue
            ta, tb = tokens[id(a)], tokens[id(b)]
            if min(len(ta), len(tb)) / max(len(ta), len(tb)) < args.threshold:
                continue  # limite superior da razão: evita o cálculo caro
            sm = difflib.SequenceMatcher(None, ta, tb, autojunk=False)
            if sm.real_quick_ratio() < args.threshold or sm.quick_ratio() < args.threshold:
                continue
            ratio = sm.ratio()
            if ratio >= args.threshold:
                pairs.append((ratio, a, b))

    pairs.sort(key=lambda p: -p[0])
    for ratio, a, b in pairs:
        print(f"{ratio:.2f}  {a.path}:{a.start} {a.name}  ~  {b.path}:{b.start} {b.name}")
    if pairs:
        print(g.verdict_line("Duplicação", "FAIL", f"{len(pairs)} par(es) com similaridade >= {args.threshold:g}"))
        return g.EXIT_FAIL
    print(g.verdict_line("Duplicação", "PASS", f"{len(funcs)} funções comparadas"))
    return g.EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
