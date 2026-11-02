"""Code optimization: safe mechanical rewrites + advisory suggestions, optional AI.

The original code is never modified; an optimized *copy* is returned for comparison.
Python rewrites are verified by re-parsing; a rewrite that breaks parsing is discarded.
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from typing import Any

from app.analyzers import tools
from app.analyzers.base import LANGUAGE_LABEL, mask_source
from app.analyzers.registry import run_static_analysis
from app.schemas import OptimizeIn
from app.services import ai


def _sugg(kind: str, title: str, desc: str, line: int | None = None, before: str | None = None, after: str | None = None, impact: str = "medium") -> dict[str, Any]:
    return {"kind": kind, "title": title, "description": desc, "line": line, "before": before, "after": after, "impact": impact}


def _parses(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _indent(s: str) -> int:
    return len(s) - len(s.lstrip())


def _block_end(lines: list[str], i: int) -> int:
    """Index (exclusive) of the end of the indented block whose header is lines[i]."""
    base = _indent(lines[i])
    j = i + 1
    while j < len(lines) and (not lines[j].strip() or _indent(lines[j]) > base):
        j += 1
    while j - 1 > i and not lines[j - 1].strip():
        j -= 1
    return j


def _singular(name: str) -> str:
    if name.endswith("ies") and len(name) > 4:
        return name[:-3] + "y"
    if name.endswith("s") and not name.endswith("ss") and len(name) > 2:
        return name[:-1]
    return "item"


# --------------------------------------------------------------------------- Python
def _py_append_to_comprehension(lines: list[str], out: list[dict]) -> list[str]:
    i = 0
    while i < len(lines) - 2:
        m0 = re.match(r"^(\s*)(\w+)\s*=\s*\[\]\s*$", lines[i])
        m1 = re.match(r"^(\s*)for\s+(.+?)\s+in\s+(.+):\s*$", lines[i + 1]) if m0 else None
        if m0 and m1 and m1.group(1) == m0.group(1):
            ind, var = m0.group(1), m0.group(2)
            end = _block_end(lines, i + 1)
            body = [ln for ln in lines[i + 2:end] if ln.strip()]
            new = None
            if len(body) == 1:
                m2 = re.match(rf"^\s*{re.escape(var)}\.append\((.+)\)\s*$", body[0])
                if m2:
                    new = f"{ind}{var} = [{m2.group(1)} for {m1.group(2)} in {m1.group(3)}]"
            elif len(body) == 2:
                mi = re.match(r"^\s*if\s+(.+):\s*$", body[0])
                m2 = re.match(rf"^\s*{re.escape(var)}\.append\((.+)\)\s*$", body[1])
                if mi and m2 and _indent(body[1]) > _indent(body[0]):
                    new = f"{ind}{var} = [{m2.group(1)} for {m1.group(2)} in {m1.group(3)} if {mi.group(1)}]"
            if new:
                before = "\n".join(lines[i:end])
                candidate = lines[:i] + [new] + lines[end:]
                if _parses("\n".join(candidate)):
                    out.append(_sugg("pattern", "Replace append loop with a list comprehension",
                                     "List comprehensions are more concise and run faster than repeated .append() calls.", i + 1, before, new, "medium"))
                    lines = candidate
        i += 1
    return lines


def _py_string_concat(lines: list[str], out: list[dict]) -> list[str]:
    i = 0
    while i < len(lines):
        m0 = re.match(r"^(\s*)(\w+)\s*=\s*(\"\"|'')\s*$", lines[i])
        if not m0:
            i += 1
            continue
        ind, var = m0.group(1), m0.group(2)
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or not re.match(rf"^{ind}(for|while)\b.*:\s*$", lines[j]):
            i += 1
            continue
        end = _block_end(lines, j)
        body = lines[j + 1:end]
        word = re.compile(rf"(?<![\w.]){re.escape(var)}(?!\w)")
        concat = [k for k, ln in enumerate(body) if re.match(rf"^\s*{re.escape(var)}\s*\+=\s*.+$", ln)]
        other = [k for k, ln in enumerate(body) if word.search(ln) and k not in concat]
        if len(concat) >= 1 and not other:
            parts = f"{var}_parts"
            new_body = [re.sub(rf"^(\s*){re.escape(var)}\s*\+=\s*(.+)$", rf"\1{parts}.append(\2)", ln) if k in concat else ln for k, ln in enumerate(body)]
            new = lines[:i] + [f"{ind}{parts} = []"] + lines[i + 1:j + 1] + new_body + [f'{ind}{var} = "".join({parts})'] + lines[end:]
            if _parses("\n".join(new)):
                out.append(_sugg("performance", "Build strings with a list and ''.join()",
                                 f"`{var} += ...` inside a loop copies the whole string on each iteration (O(n²) for long strings). Collecting parts and joining once is linear.",
                                 i + 1, "\n".join(lines[i:end]), "\n".join(new[i:end + 2]), "high"))
                lines = new
        i += 1
    return lines


def _py_range_len(lines: list[str], out: list[dict]) -> list[str]:
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*)for\s+(\w+)\s+in\s+range\(\s*len\(\s*([\w.]+)\s*\)\s*\)\s*:\s*$", ln)
        if not m:
            continue
        ind, idx, seq = m.groups()
        end = _block_end(lines, i)
        body = lines[i + 1:end]
        access = re.compile(rf"{re.escape(seq)}\[\s*{re.escape(idx)}\s*\]")
        if any(re.search(rf"{re.escape(seq)}\[\s*{re.escape(idx)}\s*\]\s*(=[^=]|\+=|-=|\*=|/=)", b) for b in body):
            continue  # mutation through the index: keep index loop
        if not any(access.search(b) for b in body):
            continue
        item = _singular(seq.split(".")[-1])
        if re.search(rf"(?<![\w.]){re.escape(item)}(?!\w)", "\n".join(body)):
            item = f"{item}_value"
        new_body = [access.sub(item, b) for b in body]
        still_uses_idx = any(re.search(rf"(?<![\w.]){re.escape(idx)}(?!\w)", b) for b in new_body)
        header = f"{ind}for {idx}, {item} in enumerate({seq}):" if still_uses_idx else f"{ind}for {item} in {seq}:"
        candidate = lines[:i] + [header] + new_body + lines[end:]
        if _parses("\n".join(candidate)):
            out.append(_sugg("readability", "Iterate over items instead of indices",
                             "`for i in range(len(seq))` with `seq[i]` is harder to read and slightly slower than iterating directly (or using enumerate when the index is needed).",
                             i + 1, "\n".join(lines[i:end]), "\n".join([header] + new_body), "low"))
            return _py_range_len(candidate, out)  # restart: line numbers shifted
    return lines


def _py_ast_rewrites(code: str, out: list[dict]) -> str:
    """Rewrites based on AST node positions; applied from the end so offsets stay valid."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    lines = code.splitlines(keepends=True)
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln))

    def pos(lineno: int, col: int) -> int:
        # col_offset is in UTF-8 bytes; convert to characters for this line
        line = lines[lineno - 1]
        return offsets[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8", errors="ignore"))

    edits: list[tuple[int, int, str, dict]] = []
    for node in ast.walk(tree):
        # sum/any/all/min/max([...comprehension...]) -> generator
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("sum", "any", "all", "min", "max") \
                and len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.ListComp):
            lc = node.args[0]
            s, e = pos(lc.lineno, lc.col_offset), pos(lc.end_lineno, lc.end_col_offset)  # type: ignore[arg-type]
            inner = code[s + 1:e - 1]
            edits.append((s, e, inner, _sugg("performance", f"Pass a generator to {node.func.id}()",
                                               f"Building a temporary list for `{node.func.id}()` wastes memory" + (" and prevents short-circuiting." if node.func.id in ("any", "all") else "."),
                                               node.lineno, code[s:e], inner, "low")))
        # list(map(lambda x: expr, xs)) -> [expr for x in xs]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "list" and len(node.args) == 1:
            inner = node.args[0]
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id == "map" and len(inner.args) == 2 \
                    and isinstance(inner.args[0], ast.Lambda) and len(inner.args[0].args.args) == 1:
                lam = inner.args[0]
                arg = lam.args.args[0].arg
                rep = f"[{ast.unparse(lam.body)} for {arg} in {ast.unparse(inner.args[1])}]"
                s, e = pos(node.lineno, node.col_offset), pos(node.end_lineno, node.end_col_offset)  # type: ignore[arg-type]
                edits.append((s, e, rep, _sugg("readability", "Use a list comprehension instead of list(map(lambda ...))",
                                               "A comprehension is clearer and avoids a function call per element.", node.lineno, code[s:e], rep, "low")))
        # x in [1, 2, 3] -> x in {1, 2, 3}
        if isinstance(node, ast.Compare):
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, ast.List) and len(comp.elts) >= 3 \
                        and all(isinstance(el, ast.Constant) and isinstance(el.value, (int, str)) for el in comp.elts):
                    s, e = pos(comp.lineno, comp.col_offset), pos(comp.end_lineno, comp.end_col_offset)  # type: ignore[arg-type]
                    rep = "{" + code[s + 1:e - 1] + "}"
                    edits.append((s, e, rep, _sugg("performance", "Use a set literal for membership tests",
                                                   "Membership in a set is O(1) on average; in a list it is O(n).", node.lineno, code[s:e], rep, "low")))
        # for k in d.keys(): -> for k in d:
        if isinstance(node, (ast.For, ast.comprehension)):
            it = node.iter
            if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) and it.func.attr == "keys" and not it.args:
                s, e = pos(it.lineno, it.col_offset), pos(it.end_lineno, it.end_col_offset)  # type: ignore[arg-type]
                rep = ast.unparse(it.func.value)
                edits.append((s, e, rep, _sugg("readability", "Iterate a dict directly instead of .keys()",
                                               "Iterating a dict yields its keys already; `.keys()` is redundant.", it.lineno, code[s:e], rep, "low")))
        # bare except -> except Exception
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            line = lines[node.lineno - 1]
            m = re.match(r"^(\s*)except\s*:", line)
            if m:
                s = offsets[node.lineno - 1] + len(m.group(1))
                e = offsets[node.lineno - 1] + m.end()
                edits.append((s, e, "except Exception:", _sugg("pattern", "Catch Exception instead of using a bare except",
                                                                "A bare `except:` also catches KeyboardInterrupt and SystemExit, which makes programs hard to stop. Prefer the specific exceptions you expect.",
                                                                node.lineno, line.strip(), "except Exception:", "medium")))
    # drop overlapping edits (keep outermost first-found)
    edits.sort(key=lambda t: (t[0], -t[1]))
    chosen: list[tuple[int, int, str, dict]] = []
    last_end = -1
    for ed in edits:
        if ed[0] >= last_end:
            chosen.append(ed)
            last_end = ed[1]
    new = code
    for s, e, rep, _ in sorted(chosen, key=lambda t: t[0], reverse=True):
        new = new[:s] + rep + new[e:]
    if _parses(new):
        out.extend(sorted((c[3] for c in chosen), key=lambda d: d["line"] or 0))
        return new
    return code


def _py_textual(code: str, out: list[dict]) -> str:
    masked = mask_source(code, "python")
    edits = []
    for m in re.finditer(r"([!=])=\s*None\b", masked):
        rep = "is not None" if m.group(1) == "!" else "is None"
        line = masked.count("\n", 0, m.start()) + 1
        edits.append((m.start(), m.end(), rep, line))
    new = code
    for s, e, rep, _ in sorted(edits, reverse=True):
        new = new[:s] + rep + new[e:]
    if edits and _parses(new):
        out.append(_sugg("pattern", "Compare to None with `is`", "`== None` can be overridden by `__eq__`; identity comparison is correct and idiomatic.",
                         edits[0][3], "x == None", "x is None", "low"))
        return new
    return code


def _py_advice(code: str, out: list[dict]) -> None:
    for n, ln in enumerate(code.splitlines(), start=1):
        s = ln.strip()
        if re.search(r"\blen\(\s*[\w.]+\s*\)\s*(==\s*0|>\s*0|!=\s*0)", s):
            out.append(_sugg("readability", "Use truthiness instead of len() comparisons", "`if not items:` / `if items:` is the idiomatic way to test for empty containers.", n, s, None, "low"))
        if re.search(r"\btype\(\s*\w+\s*\)\s*==", s):
            out.append(_sugg("pattern", "Use isinstance() instead of type() ==", "isinstance also accepts subclasses and reads better.", n, s, None, "low"))
        if re.search(r"==\s*True\b|==\s*False\b", s):
            out.append(_sugg("readability", "Avoid comparing with True/False", "Write `if flag:` or `if not flag:`.", n, s, None, "low"))
        if re.search(r"(?<![\w.])open\(", s) and not s.startswith("with"):
            out.append(_sugg("pattern", "Open files with a context manager", "`with open(...) as fh:` closes the file even when an error occurs.", n, s, None, "medium"))


def optimize_python(code: str, out: list[dict]) -> str:
    try:
        ast.parse(code)
    except SyntaxError as e:
        out.append(_sugg("pattern", "Fix syntax errors first", f"The code does not parse (line {e.lineno}: {e.msg}); automatic rewrites were skipped.", e.lineno, None, None, "high"))
        return code
    trailing_nl = code.endswith("\n")
    lines = code.splitlines()
    lines = _py_append_to_comprehension(lines, out)
    lines = _py_string_concat(lines, out)
    lines = _py_range_len(lines, out)
    new = "\n".join(lines) + ("\n" if trailing_nl else "")
    new = _py_ast_rewrites(new, out)
    new = _py_textual(new, out)
    fixed = tools.ruff_fix(new, fmt=False)
    if fixed and fixed != new and _parses(fixed):
        out.append(_sugg("readability", "Applied Ruff safe autofixes", "Removed unused imports and modernised syntax using Ruff's safe fixes.", None, None, None, "low"))
        new = fixed
    _py_advice(new, out)
    return new


# --------------------------------------------------------------------------- brace languages
def _apply(code: str, masked: str, pattern: str, repl, flags: int = 0) -> tuple[str, list[int]]:
    edits = []
    for m in re.finditer(pattern, masked, flags):
        r = repl(m, code) if callable(repl) else m.expand(repl)
        if r is None:
            continue
        edits.append((m.start(), m.end(), r))
    lines_hit = [masked.count("\n", 0, s) + 1 for s, _, _ in edits]
    for s, e, r in sorted(edits, reverse=True):
        code = code[:s] + r + code[e:]
    return code, lines_hit


def optimize_clike(code: str, lang: str, out: list[dict]) -> str:
    new = code

    def step(pattern: str, repl, kind: str, title: str, desc: str, before: str, after: str, impact: str = "low", flags: int = 0) -> None:
        nonlocal new
        masked = mask_source(new, lang)
        new2, hit = _apply(new, masked, pattern, repl, flags)
        if hit and new2 != new:
            out.append(_sugg(kind, title, desc + (f" ({len(hit)} occurrence{'s' if len(hit) > 1 else ''})" if len(hit) > 1 else ""), hit[0], before, after, impact))
            new = new2

    if lang in ("javascript", "typescript"):
        step(r"(?<![=!<>])([!=])=(?!=)(?!\s*(?:null|undefined)\b)", lambda m, c: m.group(1) + "==", "pattern", "Use strict equality",
             "`===` avoids implicit type coercion bugs such as `'0' == 0`.", "a == b", "a === b")
        step(r"(?<![\w.$])var(?=\s+[A-Za-z_$])", "let", "readability", "Replace var with let",
             "`let` is block-scoped and not hoisted, avoiding a class of scoping bugs. Use `const` where the variable is never reassigned.", "var x = 1", "let x = 1")
        step(r"\.indexOf\(([^()]+)\)\s*(?:!==?\s*-1|>=\s*0|>\s*-1)", lambda m, c: f".includes({c[m.start(1):m.end(1)]})", "readability", "Use includes() for membership",
             "`includes` states intent directly.", "arr.indexOf(x) !== -1", "arr.includes(x)")
        step(r"JSON\.parse\(\s*JSON\.stringify\(([^()]+)\)\s*\)", lambda m, c: f"structuredClone({c[m.start(1):m.end(1)]})", "performance", "Use structuredClone for deep copies",
             "structuredClone is faster and preserves Dates, Maps, Sets and cyclic references.", "JSON.parse(JSON.stringify(obj))", "structuredClone(obj)")
        step(r"\bnew Array\(\s*\)", "[]", "readability", "Use array literals", "`[]` is shorter and avoids the Array constructor's argument quirks.", "new Array()", "[]")
        step(r"\bnew Object\(\s*\)", "{}", "readability", "Use object literals", "`{}` is the idiomatic form.", "new Object()", "{}")
    elif lang == "java":
        step(r"\.size\(\)\s*==\s*0", ".isEmpty()", "readability", "Use isEmpty()", "Expresses intent and can be O(1) for all collections.", "list.size() == 0", "list.isEmpty()")
        step(r"\bnew\s+(Integer|Long|Double|Float|Short|Byte|Boolean)\s*\(", lambda m, c: f"{m.group(1)}.valueOf(", "performance", "Use valueOf() instead of boxing constructors",
             "valueOf may return cached instances; the constructors are deprecated.", "new Integer(5)", "Integer.valueOf(5)")
    elif lang in ("c", "cpp"):
        # hoist strlen out of loop conditions
        masked = mask_source(new, lang)
        lines = new.splitlines()
        mlines = masked.splitlines()
        for i, ml in enumerate(mlines):
            m = re.search(r"for\s*\(([^;]*);([^;]*)\bstrlen\s*\(\s*([A-Za-z_]\w*)\s*\)([^;]*);", ml)
            if m:
                var = m.group(3)
                ind = re.match(r"\s*", lines[i]).group(0)
                before = lines[i]
                lines[i] = lines[i].replace(f"strlen({var})", f"{var}_len", 1)
                if lines[i] != before:
                    lines.insert(i, f"{ind}size_t {var}_len = strlen({var});")
                    out.append(_sugg("performance", "Hoist strlen() out of the loop condition",
                                     "strlen scans the whole string; calling it in the condition makes the loop O(n²).", i + 1, before.strip(),
                                     f"size_t {var}_len = strlen({var});\n{lines[i + 1].strip()}", "high"))
                    break
        new = "\n".join(lines) + ("\n" if code.endswith("\n") else "")
        step(r"(?<![\w.])gets\s*\(\s*([A-Za-z_]\w*)\s*\)", lambda m, c: f"fgets({m.group(1)}, sizeof({m.group(1)}), stdin)", "pattern", "Replace gets() with fgets()",
             "gets() cannot bound input and is removed from modern C. Note fgets keeps the trailing newline.", "gets(buf)", "fgets(buf, sizeof(buf), stdin)", "high")
        if lang == "cpp":
            step(r"<<\s*(?:std::)?endl\b", "<< '\\n'", "performance", "Use '\\n' instead of std::endl",
                 "std::endl forces a flush every time; '\\n' lets the stream buffer output.", "std::cout << x << std::endl;", "std::cout << x << '\\n';")
    return new


def _clike_advice(code: str, lang: str, out: list[dict]) -> None:
    masked = mask_source(code, lang).splitlines()
    for n, ml in enumerate(masked, start=1):
        s = code.splitlines()[n - 1].strip() if n - 1 < len(code.splitlines()) else ml
        if lang in ("javascript", "typescript"):
            if re.search(r"for\s*\(\s*(?:let|var)\s+(\w+)\s*=\s*0\s*;\s*\1\s*<\s*([\w.]+)\.length", ml):
                out.append(_sugg("readability", "Prefer for...of for simple array iteration",
                                 "`for (const item of arr)` removes index bookkeeping when you only need elements.", n, s, "for (const item of arr) { ... }", "low"))
            if re.search(r"\"[^\"]*\"\s*\+\s*\w+\s*\+\s*\"", s):
                out.append(_sugg("readability", "Use template literals", "Template literals (`Hello ${name}`) are easier to read than concatenation.", n, s, None, "low"))
        if lang == "java" and re.search(r"for\s*\(\s*int\s+(\w+)\s*=\s*0\s*;\s*\1\s*<\s*(\w+)\.size\(\)", ml):
            out.append(_sugg("readability", "Use an enhanced for loop", "`for (T item : list)` is clearer and avoids O(n) get(i) on LinkedList.", n, s, "for (T item : list) { ... }", "medium"))
        if lang == "cpp" and re.search(r"[(,]\s*(?:std::)?(?:vector|string|map|unordered_map|set)\b(?:<[^&*()]*>)?\s+\w+\s*[,)]", ml):
            out.append(_sugg("performance", "Pass containers by const reference", "Passing by value copies the entire container on each call.", n, s, "const std::vector<int>& v", "medium"))
        if lang == "go" and re.search(r"(\w+)\s*:?=\s*make\(\[\][\w.]+\s*,\s*0\s*\)", ml):
            out.append(_sugg("performance", "Preallocate slice capacity", "If the final size is known, `make([]T, 0, n)` avoids repeated reallocation.", n, s, "make([]T, 0, n)", "low"))


def local_optimize(code: str, language: str) -> tuple[str, list[dict[str, Any]]]:
    out: list[dict[str, Any]] = []
    new = optimize_python(code, out) if language == "python" else optimize_clike(code, language, out)
    if language != "python":
        _clike_advice(new, language, out)
    # surface static performance findings that were not rewritten automatically
    try:
        res, _, _ = run_static_analysis(code, language, None, ["performance"])
        seen = {(s["line"], s["title"]) for s in out}
        rewritten = {s["title"].lower() for s in out}
        for f in res.findings:
            if (f.line, f.title) in seen:
                continue
            if "string" in f.title.lower() and any("string" in r for r in rewritten):
                continue
            if f.rule in ("PERF401", "PERF402") and any("comprehension" in r for r in rewritten):
                continue
            out.append(_sugg("performance", f.title, f"{f.description} {f.recommendation}", f.line, (f.snippet or "").strip() or None, None,
                             "high" if f.severity in ("critical", "high") else "medium" if f.severity == "medium" else "low"))
    except Exception:
        pass
    return new, out


AI_OPT_SYSTEM = """You are a performance and clean-code expert. Optimize the given code without changing its observable behaviour.
Return JSON:
{"summary": "short overview of the improvements",
 "suggestions": [{"kind": "performance|readability|pattern", "title": "...", "description": "why it helps", "line": <int or null>,
                  "before": "original snippet", "after": "improved snippet", "impact": "high|medium|low"}],
 "optimized_code": "the full optimized code"}"""


def run_optimize(inp: OptimizeIn, allow_ai: bool) -> dict[str, Any]:
    optimized, suggestions = local_optimize(inp.code, inp.language)
    ai_used, ai_error = False, None
    summary = ""
    if allow_ai:
        try:
            d = ai.chat_json(AI_OPT_SYSTEM, f"Language: {LANGUAGE_LABEL[inp.language]}\n```{inp.language}\n{ai.clip_code(inp.code)}\n```", max_tokens=6000)
            code_ai = ai.as_str(d.get("optimized_code"), "", 100_000).strip()
            ai_s = []
            for x in d.get("suggestions") or []:
                if not isinstance(x, dict):
                    continue
                kind = x.get("kind") if x.get("kind") in ("performance", "readability", "pattern") else "pattern"
                impact = x.get("impact") if x.get("impact") in ("high", "medium", "low") else "medium"
                ai_s.append(_sugg(kind, ai.as_str(x.get("title"), "Suggestion", 200), ai.as_str(x.get("description"), "", 2000),
                                  ai.as_int(x.get("line")), ai.as_str(x.get("before"), "", 5000) or None, ai.as_str(x.get("after"), "", 5000) or None, impact))
            if code_ai:
                optimized = code_ai + ("\n" if inp.code.endswith("\n") and not code_ai.endswith("\n") else "")
                suggestions = ai_s or suggestions
            summary = ai.as_str(d.get("summary"), "", 3000)
            ai_used = True
        except ai.AIError as exc:
            ai_error = str(exc)
    changed = optimized.strip() != inp.code.strip()
    if not summary:
        auto = sum(1 for s in suggestions if s.get("after") and s.get("before"))
        summary = (f"Found {len(suggestions)} suggestion(s)." + (f" {auto} were applied automatically to the optimized copy; review the diff before adopting it." if changed else
                   " No automatic rewrite was safe to apply, so the optimized copy matches the original.")) if suggestions else \
            "No optimization opportunities were detected by the local rules. The code already follows the patterns checked."
    return {"language": inp.language, "original_code": inp.code, "optimized_code": optimized, "changed": changed, "suggestions": suggestions[:60],
            "summary": summary, "ai_used": ai_used, "ai_error": ai_error, "created_at": datetime.now(timezone.utc)}
