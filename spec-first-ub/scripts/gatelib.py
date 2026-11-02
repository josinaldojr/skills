"""Código compartilhado dos gates CRAP, duplicação e mutação (stdlib apenas, sem regex).

Linguagens: Python (via `ast` + `tokenize`, preciso) e JS/TS, Go e Java (via lexer
próprio que reconhece strings, comentários e literais regex, e casamento de
chaves/parênteses; fronteiras de função e complexidade são aproximadas). Os
scripts relatam a limitação na saída.
"""
from __future__ import annotations

import ast
import bisect
import io
import json
import keyword
import os
import subprocess
import sys
import tokenize
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

SOURCE_EXT = {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".go", ".java"}
JS_EXT = {".js", ".jsx", ".mjs", ".ts", ".tsx"}
SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__", ".venv", "venv", "dist", "build", "target",
             ".mutate-backup"}
TEST_DIRS = {"tests", "test", "__tests__"}

EXIT_PASS, EXIT_FAIL, EXIT_NOT_MEASURED = 0, 1, 2


def force_utf8_output() -> None:
    """Evita mojibake e UnicodeEncodeError em consoles Windows (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


@dataclass
class Func:
    path: Path
    name: str
    start: int  # 1-based, inclusive
    end: int
    complexity: int
    tokens: list[str]
    kinds: list[str] = field(default_factory=list)  # "id" | "num" | "str" | "op", paralelo a tokens


# ---------------------------------------------------------------- arquivos

def is_test_name(name: str) -> bool:
    if name.endswith(".py"):
        return name.startswith("test_") or name.endswith("_test.py")
    if name.endswith("_test.go"):
        return True
    if name.endswith(("Test.java", "Tests.java")):
        return True
    stem, _, ext = name.rpartition(".")
    if ext in ("js", "jsx", "ts", "tsx"):
        return stem.endswith((".test", ".spec"))
    return False


def collect_files(targets: list[str], include_tests: bool = False) -> list[Path]:
    """Arquivos-fonte sob `targets`. Levanta FileNotFoundError se um alvo não existe."""
    files: list[Path] = []
    for target in targets:
        root = Path(target)
        if not root.exists():
            raise FileNotFoundError(target)
        if root.is_file():
            found = [root]
        else:
            found = []
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
                relative_dirs = Path(dirpath).relative_to(root).parts
                if not include_tests and TEST_DIRS & set(relative_dirs):
                    dirnames[:] = []
                    continue
                found += [Path(dirpath) / n for n in sorted(filenames)]
        for q in found:
            if q.suffix in SOURCE_EXT and (include_tests or not is_test_name(q.name)):
                files.append(q)
    return files


def _git(args: list[str]) -> str | None:
    try:
        out = subprocess.run(["git", "-c", "core.quotepath=off", *args], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", check=True)
        return out.stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def parse_hunk_range(header: str) -> tuple[int, int] | None:
    """`@@ -a,b +c,d @@ ...` -> (c, d); d padrão 1. None se o cabeçalho for inválido."""
    for part in header.split():
        if part.startswith("+"):
            start, _, count = part[1:].partition(",")
            if start.isdigit() and (count == "" or count.isdigit()):
                return int(start), int(count) if count else 1
            return None
    return None


def changed_lines(base: str = "HEAD") -> dict[Path, set[int] | None] | None:
    """Arquivo -> linhas alteradas (None = arquivo inteiro, p. ex. não rastreado). None se não há git."""
    diff = _git(["diff", "-U0", "--no-color", "--no-ext-diff", "--src-prefix=a/", "--dst-prefix=b/", base])
    if diff is None:
        return None
    root = Path((_git(["rev-parse", "--show-toplevel"]) or ".").strip())
    result: dict[Path, set[int] | None] = {}
    current: Path | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            name = line[4:].split("\t", 1)[0]
            if name.startswith("b/"):
                current = (root / name[2:]).resolve()
                result.setdefault(current, set())
            else:
                current = None  # `+++ /dev/null`: arquivo removido; os hunks seguintes não pertencem ao anterior
        elif line.startswith("@@") and current is not None:
            hunk = parse_hunk_range(line)
            lines = result[current]
            if hunk is not None and lines is not None:
                start, count = hunk
                lines.update(range(start, start + max(count, 1)))
    for rel in (_git(["ls-files", "-o", "--exclude-standard"]) or "").splitlines():
        result[(root / rel).resolve()] = None
    return result


def in_changes(func_range: tuple[int, int], lines: set[int] | None) -> bool:
    return lines is None or any(func_range[0] <= n <= func_range[1] for n in lines)


# ---------------------------------------------------------------- lexer (JS/TS/Go/Java)

@dataclass
class Tok:
    kind: str  # "id" | "num" | "str" | "com" | "op"
    text: str
    pos: int
    end: int
    line: int


_OPS3 = {"===", "!==", "<<=", ">>=", ">>>", "&&=", "||=", "??=", "...", "&^="}
_OPS2 = {"==", "!=", "<=", ">=", "&&", "||", "++", "--", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<",
         ">>", "=>", "->", "?.", "??", ":=", "<-", "::", "**", "&^"}
# `/` depois destes tokens inicia um literal regex em JS/TS; depois de id/num/str/`)`/`]`/`}` é divisão.
_REGEX_AFTER_ID = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case",
                   "do", "else", "yield", "await"}
_STRING_QUOTES = ("'", '"', "`")


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch in "_$"


def _is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch in "_$"


def _scan_string(src: str, i: int, ext: str) -> int:
    """`i` aponta para a aspa de abertura; devolve a posição logo após o fechamento."""
    quote, n = src[i], len(src)
    if quote == '"' and ext == ".java" and src.startswith('"""', i):  # bloco de texto
        close = src.find('"""', i + 3)
        return n if close < 0 else close + 3
    raw = quote == "`" and ext == ".go"  # string crua do Go não tem escapes
    i += 1
    while i < n:
        ch = src[i]
        if ch == "\\" and not raw:
            i += 2
            continue
        if ch == quote:
            return i + 1
        if ch == "\n" and quote != "`":
            return i  # string não terminada: não engolir o resto do arquivo
        i += 1
    return n


def _scan_regex(src: str, i: int) -> int:
    """`i` aponta para a `/` de abertura de um literal regex JS; devolve a posição após as flags."""
    n, in_class = len(src), False
    i += 1
    while i < n and src[i] != "\n":
        ch = src[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "[":
            in_class = True
        elif ch == "]":
            in_class = False
        elif ch == "/" and not in_class:
            i += 1
            while i < n and _is_ident_char(src[i]):
                i += 1
            return i
        i += 1
    return i


def _scan_number(src: str, i: int) -> int:
    n = len(src)
    hexadecimal = src.startswith(("0x", "0X"), i)
    i += 1
    while i < n:
        ch = src[i]
        if ch.isalnum() or ch == "_":
            if not hexadecimal and ch in "eE" and i + 1 < n and src[i + 1] in "+-":
                i += 2
            else:
                i += 1
        elif ch == "." and i + 1 < n and src[i + 1].isdigit():
            i += 1
        else:
            break
    return i


def lex(src: str, ext: str) -> list[Tok]:
    """Tokeniza JS/TS/Go/Java. Comentários e strings viram tokens próprios (kind "com"/"str")."""
    toks: list[Tok] = []
    n, i, line = len(src), 0, 1
    is_js = ext in JS_EXT

    def prev_significant() -> Tok | None:
        for t in reversed(toks):
            if t.kind != "com":
                return t
        return None

    def add(kind: str, start: int, end: int) -> None:
        nonlocal line
        toks.append(Tok(kind, src[start:end], start, end, line))
        line += src.count("\n", start, end)

    while i < n:
        ch = src[i]
        if ch == "\n":
            line += 1
            i += 1
        elif ch.isspace():
            i += 1
        elif src.startswith("//", i):
            end = src.find("\n", i)
            end = n if end < 0 else end
            add("com", i, end)
            i = end
        elif src.startswith("/*", i):
            end = src.find("*/", i + 2)
            end = n if end < 0 else end + 2
            add("com", i, end)
            i = end
        elif ch in _STRING_QUOTES:
            end = _scan_string(src, i, ext)
            add("str", i, end)
            i = end
        elif ch == "/" and is_js and _regex_allowed(prev_significant()):
            end = _scan_regex(src, i)
            add("str", i, end)
            i = end
        elif _is_ident_start(ch):
            end = i + 1
            while end < n and _is_ident_char(src[end]):
                end += 1
            add("id", i, end)
            i = end
        elif ch.isdigit() or (ch == "." and i + 1 < n and src[i + 1].isdigit()):
            end = _scan_number(src, i)
            add("num", i, end)
            i = end
        else:
            width = 3 if src[i:i + 3] in _OPS3 else 2 if src[i:i + 2] in _OPS2 else 1
            add("op", i, i + width)
            i += width
    return toks


def _regex_allowed(prev: Tok | None) -> bool:
    if prev is None:
        return True
    if prev.kind == "id":
        return prev.text in _REGEX_AFTER_ID
    if prev.kind in ("num", "str"):
        return False
    return prev.text not in (")", "]", "}")


# ---------------------------------------------------------------- funções (JS/TS/Go/Java)

_NOT_FUNCS = {"if", "for", "while", "switch", "catch", "return", "else", "synchronized", "try", "with", "await",
              "function", "do", "finally", "new", "typeof", "super", "this"}
_NOT_PRIOR = {"new", "return", "extends", "implements", "else", "throw", "await", "yield", "typeof", "in", "of",
              "case", "instanceof"}
_HEADER_FILLER_OPS = {":", "<", ">", "[", "]", ",", ".", "|", "&", "?", "*"}
_DECISION_IDS = {"if", "for", "while", "case", "catch"}
_TERNARY_NOT_BEFORE = {":", ",", ")", ">", "=", ";"}
_GO_DECL = {"func", "type", "var", "const", "import", "package"}
_MAX_HEADER = 40


def _match_brackets(sig: list[Tok]) -> dict[int, int]:
    """índice do abre -> índice do fecha, e o inverso, para (), [] e {}."""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[int] = []
    match: dict[int, int] = {}
    for i, t in enumerate(sig):
        if t.kind != "op":
            continue
        if t.text in "([{" and len(t.text) == 1:
            stack.append(i)
        elif t.text in pairs and len(t.text) == 1:
            while stack and sig[stack[-1]].text != pairs[t.text]:
                stack.pop()  # abertura sem par: descarta
            if stack:
                opener = stack.pop()
                match[opener] = i
                match[i] = opener
    return match


def _skip_generics_back(sig: list[Tok], p: int) -> int:
    """Se sig[p] é `>`, volta até o `<` correspondente e devolve o índice anterior a ele."""
    if p < 0 or sig[p].text != ">":
        return p
    depth = 0
    while p >= 0:
        if sig[p].text == ">":
            depth += 1
        elif sig[p].text == ">>":
            depth += 2
        elif sig[p].text == "<":
            depth -= 1
            if depth <= 0:
                return p - 1
        p -= 1
    return p


def _arrow_name(sig: list[Tok], arrow: int, match: dict[int, int]) -> int | None:
    """Índice do nome de `const nome = (...) => {` ou `nome: (...) => {`; None se anônima."""
    k = arrow - 1
    if k >= 0 and sig[k].text == ")" and k in match:
        k = match[k] - 1
    elif k >= 0 and sig[k].kind == "id":
        k -= 1
    if k >= 0 and sig[k].text == "async":
        k -= 1
    if k >= 1 and sig[k].text in ("=", ":") and sig[k - 1].kind == "id":
        return k - 1
    return None


def _call_header_name(sig: list[Tok], brace: int, match: dict[int, int], lang: str) -> int | None:
    """Para JS/TS/Java: o `{` em `brace` abre o corpo de uma função/método? Devolve o índice do nome."""
    j = brace - 1
    steps = 0
    while j >= 0 and sig[j].text != ")" and steps < _MAX_HEADER:
        t = sig[j]
        if not (t.kind == "id" or (t.kind == "op" and t.text in _HEADER_FILLER_OPS)):
            return None
        j -= 1
        steps += 1
    if j < 0 or sig[j].text != ")" or j not in match:
        return None
    p = _skip_generics_back(sig, match[j] - 1)
    if p < 0 or sig[p].kind != "id" or sig[p].text in _NOT_FUNCS:
        return None
    prior = sig[p - 1] if p > 0 else None
    if lang == "java":
        # método/construtor precisa de tipo ou modificador antes do nome (exclui `new X() {`, chamadas, etc.)
        if prior is None or not ((prior.kind == "id" and prior.text not in _NOT_PRIOR) or prior.text in (">", "]")):
            return None
    elif prior is not None and (prior.text == "." or prior.text == "new"):
        return None
    return p


def _brace_complexity(body: list[Tok]) -> int:
    c = 1
    for i, t in enumerate(body):
        if t.kind == "id" and t.text in _DECISION_IDS:
            c += 1
        elif t.kind == "op":
            if t.text in ("&&", "||"):
                c += 1
            elif t.text == "?":
                prev = body[i - 1].text if i else ""
                nxt = body[i + 1].text if i + 1 < len(body) else ""
                if nxt not in _TERNARY_NOT_BEFORE and prev not in ("<", ",") and nxt not in ("extends", "super"):
                    c += 1
    return c


def _make_func(path: Path, sig: list[Tok], name_idx: int, close_idx: int) -> Func:
    body = sig[name_idx:close_idx + 1]
    tokens = ["<str>" if t.kind == "str" else t.text for t in body]
    return Func(path, sig[name_idx].text, sig[name_idx].line, sig[close_idx].line, _brace_complexity(body),
                tokens, [t.kind for t in body])


def _go_functions(path: Path, sig: list[Tok], match: dict[int, int]) -> list[Func]:
    funcs: list[Func] = []
    for i, t in enumerate(sig):
        if t.kind != "id" or t.text != "func":
            continue
        k = i + 1
        if k < len(sig) and sig[k].text == "(" and k in match:
            after = match[k] + 1  # receptor (método) ou parâmetros (função anônima)
            if not (after + 1 < len(sig) and sig[after].kind == "id" and sig[after + 1].text in ("(", "[")):
                continue  # `func(...)` anônima
            k = after
        if k >= len(sig) or sig[k].kind != "id":
            continue
        name_idx = k
        k += 1
        if k < len(sig) and sig[k].text == "[" and k in match:  # parâmetros de tipo
            k = match[k] + 1
        if k >= len(sig) or sig[k].text != "(" or k not in match:
            continue
        last_line = sig[match[k]].line
        k = match[k] + 1
        body_open = None
        while k < len(sig):
            cur = sig[k]
            if cur.text == "{" and cur.kind == "op":
                if sig[k - 1].text in ("interface", "struct") and k in match:
                    k = match[k] + 1
                    continue
                body_open = k
                break
            if cur.text in ("(", "[") and cur.kind == "op" and k in match:
                k = match[k] + 1
                continue
            if cur.kind == "id" and cur.text in _GO_DECL and cur.line != last_line:
                break  # declaração sem corpo (interface, função externa)
            k += 1
        if body_open is not None and body_open in match:
            funcs.append(_make_func(path, sig, name_idx, match[body_open]))
    return funcs


def _brace_functions(path: Path, src: str) -> list[Func]:
    lang = "go" if path.suffix == ".go" else "java" if path.suffix == ".java" else "js"
    sig = [t for t in lex(src, path.suffix) if t.kind != "com"]
    match = _match_brackets(sig)
    if lang == "go":
        return _go_functions(path, sig, match)
    funcs: list[Func] = []
    for i, t in enumerate(sig):
        if t.text != "{" or t.kind != "op" or i not in match:
            continue
        if i > 0 and sig[i - 1].text == "=>":
            name_idx = _arrow_name(sig, i - 1, match)
        else:
            name_idx = _call_header_name(sig, i, match, lang)
        if name_idx is not None:
            funcs.append(_make_func(path, sig, name_idx, match[i]))
    return funcs


# ---------------------------------------------------------------- funções (Python)

_PY_FSTRING_START = getattr(tokenize, "FSTRING_START", -1)
_PY_FSTRING_SKIP = {getattr(tokenize, "FSTRING_MIDDLE", -1), getattr(tokenize, "FSTRING_END", -1)}
_PY_SKIP = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER}


def _py_complexity(node: ast.AST) -> int:
    match_case = getattr(ast, "match_case", ())
    c = 1
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp, ast.Assert)):
            c += 1
        elif isinstance(n, ast.BoolOp):
            c += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            c += 1 + len(n.ifs)
        elif match_case and isinstance(n, match_case):
            c += 1
    return c


def python_tokens(src: str) -> list[tuple[int, str, str]]:
    """(linha, texto, tipo) sem comentários/espaços; strings viram `<str>`."""
    out: list[tuple[int, str, str]] = []
    try:
        for t in tokenize.generate_tokens(io.StringIO(src).readline):
            if t.type in _PY_SKIP or t.type in _PY_FSTRING_SKIP:
                continue
            if t.type == tokenize.STRING or t.type == _PY_FSTRING_START:
                out.append((t.start[0], "<str>", "str"))
            elif t.type == tokenize.NAME:
                out.append((t.start[0], t.string, "id"))
            elif t.type == tokenize.NUMBER:
                out.append((t.start[0], t.string, "num"))
            else:
                out.append((t.start[0], t.string, "op"))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    return out


def _python_functions(path: Path, src: str) -> list[Func]:
    tree = ast.parse(src)
    toks = python_tokens(src)
    token_lines = [t[0] for t in toks]
    funcs = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = n.end_lineno or n.lineno
            chunk = toks[bisect.bisect_left(token_lines, n.lineno):bisect.bisect_right(token_lines, end)]
            funcs.append(Func(path, n.name, n.lineno, end, _py_complexity(n),
                              [t[1] for t in chunk], [t[2] for t in chunk]))
    return funcs


def read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def find_functions(path: Path) -> list[Func]:
    src = read_source(path)
    if path.suffix == ".py":
        try:
            return _python_functions(path, src)
        except SyntaxError:
            return []
    return _brace_functions(path, src)


KEYWORDS = set(keyword.kwlist) | {
    "function", "const", "let", "var", "class", "extends", "implements", "interface", "static", "public",
    "private", "protected", "final", "void", "new", "this", "throw", "throws", "try", "catch", "finally", "switch",
    "case", "default", "break", "continue", "do", "typeof", "instanceof", "func", "go", "defer", "chan", "select",
    "range", "struct", "map", "package", "import", "type", "return", "true", "false", "null", "nil", "async",
    "await", "super", "enum", "export",
}


# ---------------------------------------------------------------- cobertura

Coverage = dict[str, tuple[set[int], set[int]]]  # caminho -> (linhas cobertas, linhas não cobertas)


def _load_go_profile(text: str) -> Coverage:
    cov: Coverage = {}
    for line in text.splitlines()[1:]:
        fields = line.rsplit(" ", 2)
        if len(fields) != 3:
            continue
        location, _, count = fields
        name, _, span = location.rpartition(":")
        first, _, last = span.partition(",")
        first_line, last_line = first.split(".")[0], last.split(".")[0]
        if not (name and first_line.isdigit() and last_line.isdigit() and count.isdigit()):
            continue
        hit, miss = cov.setdefault(name, (set(), set()))
        (hit if int(count) > 0 else miss).update(range(int(first_line), int(last_line) + 1))
    for hit, miss in cov.values():
        miss -= hit
    return cov


def _load_lcov(text: str) -> Coverage:
    cov: Coverage = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("SF:"):
            current = line[3:].strip()
            cov.setdefault(current, (set(), set()))
        elif line.startswith("DA:") and current:
            num, _, rest = line[3:].partition(",")
            hits = rest.split(",")[0]
            if num.strip().isdigit() and hits.strip().lstrip("-").isdigit():
                (cov[current][0] if int(hits) > 0 else cov[current][1]).add(int(num))
    return cov


def _load_json_coverage(text: str) -> Coverage:
    data = json.loads(text)
    cov: Coverage = {}
    if "files" in data:  # coverage.py
        for name, entry in data["files"].items():
            cov[name] = (set(entry.get("executed_lines", [])), set(entry.get("missing_lines", [])))
        return cov
    for name, entry in data.items():  # Istanbul/nyc (coverage-final.json)
        if not isinstance(entry, dict) or "statementMap" not in entry:
            continue
        hit, miss = set(), set()
        for stmt, location in entry["statementMap"].items():
            lines = range(location["start"]["line"], location["end"]["line"] + 1)
            (hit if entry["s"].get(stmt, 0) > 0 else miss).update(lines)
        cov[entry.get("path", name)] = (hit, miss - hit)
    return cov


def _add_line(cov: Coverage, name: str, number: str | None, hit: bool) -> None:
    if number is not None and number.isdigit():
        cov.setdefault(name, (set(), set()))[0 if hit else 1].add(int(number))


def _load_xml_coverage(text: str) -> Coverage:
    """JaCoCo (`<package>/<sourcefile>/<line nr mi ci>`) ou Cobertura (`<class filename>/<line number hits>`)."""
    root = ET.fromstring(text)
    cov: Coverage = {}
    for package in root.iter("package"):
        prefix = package.get("name", "")
        for source in package.findall("sourcefile"):  # JaCoCo
            name = f"{prefix}/{source.get('name', '')}" if prefix else source.get("name", "")
            cov.setdefault(name, (set(), set()))
            for line in source.findall("line"):
                _add_line(cov, name, line.get("nr"), int(line.get("ci", "0")) > 0)
    for cls in root.iter("class"):  # Cobertura
        name = cls.get("filename")
        if name:
            cov.setdefault(name, (set(), set()))
            for line in cls.iter("line"):
                _add_line(cov, name, line.get("number"), int(line.get("hits", "0")) > 0)
    for hit, miss in cov.values():
        miss -= hit  # a mesma linha pode aparecer em várias classes
    return cov


def load_coverage(path: Path) -> Coverage:
    """Lê coverage.py JSON, Istanbul JSON, JaCoCo/Cobertura XML, lcov ou perfil do Go (`-coverprofile`)."""
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith("<"):
        return _load_xml_coverage(text)
    if text.lstrip().startswith("{"):
        return _load_json_coverage(text)
    if text.startswith("mode:"):
        return _load_go_profile(text)
    return _load_lcov(text)


def _parts(name: str) -> tuple[str, ...]:
    return tuple(p for p in PurePosixPath(name.replace("\\", "/")).parts if p not in (".", "/") and not p.endswith(":"))


def coverage_for(cov: Coverage, path: Path) -> tuple[set[int], set[int]] | None:
    """Casa por sufixo de componentes de caminho; vence o casamento mais longo (evita `a/util.py` ~ `b/util.py`)."""
    resolved = _parts(path.resolve().as_posix())
    given = _parts(path.as_posix())
    best: tuple[int, tuple[set[int], set[int]]] | None = None
    for name, value in cov.items():
        parts = _parts(name)
        if not parts:
            continue
        if resolved[-len(parts):] == parts:
            score = len(parts)
        elif given and parts[-len(given):] == given:
            score = len(given)
        else:
            continue
        if best is None or score > best[0]:
            best = (score, value)
    return best[1] if best else None


def function_coverage(func: Func, file_cov: tuple[set[int], set[int]]) -> float:
    hit = {n for n in file_cov[0] if func.start <= n <= func.end}
    miss = {n for n in file_cov[1] if func.start <= n <= func.end}
    total = len(hit) + len(miss)
    return 1.0 if total == 0 else len(hit) / total


def verdict_line(gate: str, status: str, detail: str) -> str:
    return f"GATE {gate}: {status} — {detail}"
