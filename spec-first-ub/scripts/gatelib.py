"""Código compartilhado dos gates CRAP, duplicação e mutação (stdlib apenas).

Linguagens: Python (via ast, preciso) e JS/TS, Go e Java (heurística por regex
e contagem de chaves; aproximada). Os scripts relatam a limitação na saída.
"""
from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SOURCE_EXT = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".go", ".java"}
SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build", "target"}
TEST_NAME = re.compile(r"(^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.[jt]sx?$|Test\.java$|Tests\.java$)")

EXIT_PASS, EXIT_FAIL, EXIT_NOT_MEASURED = 0, 1, 2


@dataclass
class Func:
    path: Path
    name: str
    start: int  # 1-based, inclusive
    end: int
    complexity: int
    tokens: list[str]


# ---------------------------------------------------------------- arquivos

def is_test_file(path: Path) -> bool:
    return bool(TEST_NAME.search(path.name)) or "tests" in path.parts or "test" in path.parts


def collect_files(targets: list[str], include_tests: bool = False) -> list[Path]:
    files: list[Path] = []
    for target in targets:
        p = Path(target)
        candidates = [p] if p.is_file() else sorted(q for q in p.rglob("*") if q.is_file())
        for q in candidates:
            if q.suffix not in SOURCE_EXT or SKIP_DIRS & set(q.parts):
                continue
            if not include_tests and is_test_file(q):
                continue
            files.append(q)
    return files


def _git(args: list[str]) -> str | None:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
        return out.stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def changed_lines(base: str = "HEAD") -> dict[Path, set[int] | None] | None:
    """Arquivo -> linhas alteradas (None = arquivo inteiro, p. ex. não rastreado). None se não há git."""
    diff = _git(["diff", "-U0", base])
    if diff is None:
        return None
    root = Path((_git(["rev-parse", "--show-toplevel"]) or ".").strip())
    result: dict[Path, set[int] | None] = {}
    current: Path | None = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = (root / line[6:]).resolve()
            result.setdefault(current, set())
        elif line.startswith("@@") and current is not None:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start, count = int(m.group(1)), int(m.group(2) or 1)
                lines = result[current]
                if lines is not None:
                    lines.update(range(start, start + max(count, 1)))
    for rel in (_git(["ls-files", "-o", "--exclude-standard"]) or "").splitlines():
        result[(root / rel).resolve()] = None
    return result


def in_changes(func_range: tuple[int, int], lines: set[int] | None) -> bool:
    return lines is None or any(func_range[0] <= n <= func_range[1] for n in lines)


# ---------------------------------------------------------------- funções

def _blank_strings_and_comments(src: str, ext: str) -> str:
    """Troca strings e comentários por espaços, preservando quebras de linha e posições."""
    line_comment = r"#.*" if ext == ".py" else r"//.*"
    pattern = re.compile(
        r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`[\s\S]*?`|/\*[\s\S]*?\*/|'
        + line_comment + ")"
    )

    def blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    return pattern.sub(blank, src)


_DECISION = re.compile(r"\b(?:if|for|while|case|catch)\b|&&|\|\||(?<!\?)\?(?![.?:])")
_TOKEN = re.compile(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|&&|\|\||=>|->|[^\s\w]")

_BRACE_SIGS = {
    ".js": [r"\bfunction\s*\*?\s*(?P<n>\w+)\s*\([^)]*\)\s*\{", r"^\s*(?:async\s+)?(?P<n>\w+)\s*\([^)]*\)\s*\{",
            r"\b(?:const|let|var)\s+(?P<n>\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>\s*\{"],
    ".go": [r"\bfunc\s+(?:\([^)]*\)\s*)?(?P<n>\w+)\s*\([^)]*\)[^{\n]*\{"],
    ".java": [r"^\s*(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)+[\w<>\[\],.? ]+?\s+"
              r"(?P<n>\w+)\s*\([^)]*\)\s*(?:throws\s+[\w., ]+)?\s*\{"],
}
_BRACE_SIGS.update({".jsx": _BRACE_SIGS[".js"], ".mjs": _BRACE_SIGS[".js"],
                    ".ts": _BRACE_SIGS[".js"], ".tsx": _BRACE_SIGS[".js"]})
_NOT_FUNCS = {"if", "for", "while", "switch", "catch", "return", "else", "synchronized"}


def _py_complexity(node: ast.AST) -> int:
    c = 1
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp, ast.Assert)):
            c += 1
        elif isinstance(n, ast.BoolOp):
            c += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            c += 1 + len(n.ifs)
        elif type(n).__name__ == "match_case":
            c += 1
    return c


def _python_functions(path: Path, src: str) -> list[Func]:
    tree = ast.parse(src)
    lines = src.splitlines()
    funcs = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = n.end_lineno or n.lineno
            body = "\n".join(lines[n.lineno - 1:end])
            funcs.append(Func(path, n.name, n.lineno, end, _py_complexity(n), _TOKEN.findall(_blank_strings_and_comments(body, ".py"))))
    return funcs


def _brace_functions(path: Path, src: str) -> list[Func]:
    clean = _blank_strings_and_comments(src, path.suffix)
    funcs: list[Func] = []
    taken: list[tuple[int, int]] = []
    for sig in _BRACE_SIGS.get(path.suffix, []):
        for m in re.finditer(sig, clean, re.M):
            name = m.group("n")
            if name in _NOT_FUNCS:
                continue
            open_pos = m.end() - 1
            depth, pos = 0, open_pos
            while pos < len(clean):
                depth += (clean[pos] == "{") - (clean[pos] == "}")
                if depth == 0:
                    break
                pos += 1
            if depth != 0:
                continue
            span = (m.start(), pos)
            if span in taken:
                continue
            taken.append(span)
            body = clean[m.start("n"):pos + 1]
            start = clean.count("\n", 0, m.start("n")) + 1
            end = clean.count("\n", 0, pos) + 1
            funcs.append(Func(path, name, start, end, 1 + len(_DECISION.findall(body)), _TOKEN.findall(body)))
    return funcs


def find_functions(path: Path) -> list[Func]:
    src = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".py":
        try:
            return _python_functions(path, src)
        except SyntaxError:
            return []
    return _brace_functions(path, src)


# ---------------------------------------------------------------- cobertura

Coverage = dict[str, tuple[set[int], set[int]]]  # caminho -> (linhas cobertas, linhas não cobertas)


def load_coverage(path: Path) -> Coverage:
    """Lê coverage.py JSON (`coverage json`), lcov ou perfil do Go (`-coverprofile`)."""
    text = path.read_text(encoding="utf-8")
    cov: Coverage = {}
    if text.lstrip().startswith("{"):
        import json
        for name, data in json.loads(text).get("files", {}).items():
            cov[name] = (set(data.get("executed_lines", [])), set(data.get("missing_lines", [])))
    elif text.startswith("mode:"):
        for line in text.splitlines()[1:]:
            m = re.match(r"(.+?):(\d+)\.\d+,(\d+)\.\d+ \d+ (\d+)", line)
            if m:
                hit, miss = cov.setdefault(m.group(1), (set(), set()))
                (hit if int(m.group(4)) > 0 else miss).update(range(int(m.group(2)), int(m.group(3)) + 1))
        for hit, miss in cov.values():
            miss -= hit
    else:
        current = ""
        for line in text.splitlines():
            if line.startswith("SF:"):
                current = line[3:]
                cov.setdefault(current, (set(), set()))
            elif line.startswith("DA:") and current:
                num, hits = line[3:].split(",")[:2]
                (cov[current][0] if int(hits) > 0 else cov[current][1]).add(int(num))
    return cov


def coverage_for(cov: Coverage, path: Path) -> tuple[set[int], set[int]] | None:
    resolved = path.resolve().as_posix()
    for name, value in cov.items():
        norm = Path(name).as_posix() if Path(name).is_absolute() else name
        if resolved.endswith("/" + norm.lstrip("./")) or resolved == norm or norm.endswith("/" + path.as_posix().lstrip("./")):
            return value
    return None


def function_coverage(func: Func, file_cov: tuple[set[int], set[int]]) -> float:
    hit = {n for n in file_cov[0] if func.start <= n <= func.end}
    miss = {n for n in file_cov[1] if func.start <= n <= func.end}
    total = len(hit) + len(miss)
    return 1.0 if total == 0 else len(hit) / total


def verdict_line(gate: str, status: str, detail: str) -> str:
    return f"GATE {gate}: {status} — {detail}"
