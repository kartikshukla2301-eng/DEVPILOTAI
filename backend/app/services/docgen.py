"""Markdown documentation generator: AST for Python, doc-comment + signature parsing for others."""
from __future__ import annotations

import ast
import re
import sys
from datetime import datetime, timezone
from typing import Any

from app.analyzers.base import LANGUAGE_LABEL, mask_source
from app.analyzers.clike import CLASS_PATTERNS, CONTROL, FUNC_PATTERNS, _family
from app.schemas import DocsIn
from app.services import ai

STDLIB = set(getattr(sys, "stdlib_module_names", ()))

NAME_HINTS = [
    (r"(^|_)(path|file|filename|filepath)$", "Path to the file."),
    (r"(^|_)(dir|directory|folder)$", "Path to the directory."),
    (r"(^|_)(url|uri|endpoint)$", "URL of the resource."),
    (r"_id$|^id$", "Unique identifier."),
    (r"^(n|num|count|size|length|limit|k)$", "Number of items."),
    (r"^(i|j|idx|index)$", "Index position."),
    (r"^(items|values|data|nums|numbers|arr|array|lst|elements)$", "Collection of input values."),
    (r"^(name|title|label)$", "Human-readable name."),
    (r"^(text|msg|message|s|string)$", "Input text."),
    (r"^(timeout|delay)$", "Time limit, in seconds unless documented otherwise."),
    (r"^(callback|cb|fn|func|handler)$", "Function to call."),
    (r"^(config|cfg|options|opts|settings)$", "Configuration options."),
    (r"^(user|username)$", "The user."),
    (r"^(key)$", "Lookup key."),
    (r"^(target)$", "Value to search for."),
    (r"^(verbose|debug)$", "Enable additional output."),
]


def _hint(name: str) -> str:
    for pat, desc in NAME_HINTS:
        if re.search(pat, name, re.I):
            return desc
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", name).replace("_", " ").strip().lower()
    return f"The {words}." if words else ""


def _parse_docstring(doc: str | None) -> dict[str, Any]:
    """Supports Google, NumPy and reST (:param x:) styles."""
    res: dict[str, Any] = {"summary": "", "params": {}, "returns": "", "raises": [], "examples": ""}
    if not doc:
        return res
    lines = doc.strip().splitlines()
    summary = []
    for ln in lines:
        if not ln.strip():
            break
        summary.append(ln.strip())
    res["summary"] = " ".join(summary)
    for m in re.finditer(r":param\s+(?:\w+\s+)?(\w+):\s*(.+)", doc):
        res["params"][m.group(1)] = m.group(2).strip()
    m = re.search(r":returns?:\s*(.+)", doc)
    if m:
        res["returns"] = m.group(1).strip()
    for m in re.finditer(r":raises\s+(\w+):\s*(.*)", doc):
        res["raises"].append(f"`{m.group(1)}` — {m.group(2).strip()}")
    section = None
    for ln in lines:
        s = ln.strip()
        head = re.match(r"^(Args|Arguments|Parameters|Returns|Return|Yields|Raises|Examples?)\s*:?\s*$", s)
        if head:
            section = head.group(1).lower()
            continue
        if s.startswith("---"):
            continue
        if not s:
            if section in ("examples", "example"):
                res["examples"] += "\n"
            continue
        if section in ("args", "arguments", "parameters"):
            pm = re.match(r"^(\*{0,2}\w+)\s*(?:\(([^)]*)\))?\s*:\s*(.*)$", s) or re.match(r"^(\w+)\s*:\s*([\w\[\], .|]+)$", s)
            if pm:
                res["params"][pm.group(1).lstrip("*")] = (pm.group(3) if pm.lastindex and pm.lastindex >= 3 else "").strip() or res["params"].get(pm.group(1), "")
            elif res["params"]:
                last = list(res["params"])[-1]
                res["params"][last] = (res["params"][last] + " " + s).strip()
        elif section in ("returns", "return", "yields"):
            res["returns"] = (res["returns"] + " " + re.sub(r"^[\w\[\], .|]+:\s*", "", s)).strip()
        elif section == "raises":
            rm = re.match(r"^(\w+)\s*:\s*(.*)$", s)
            res["raises"].append(f"`{rm.group(1)}` — {rm.group(2)}" if rm else s)
        elif section in ("examples", "example"):
            res["examples"] += ln + "\n"
    return res


def _sig(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        args = ast.unparse(fn.args)
    except Exception:
        args = "..."
    ret = f" -> {ast.unparse(fn.returns)}" if fn.returns is not None else ""
    return f"{'async ' if isinstance(fn, ast.AsyncFunctionDef) else ''}def {fn.name}({args}){ret}"


def _infer_return(fn: ast.AST) -> str:
    rets = [r.value for r in ast.walk(fn) if isinstance(r, ast.Return) and r.value is not None]
    if any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(fn)):
        return "A generator."
    if not rets:
        return ""
    v = rets[0]
    kinds = {ast.List: "A list", ast.ListComp: "A list", ast.Dict: "A dictionary", ast.DictComp: "A dictionary", ast.Tuple: "A tuple",
             ast.Set: "A set", ast.Compare: "A boolean", ast.BoolOp: "A boolean", ast.JoinedStr: "A string"}
    if type(v) in kinds:
        return kinds[type(v)] + "."
    if isinstance(v, ast.Constant):
        return f"A {type(v.value).__name__} value."
    return f"The value of `{ast.unparse(v)[:60]}`."


def _example_call(fn: ast.FunctionDef | ast.AsyncFunctionDef, owner: str | None) -> str:
    args = []
    params = fn.args.posonlyargs + fn.args.args
    defaults_from = len(params) - len(fn.args.defaults)
    for i, a in enumerate(params):
        if a.arg in ("self", "cls") or i >= defaults_from:
            continue
        ann = ast.unparse(a.annotation) if a.annotation is not None else ""
        sample = {"int": "10", "float": "1.5", "str": '"example"', "bool": "True", "list": "[1, 2, 3]", "dict": '{"key": "value"}'}.get(
            ann.split("[")[0].lower(), None)
        if sample is None:
            sample = {"n": "10", "k": "3", "path": '"data.txt"', "name": '"Alice"', "items": "[1, 2, 3]", "nums": "[1, 2, 3]",
                      "text": '"hello"', "s": '"hello"', "x": "1", "y": "2", "a": "1", "b": "2"}.get(a.arg, a.arg)
        args.append(sample)
    call = f"{fn.name}({', '.join(args)})"
    prefix = "await " if isinstance(fn, ast.AsyncFunctionDef) else ""
    if owner:
        return f"obj = {owner}(...)\nresult = {prefix}obj.{call}"
    return f"result = {prefix}{call}"


def _py_function_md(fn: ast.FunctionDef | ast.AsyncFunctionDef, level: int, owner: str | None = None) -> str:
    doc = _parse_docstring(ast.get_docstring(fn))
    h = "#" * level
    md = [f"{h} `{fn.name}`", "", f"```python\n{_sig(fn)}\n```", ""]
    md.append(doc["summary"] or f"{'Method' if owner else 'Function'} `{fn.name}`." + (" Asynchronous." if isinstance(fn, ast.AsyncFunctionDef) else ""))
    md.append("")
    params = [a for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs if a.arg not in ("self", "cls")]
    if fn.args.vararg:
        params.append(fn.args.vararg)
    if fn.args.kwarg:
        params.append(fn.args.kwarg)
    all_pos = fn.args.posonlyargs + fn.args.args
    defaults = {a.arg: d for a, d in zip(all_pos[len(all_pos) - len(fn.args.defaults):], fn.args.defaults)}
    defaults.update({a.arg: d for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults) if d is not None})
    if params:
        md += ["**Parameters**", "", "| Name | Type | Default | Description |", "|---|---|---|---|"]
        for a in params:
            typ = f"`{ast.unparse(a.annotation)}`" if a.annotation is not None else "—"
            dflt = f"`{ast.unparse(defaults[a.arg])}`" if a.arg in defaults else ("—" if a not in (fn.args.vararg, fn.args.kwarg) else "variadic")
            desc = (doc["params"].get(a.arg) or _hint(a.arg)).replace("|", "\\|")
            md.append(f"| `{a.arg}` | {typ} | {dflt} | {desc} |")
        md.append("")
    ret_desc = doc["returns"] or _infer_return(fn)
    if fn.returns is not None or ret_desc:
        md += ["**Returns**", "", (f"`{ast.unparse(fn.returns)}` — " if fn.returns is not None else "") + (ret_desc or "See signature."), ""]
    raises = doc["raises"] or sorted({f"`{ast.unparse(r.exc.func if isinstance(r.exc, ast.Call) else r.exc)}`"
                                      for r in ast.walk(fn) if isinstance(r, ast.Raise) and r.exc is not None})
    if raises:
        md += ["**Raises**", ""] + [f"- {r}" for r in raises] + [""]
    md += ["**Example**", "", "```python", doc["examples"].strip() or _example_call(fn, owner), "```", ""]
    return "\n".join(md)


def _py_docs(code: str, title: str) -> tuple[str, dict[str, int]]:
    tree = ast.parse(code)
    mod_doc = _parse_docstring(ast.get_docstring(tree))
    imports: dict[str, str] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                imports[a.name.split(".")[0]] = a.name
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            imports[n.module.split(".")[0]] = n.module
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    funcs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    consts = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
    n_methods = 0

    md = [f"# {title}", "", f"> Generated by DevPilot AI on {datetime.now(timezone.utc):%Y-%m-%d}. Review and edit before publishing.", "", "## Overview", ""]
    overview = mod_doc["summary"] or (
        f"This Python module defines {len(classes)} class{'es' if len(classes) != 1 else ''} and {len(funcs)} top-level function{'s' if len(funcs) != 1 else ''}.")
    md += [overview, ""]
    if classes or funcs:
        md += ["## Contents", ""]
        md += [f"- Class [`{c.name}`](#{c.name.lower()})" for c in classes]
        md += [f"- Function [`{f.name}`](#{f.name.lower()})" for f in funcs]
        md.append("")
    md += ["## Dependencies", ""]
    if imports:
        for root, full in sorted(imports.items()):
            kind = "standard library" if root in STDLIB else "third-party — install with pip"
            md.append(f"- `{full}` ({kind})")
    else:
        md.append("No imports; only built-ins are used.")
    md.append("")
    if consts:
        rows = []
        for c in consts:
            targets = c.targets if isinstance(c, ast.Assign) else [c.target]
            for t in targets:
                if isinstance(t, ast.Name) and (t.id.isupper() or len(consts) <= 10):
                    rows.append(f"| `{t.id}` | `{ast.unparse(c.value)[:60] if c.value is not None else ''}` |".replace("\n", " "))
        if rows:
            md += ["## Module-level values", "", "| Name | Value |", "|---|---|"] + rows + [""]
    if classes:
        md += ["## Classes", ""]
        for c in classes:
            cdoc = _parse_docstring(ast.get_docstring(c))
            md += [f"### `{c.name}`", ""]
            if c.bases:
                md += [f"**Inherits from:** {', '.join(f'`{ast.unparse(b)}`' for b in c.bases)}", ""]
            md += [cdoc["summary"] or f"Class `{c.name}`.", ""]
            attrs = sorted({t.attr for n in ast.walk(c) if isinstance(n, (ast.Assign, ast.AnnAssign))
                            for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
                            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self"})
            if attrs:
                md += ["**Attributes:** " + ", ".join(f"`{a}`" for a in attrs), ""]
            methods = [m for m in c.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
            n_methods += len(methods)
            for m in methods:
                md.append(_py_function_md(m, 4, c.name))
    if funcs:
        md += ["## Functions", ""]
        for f in funcs:
            md.append(_py_function_md(f, 3))
    if 'if __name__ == "__main__"' in code or "if __name__ == '__main__'" in code:
        md += ["## Running", "", "```bash", "python " + (title if title.endswith(".py") else "script.py"), "```", ""]
    return "\n".join(md).rstrip() + "\n", {"classes": len(classes), "functions": len(funcs), "methods": n_methods, "dependencies": len(imports)}


# --------------------------------------------------------------------------- other languages
def _doc_comment_above(lines: list[str], idx: int) -> str:
    """Collect /** */ or consecutive // or /// comment lines immediately above lines[idx]."""
    j = idx - 1
    while j >= 0 and lines[j].strip().startswith("@"):  # skip annotations such as @Override
        j -= 1
    if j < 0 or not lines[j].strip():
        return ""
    s = lines[j].strip()
    if s.endswith("*/"):
        k = j
        while k >= 0 and "/*" not in lines[k]:
            k -= 1
        block = lines[max(k, 0):j + 1]
        text = "\n".join(re.sub(r"^\s*/?\*+/?\s?", "", b).rstrip("*/ ").rstrip() for b in block)
        return text.strip()
    if s.startswith("//"):
        k = j
        buf = []
        while k >= 0 and lines[k].strip().startswith("//"):
            buf.insert(0, re.sub(r"^\s*/{2,3}\s?", "", lines[k]))
            k -= 1
        return "\n".join(buf).strip()
    return ""


def _parse_tagged(doc: str) -> dict[str, Any]:
    res: dict[str, Any] = {"summary": "", "params": {}, "returns": "", "raises": []}
    summary = []
    for ln in doc.splitlines():
        if ln.strip().startswith("@"):
            break
        summary.append(ln.strip())
    res["summary"] = " ".join(x for x in summary if x)
    for m in re.finditer(r"@param\s+(?:\{[^}]*\}\s*)?\[?(\w+)\]?\s*(?:-\s*)?(.*)", doc):
        res["params"][m.group(1)] = m.group(2).strip()
    m = re.search(r"@returns?\s+(?:\{[^}]*\}\s*)?(.*)", doc)
    if m:
        res["returns"] = m.group(1).strip()
    for m in re.finditer(r"@(?:throws|exception)\s+(?:\{([^}]*)\}|(\w+))\s*(.*)", doc):
        res["raises"].append(f"`{m.group(1) or m.group(2)}` — {m.group(3).strip()}")
    return res


def _split_params(text: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "<([{":
            depth += 1
        elif ch in ">)]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _param_rows(ptxt: str, lang: str) -> list[tuple[str, str, str]]:
    rows = []
    parts = _split_params(ptxt)
    if lang == "go":
        pending: list[str] = []
        for p in parts:
            bits = p.split(None, 1)
            if len(bits) == 1:
                pending.append(bits[0])
                continue
            for nm in pending:
                rows.append((nm, bits[1], ""))
            pending = []
            rows.append((bits[0], bits[1], ""))
        for nm in pending:
            rows.append((nm, "", ""))
        return rows
    for p in parts:
        if not p or p == "void":
            continue
        dflt = ""
        if "=" in p:
            p, dflt = p.split("=", 1)
            p, dflt = p.strip(), dflt.strip()
        if lang in ("javascript", "typescript"):
            p = re.sub(r"^(public|private|protected|readonly)\s+", "", p)
            if ":" in p:
                nm, typ = p.split(":", 1)
                rows.append((nm.strip().rstrip("?"), typ.strip(), dflt))
            else:
                rows.append((p.strip(), "", dflt))
        else:
            p = re.sub(r"^(final|const)\s+", "", p)
            m = re.match(r"(.*?)([A-Za-z_]\w*)\s*(\[\s*\])?$", p)
            if m:
                rows.append((m.group(2), (m.group(1).strip() + (m.group(3) or "")).strip(), dflt))
    return rows


def _clike_docs(code: str, lang: str, title: str) -> tuple[str, dict[str, int]]:
    fam = _family(lang)
    lines = code.splitlines()
    masked = mask_source(code, lang).splitlines()
    dep_patterns = {
        "js": [r"^import\s+(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]", r"require\(\s*['\"]([^'\"]+)['\"]\s*\)"],
        "java": [r"^import\s+(?:static\s+)?([\w.*]+)\s*;"],
        "c": [r"^#\s*include\s*([<\"][^>\"]+[>\"])"],
        "go": [r"^import\s+(?:[\w.]+\s+)?\"([\w./-]+)\"", r"^(?:[\w.]+\s+)?\"([\w./-]+)\"$"],
    }[fam]
    deps: list[str] = []
    in_go_block = False
    for ln in lines:
        s = ln.strip()
        if fam == "go":
            if s.startswith("import ("):
                in_go_block = True
                continue
            if in_go_block and s == ")":
                in_go_block = False
                continue
            pats = dep_patterns if in_go_block else dep_patterns[:1]
        else:
            pats = dep_patterns
        for p in pats:
            m = re.search(p, s)
            if m and m.group(1) not in deps:
                deps.append(m.group(1))

    types, funcs = [], []
    for i, ml in enumerate(masked):
        cm = CLASS_PATTERNS[fam].search(ml)
        if cm:
            types.append((cm.group(1), i))
            continue
        for p in FUNC_PATTERNS[fam]:
            fm = p.search(ml)
            if fm and fm.group(1) not in CONTROL:
                funcs.append((fm.group(1), i))
                break

    md = [f"# {title}", "", f"> Generated by DevPilot AI on {datetime.now(timezone.utc):%Y-%m-%d}. Review and edit before publishing.", "", "## Overview", ""]
    # A leading comment block counts as the file overview unless it documents the first declaration.
    first_code = next((i for i, l in enumerate(lines) if l.strip() and not l.strip().startswith(("/", "*"))), 0)
    first_decl = min([i for _, i in types + funcs], default=-1)
    file_doc = _doc_comment_above(lines, first_code) if first_code != first_decl else ""
    overview = _parse_tagged(file_doc)["summary"] if file_doc else ""
    if not overview:
        overview = (f"This {LANGUAGE_LABEL[lang]} source defines {len(types)} type{'s' if len(types) != 1 else ''} "
                    f"and {len(funcs)} function{'s' if len(funcs) != 1 else ''}.")
    md += [overview, ""]
    if types or funcs:
        md += ["## Contents", ""] + [f"- Type `{t}`" for t, _ in types] + [f"- Function `{f}`" for f, _ in funcs] + [""]
    md += ["## Dependencies", ""] + ([f"- `{d}`" for d in deps] or ["No imports or includes."]) + [""]
    if types:
        md += ["## Types", ""]
        for name, i in types:
            doc = _parse_tagged(_doc_comment_above(lines, i))
            md += [f"### `{name}`", "", f"```{lang}\n{lines[i].strip().rstrip('{').strip()}\n```", "", doc["summary"] or f"Type `{name}`.", ""]
    if funcs:
        md += ["## Functions", ""]
        for name, i in funcs:
            header = lines[i].strip()
            k = i
            while "{" not in header and ")" not in header and k + 1 < len(lines) and k - i < 5:
                k += 1
                header += " " + lines[k].strip()
            sig = header.split("{")[0].strip().rstrip("{").strip()
            doc = _parse_tagged(_doc_comment_above(lines, i))
            md += [f"### `{name}`", "", f"```{lang}\n{sig}\n```", "", doc["summary"] or f"Function `{name}`.", ""]
            pm = re.search(r"\(([^)]*)\)", sig[sig.find(name):] if name in sig else sig)
            rows = _param_rows(pm.group(1), lang) if pm else []
            if rows:
                md += ["**Parameters**", "", "| Name | Type | Default | Description |", "|---|---|---|---|"]
                for nm, typ, dflt in rows:
                    md.append(f"| `{nm}` | {('`' + typ + '`') if typ else '—'} | {('`' + dflt + '`') if dflt else '—'} | {(doc['params'].get(nm) or _hint(nm)).replace('|', '/')} |")
                md.append("")
            if doc["returns"]:
                md += ["**Returns**", "", doc["returns"], ""]
            if doc["raises"]:
                md += ["**Throws**", ""] + [f"- {r}" for r in doc["raises"]] + [""]
            example_args = ", ".join(r[0] for r in rows)
            md += ["**Example**", "", f"```{lang}", f"{name}({example_args});" if lang != "go" else f"{name}({example_args})", "```", ""]
    return "\n".join(md).rstrip() + "\n", {"classes": len(types), "functions": len(funcs), "methods": 0, "dependencies": len(deps)}


def local_docs(code: str, language: str, title: str) -> tuple[str, dict[str, int]]:
    if language == "python":
        try:
            return _py_docs(code, title)
        except SyntaxError as e:
            md, stats = _clike_docs(code, "javascript", title)
            return md.replace("## Overview\n\n", f"## Overview\n\n> The code has a syntax error on line {e.lineno}; documentation is approximate.\n\n", 1), stats
    return _clike_docs(code, language, title)


AI_DOCS_SYSTEM = """You are a technical writer. Produce clear, accurate Markdown documentation for the given code.
Include: title, overview, dependencies, classes (with attributes and methods), functions (signature, description, parameters table, return value, exceptions), usage examples.
Only document what is actually in the code. Return JSON: {"markdown": "<full markdown document>"}"""


def run_docs(inp: DocsIn, allow_ai: bool) -> dict[str, Any]:
    title = inp.project_name or inp.filename or f"{LANGUAGE_LABEL[inp.language]} module"
    md, stats = local_docs(inp.code, inp.language, title)
    ai_used, ai_error = False, None
    if allow_ai:
        try:
            d = ai.chat_json(AI_DOCS_SYSTEM, f"Title: {title}\nLanguage: {LANGUAGE_LABEL[inp.language]}\n```{inp.language}\n{ai.clip_code(inp.code)}\n```", max_tokens=6000)
            md_ai = ai.as_str(d.get("markdown"), "", 200_000).strip()
            if md_ai:
                md, ai_used = md_ai + "\n", True
        except ai.AIError as exc:
            ai_error = str(exc)
    return {"language": inp.language, "markdown": md, "symbols": stats, "ai_used": ai_used, "ai_error": ai_error, "created_at": datetime.now(timezone.utc)}
