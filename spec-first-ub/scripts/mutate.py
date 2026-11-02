#!/usr/bin/env python3
"""Gate de mutação (equivalente ao `mutator`): altera o código, roda os testes, lista sobreviventes.

Uso:
  mutate.py src/ --test-cmd "python3 -m unittest" [--changed] [--max 60] [--timeout 120]

ATENÇÃO: reescreve os arquivos-fonte NO LUGAR, um mutante por vez, e restaura o
original (byte a byte, com a data de modificação) ao fim, inclusive em Ctrl-C/SIGTERM.
Uma cópia de segurança fica em `.mutate-backup/` durante a execução; se esse diretório
já existir, uma execução anterior foi interrompida e a fonte pode estar alterada:
restaure a partir dele antes de continuar. Rode com a árvore de trabalho commitada ou
com `git stash` à mão. Antes dos mutantes, a suite precisa passar sem alteração.

Mutantes sobreviventes = comportamento que nenhum teste protege (ou código morto).
Cada sobrevivente deve ser morto com um teste novo ou removido.

Como os mutantes são gerados (sem regex):
  Python: sobre a AST (comparações, and/or, not, True/False, 0/1, + - *), regravando
          o arquivo com `ast.unparse` (formatação e comentários não importam no mutante).
  Demais: sobre os tokens do lexer (operadores, true/false, 0/1), só dentro de funções.
          Um mutante que não compila conta como "morto" (falso positivo possível).
Exit: 0 PASS (nenhum sobrevivente), 1 FAIL, 2 NOT_MEASURED.
"""
from __future__ import annotations

import argparse
import ast
import atexit
import os
import random
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import gatelib as g

BACKUP_DIR = ".mutate-backup"

# ---------------------------------------------------------------- Python (AST)

_COMPARE = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE,
            ast.GtE: ast.Gt, ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In}
_ARITH = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div}
_BOOL = {ast.And: ast.Or, ast.Or: ast.And}
_SYMBOL = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Is: "is",
           ast.IsNot: "is not", ast.In: "in", ast.NotIn: "not in", ast.Add: "+", ast.Sub: "-", ast.Mult: "*",
           ast.Div: "/", ast.And: "and", ast.Or: "or"}


@dataclass
class Mutant:
    path: Path
    line: int
    desc: str
    build: Callable[[], str]  # devolve o novo conteúdo do arquivo; chamado só na hora de rodar


def _describe(old: type, new: type) -> str:
    return f"{_SYMBOL[old]} -> {_SYMBOL[new]}"


def _replace_child(tree: ast.AST, old: ast.AST, new: ast.AST) -> None:
    for node in ast.walk(tree):
        for name, value in ast.iter_fields(node):
            if value is old:
                setattr(node, name, new)
                return
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if item is old:
                        value[i] = new
                        return


def _python_sites(tree: ast.AST) -> list[tuple[int, int, str, Callable[[ast.AST, ast.AST], None]]]:
    """(índice do nó no ast.walk, linha, descrição, função que aplica a mutação a (árvore, nó))."""
    inside: set[int] = set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inside.update(id(n) for n in ast.walk(fn))
    sites = []
    for index, node in enumerate(ast.walk(tree)):
        if id(node) not in inside or not hasattr(node, "lineno"):
            continue
        line = node.lineno
        if isinstance(node, ast.Compare):
            for k, op in enumerate(node.ops):
                if type(op) in _COMPARE:
                    new = _COMPARE[type(op)]
                    sites.append((index, line, _describe(type(op), new),
                                  lambda _t, n, k=k, new=new: n.ops.__setitem__(k, new())))
        elif isinstance(node, ast.BoolOp):
            new = _BOOL[type(node.op)]
            sites.append((index, line, _describe(type(node.op), new), lambda _t, n, new=new: setattr(n, "op", new())))
        elif isinstance(node, (ast.BinOp, ast.AugAssign)) and type(node.op) in _ARITH:
            new = _ARITH[type(node.op)]
            sites.append((index, line, _describe(type(node.op), new), lambda _t, n, new=new: setattr(n, "op", new())))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            sites.append((index, line, "not x -> x", lambda t, n: _replace_child(t, n, n.operand)))
        elif isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool):
                sites.append((index, line, f"{value} -> {not value}", lambda _t, n: setattr(n, "value", not n.value)))
            elif isinstance(value, int) and value in (0, 1):
                sites.append((index, line, f"{value} -> {1 - value}", lambda _t, n: setattr(n, "value", 1 - n.value)))
    return sites


def _python_mutants(path: Path, original: str, lines: set[int] | None) -> list[Mutant]:
    try:
        tree = ast.parse(original)
    except SyntaxError:
        return []

    def build(index: int, apply: Callable[[ast.AST, ast.AST], None]) -> Callable[[], str]:
        def run() -> str:
            fresh = ast.parse(original)  # árvore nova a cada mutante; a ordem de ast.walk é determinística
            apply(fresh, list(ast.walk(fresh))[index])
            return ast.unparse(ast.fix_missing_locations(fresh)) + "\n"
        return run

    return [Mutant(path, line, desc, build(index, apply))
            for index, line, desc, apply in _python_sites(tree) if lines is None or line in lines]


# ---------------------------------------------------------------- demais linguagens (tokens)

_TOKEN_SWAPS = {"==": "!=", "!=": "==", "===": "!==", "!==": "===", "<=": "<", ">=": ">", "&&": "||", "||": "&&",
                "true": "false", "false": "true"}
_SPACED_SWAPS = {"<": "<=", ">": ">=", "+": "-", "-": "+", "*": "/"}  # ambíguos (genéricos, unário): só entre espaços
_NUMBER_SWAPS = {"0": "1", "1": "0"}


def _token_mutants(path: Path, original: str, lines: set[int] | None) -> list[Mutant]:
    ranges = [(f.start, f.end) for f in g.find_functions(path)]
    out = []
    for tok in g.lex(original, path.suffix):
        if tok.kind == "com" or tok.kind == "str":
            continue
        if lines is not None and tok.line not in lines:
            continue
        if not any(a <= tok.line <= b for a, b in ranges):
            continue  # só dentro de funções: evita mutar imports e constantes
        if tok.kind == "id":
            repl = _TOKEN_SWAPS.get(tok.text) if tok.text in ("true", "false") else None
        elif tok.kind == "num":
            repl = _NUMBER_SWAPS.get(tok.text)
        elif tok.text in _TOKEN_SWAPS:
            repl = _TOKEN_SWAPS[tok.text]
        elif tok.text in _SPACED_SWAPS and original[tok.pos - 1:tok.pos] == " " and original[tok.end:tok.end + 1] == " ":
            repl = _SPACED_SWAPS[tok.text]
        else:
            repl = None
        if repl is not None:
            out.append(Mutant(path, tok.line, f"{tok.text} -> {repl}",
                              lambda t=tok, r=repl: original[:t.pos] + r + original[t.end:]))
    return out


def generate(path: Path, lines: set[int] | None) -> list[Mutant]:
    original = g.read_source(path)
    if path.suffix == ".py":
        return _python_mutants(path, original, lines)
    return _token_mutants(path, original, lines)


# ---------------------------------------------------------------- execução

def run_tests(cmd: str, timeout: int) -> bool:
    """True se a suite passou. Timeout conta como falha (mutante morto: laço infinito)."""
    # Sem bytecode: o cache .pyc é validado por (mtime em segundos, tamanho), e um mutante de mesmo tamanho
    # (== -> !=) gravado no mesmo segundo reaproveitaria o .pyc do código original.
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout, env=env).returncode == 0
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
    g.force_utf8_output()

    backup_dir = Path(BACKUP_DIR).resolve()
    if backup_dir.exists():
        print(g.verdict_line("Mutação", "NOT_MEASURED",
                             f"{BACKUP_DIR}/ existe: uma execução anterior foi interrompida e a fonte pode estar "
                             "mutada; restaure os arquivos a partir dele e apague o diretório"))
        return g.EXIT_NOT_MEASURED

    changes = g.changed_lines(args.base) if args.changed else None
    if args.changed and changes is None:
        print(g.verdict_line("Mutação", "NOT_MEASURED", "--changed exige repositório git"))
        return g.EXIT_NOT_MEASURED

    try:
        files = g.collect_files(args.paths)
    except FileNotFoundError as missing:
        print(g.verdict_line("Mutação", "NOT_MEASURED", f"alvo inexistente: {missing}"))
        return g.EXIT_NOT_MEASURED

    if not run_tests(args.test_cmd, args.timeout):
        print(g.verdict_line("Mutação", "NOT_MEASURED", "a suite não passa sem mutação; corrija antes"))
        return g.EXIT_NOT_MEASURED

    candidates: list[Mutant] = []
    for f in files:
        if args.changed and f.resolve() not in changes:
            continue
        candidates += generate(f, changes[f.resolve()] if args.changed else None)
    if not candidates:
        print(g.verdict_line("Mutação", "NOT_MEASURED", "nenhum mutante gerado (linguagem ou escopo sem alvos)"))
        return g.EXIT_NOT_MEASURED
    total = len(candidates)
    if total > args.max:
        candidates = random.Random(args.seed).sample(candidates, args.max)
    candidates.sort(key=lambda c: (str(c.path), c.line))

    originals = {m.path.resolve(): (m.path.resolve().read_bytes(), m.path.resolve().stat()) for m in candidates}
    backup_dir.mkdir()
    for i, (f, (data, _)) in enumerate(originals.items()):
        (backup_dir / f"{i}.bak").write_bytes(f"{f}\n".encode("utf-8") + data)

    def restore() -> None:
        for f, (data, stat) in originals.items():
            f.write_bytes(data)
            os.utime(f, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    atexit.register(restore)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: sys.exit(130))

    survivors = []
    try:
        for k, m in enumerate(candidates, start=1):
            target = m.path.resolve()
            stat = originals[target][1]
            target.write_bytes(m.build().encode("utf-8"))
            mtime = stat.st_mtime_ns + k * 2_000_000_000  # mtime distinto do original: invalida .pyc residual
            os.utime(target, ns=(mtime, mtime))
            if run_tests(args.test_cmd, args.timeout):
                survivors.append(m)
            data, stat = originals[target]
            target.write_bytes(data)
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    finally:
        restore()
        atexit.unregister(restore)
        shutil.rmtree(backup_dir, ignore_errors=True)

    killed = len(candidates) - len(survivors)
    for m in survivors:
        print(f"SOBREVIVEU  {m.path}:{m.line}  {m.desc}")
    sample = f" (amostra de {len(candidates)} entre {total})" if total > len(candidates) else ""
    summary = f"{killed}/{len(candidates)} mutantes mortos{sample}"
    if survivors:
        print(g.verdict_line("Mutação", "FAIL", f"{summary}; {len(survivors)} sobrevivente(s)"))
        return g.EXIT_FAIL
    print(g.verdict_line("Mutação", "PASS", summary))
    return g.EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
