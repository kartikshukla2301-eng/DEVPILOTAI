"""Code explainer: AST-based for Python, structural heuristics for other languages, optional AI."""
from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from typing import Any

from app.analyzers.base import LANGUAGE_LABEL, mask_source
from app.analyzers.clike import CLASS_PATTERNS, CONTROL, FUNC_PATTERNS, _family
from app.schemas import ExplainIn
from app.services import ai

MAX_LINES = 400


def _short(node: ast.AST | None, limit: int = 60) -> str:
    if node is None:
        return ""
    try:
        s = ast.unparse(node)
    except Exception:
        return "…"
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _infer_type(v: ast.AST | None) -> str:
    if isinstance(v, ast.Constant):
        return {bool: "boolean", int: "integer", float: "float", str: "string", type(None): "None", bytes: "bytes"}.get(type(v.value), "value")
    return {
        ast.List: "list", ast.ListComp: "list", ast.Dict: "dict", ast.DictComp: "dict", ast.Set: "set", ast.SetComp: "set",
        ast.Tuple: "tuple", ast.GeneratorExp: "generator", ast.Lambda: "function", ast.JoinedStr: "string", ast.Compare: "boolean",
        ast.BoolOp: "boolean",
    }.get(type(v), "")  # type: ignore[arg-type]


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            return f.id
        if isinstance(f, ast.Attribute):
            return _short(f, 40)
    return ""


OP_NAMES = {ast.Add: "adding", ast.Sub: "subtracting", ast.Mult: "multiplying by", ast.Div: "dividing by", ast.FloorDiv: "integer-dividing by",
            ast.Mod: "taking the remainder with", ast.Pow: "raising to the power of", ast.BitOr: "OR-ing with", ast.BitAnd: "AND-ing with"}

ADVANCED_CALL_NOTES = {
    "sorted": "Timsort, O(n log n), returns a new list.", "sort": "in-place Timsort, O(n log n).", "append": "amortised O(1).",
    "insert": "O(n) because elements shift.", "pop": "O(1) at the end, O(n) elsewhere.", "index": "linear scan, O(n).",
    "count": "linear scan, O(n).", "join": "linear in total length.", "deepcopy": "recursive copy, proportional to object size.",
    "len": "O(1) for built-in containers.", "max": "O(n) scan.", "min": "O(n) scan.", "sum": "O(n) scan.",
    "heappush": "O(log n).", "heappop": "O(log n).", "bisect_left": "binary search, O(log n).", "lru_cache": "memoization decorator.",
}


def _explain_stmt(node: ast.stmt, level: str) -> str:
    b, adv = level == "beginner", level == "advanced"
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        names = ", ".join(f"`{a.name}`" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            s = f"Imports {names} from the `{node.module or '.'}` module."
        else:
            s = f"Imports the module{'s' if len(node.names) > 1 else ''} {names}."
        return s + (" Modules are libraries of ready-made code you can reuse." if b else "")
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        params = [a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]
        kind = "an asynchronous function" if isinstance(node, ast.AsyncFunctionDef) else "a function"
        s = f"Defines {kind} `{node.name}`" + (f" that takes {', '.join(f'`{p}`' for p in params)}." if params else " with no parameters.")
        if node.decorator_list:
            s += f" It is decorated with {', '.join('`@' + _short(d, 30) + '`' for d in node.decorator_list)}."
        if b:
            s += " A function is a named, reusable block of code that runs when it is called."
        if adv and node.returns is not None:
            s += f" Annotated return type: `{_short(node.returns)}`."
        return s
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(_short(x, 30) for x in node.bases)
        s = f"Defines a class `{node.name}`" + (f" that inherits from `{bases}`." if bases else ".")
        return s + (" A class is a blueprint for creating objects that bundle data and behaviour." if b else "")
    if isinstance(node, ast.Return):
        return f"Returns `{_short(node.value)}` to the caller." if node.value is not None else "Returns from the function without a value (None)."
    if isinstance(node, ast.If):
        s = f"Checks whether `{_short(node.test)}` is true; the indented block below runs only in that case."
        return s + (" Otherwise Python skips to the `elif`/`else` part, if any." if b else "")
    if isinstance(node, (ast.For, ast.AsyncFor)):
        s = f"Loops over `{_short(node.iter)}`, putting each item into `{_short(node.target)}` and running the indented block once per item."
        if adv and isinstance(node.iter, ast.Call) and _call_name(node.iter) == "range":
            s += " range() is lazy, so no list is built."
        return s
    if isinstance(node, ast.While):
        s = f"Repeats the indented block as long as `{_short(node.test)}` stays true."
        return s + (" Be careful: if the condition never becomes false the loop runs forever." if b else "")
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        tgt = ", ".join(f"`{_short(t, 30)}`" for t in targets)
        v = node.value
        if v is None:
            return f"Declares {tgt} with type `{_short(node.annotation)}`."  # type: ignore[union-attr]
        typ = _infer_type(v)
        cn = _call_name(v)
        if isinstance(v, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
            s = f"Builds a {typ} with a comprehension (`{_short(v)}`) and stores it in {tgt}."
            if b:
                s += " A comprehension is a compact way to build a collection from a loop."
        elif cn:
            s = f"Calls `{cn}(…)` and stores the result in {tgt}."
            if adv and cn.split(".")[-1] in ADVANCED_CALL_NOTES:
                s += f" Note: `{cn.split('.')[-1]}` is {ADVANCED_CALL_NOTES[cn.split('.')[-1]]}"
        else:
            s = f"Stores {('a ' + typ + ' ') if typ else ''}`{_short(v)}` in {tgt}."
            if b:
                s += " A variable is a named box that holds a value."
        return s
    if isinstance(node, ast.AugAssign):
        op = OP_NAMES.get(type(node.op), "combining with")
        return f"Updates `{_short(node.target)}` by {op} `{_short(node.value)}`."
    if isinstance(node, ast.Expr):
        v = node.value
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            return "Docstring: documents what this module/function/class does."
        cn = _call_name(v)
        if cn == "print":
            return f"Prints `{_short(v.args[0]) if isinstance(v, ast.Call) and v.args else ''}` to the console."  # type: ignore[union-attr]
        if isinstance(v, ast.Await):
            return f"Waits for the asynchronous operation `{_short(v.value)}` to finish."
        if cn:
            s = f"Calls `{cn}(…)`."
            if adv and cn.split(".")[-1] in ADVANCED_CALL_NOTES:
                s += f" `{cn.split('.')[-1]}` is {ADVANCED_CALL_NOTES[cn.split('.')[-1]]}"
            return s
        return f"Evaluates `{_short(v)}`."
    if isinstance(node, ast.Try):
        return "Starts a `try` block: if any line inside raises an error, control jumps to the matching `except` handler instead of crashing."
    if isinstance(node, (ast.With, ast.AsyncWith)):
        items = ", ".join(_short(i.context_expr, 40) for i in node.items)
        s = f"Uses `{items}` as a context manager, so it is set up here and cleaned up automatically at the end of the block."
        return s + (" (For files, this guarantees the file is closed.)" if b else "")
    if isinstance(node, ast.Raise):
        return f"Raises the error `{_short(node.exc)}`, stopping normal execution until something catches it." if node.exc else "Re-raises the current error."
    if isinstance(node, ast.Break):
        return "Exits the nearest loop immediately."
    if isinstance(node, ast.Continue):
        return "Skips the rest of this loop iteration and moves to the next one."
    if isinstance(node, ast.Pass):
        return "Does nothing; a placeholder where Python requires a statement."
    if isinstance(node, ast.Assert):
        return f"Asserts that `{_short(node.test)}` is true; otherwise raises AssertionError." + (" Assertions are removed with `python -O`." if adv else "")
    if isinstance(node, ast.Global):
        return f"Declares {', '.join(node.names)} as global, so assignments change the module-level variable."
    if isinstance(node, ast.Nonlocal):
        return f"Declares {', '.join(node.names)} as nonlocal, referring to the enclosing function's variable."
    if isinstance(node, ast.Delete):
        return f"Deletes `{', '.join(_short(t, 30) for t in node.targets)}`."
    if hasattr(ast, "Match") and isinstance(node, ast.Match):
        return f"Pattern-matches `{_short(node.subject)}` against the `case` clauses below."
    return f"Executes a `{type(node).__name__}` statement."


def _algorithm_py(tree: ast.AST, code: str) -> tuple[str, str, str, str]:
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    recursive, multi_recursive, memo = [], [], False
    for f in funcs:
        calls = [n for n in ast.walk(f) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == f.name]
        if calls:
            recursive.append(f.name)
            # count self-calls appearing in the same return/expression
            exprs = [n for n in ast.walk(f) if isinstance(n, (ast.Return, ast.Assign, ast.AugAssign))]
            if any(sum(1 for c in ast.walk(e) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == f.name) >= 2 for e in exprs):
                multi_recursive.append(f.name)
        if any("cache" in _short(d) for d in f.decorator_list):
            memo = True
    if re.search(r"\bmemo\b|\bdp\b|\bcache\b", code):
        memo = True

    def loop_depth(node: ast.AST, d: int = 0) -> int:
        best = d
        for ch in ast.iter_child_nodes(node):
            nd = d + 1 if isinstance(ch, (ast.For, ast.AsyncFor, ast.While, ast.comprehension)) else d
            best = max(best, loop_depth(ch, nd))
        return best

    depth = loop_depth(tree)
    halving = bool(re.search(r"(//\s*2|>>\s*1|\bmid\b|\blow\b.*\bhigh\b|\bleft\b.*\bright\b)", code))
    sorts = bool(re.search(r"\bsorted\(|\.sort\(", code))
    uses_hash = any(isinstance(n, (ast.Dict, ast.Set, ast.DictComp, ast.SetComp)) for n in ast.walk(tree)) or bool(re.search(r"\b(dict|set|Counter|defaultdict)\(", code))
    queue = bool(re.search(r"\bdeque\(|\.popleft\(|\bqueue\b", code, re.I))
    heap = "heapq" in code

    algo: list[str] = []
    if halving and any(isinstance(n, ast.While) for n in ast.walk(tree)):
        algo.append("binary search / halving: the search range is cut in half each step")
    if multi_recursive:
        algo.append(f"tree recursion in `{multi_recursive[0]}` (each call branches into several calls)" + (" with memoization (dynamic programming)" if memo else ""))
    elif recursive:
        algo.append(f"recursion in `{recursive[0]}`")
    if memo and not multi_recursive:
        algo.append("dynamic programming / caching of intermediate results")
    if queue:
        algo.append("queue-based traversal (typical of breadth-first search)")
    if heap:
        algo.append("priority queue (heap)")
    if sorts:
        algo.append("sorting")
    if uses_hash:
        algo.append("hash-based lookups (dict/set) for O(1) average access")
    if depth >= 2 and not algo:
        algo.append(f"nested iteration ({depth} levels), e.g. comparing pairs of elements")
    elif depth == 1 and not algo:
        algo.append("a single linear pass over the data")
    algorithm = ("Uses " + "; ".join(algo) + ".") if algo else "Straight-line code without significant loops or recursion."

    if multi_recursive and not memo:
        time = "O(2^n)"
    elif halving and depth <= 1 and not sorts:
        time = "O(log n)"
    elif sorts and depth <= 1:
        time = "O(n log n)"
    elif depth >= 1:
        time = "O(n)" if depth == 1 else f"O(n^{depth})"
        if recursive and depth == 0:
            time = "O(n)"
    elif recursive:
        time = "O(n)"
    else:
        time = "O(1)"

    allocs_in_loop = any(isinstance(n, (ast.ListComp, ast.DictComp, ast.SetComp)) for n in ast.walk(tree)) or bool(
        re.search(r"\.append\(|\[\]\s*$|= \[\]|= \{\}|dict\(\)|set\(\)|list\(", code, re.M))
    if multi_recursive and memo:
        space = "O(n)"
    elif recursive:
        space = "O(n) (call stack)" if not halving else "O(log n) (call stack)"
    elif allocs_in_loop and depth >= 1:
        space = "O(n)"
    elif depth >= 2 and re.search(r"\[\s*\[", code):
        space = "O(n^2)"
    else:
        space = "O(1) extra"
    return algorithm, time, space, ("Estimated from loop nesting, recursion and well-known operations; "
                                    "n is the size of the main input. Treat this as a guide, not a proof.")


def _explain_python(code: str, level: str) -> dict[str, Any]:
    tree = ast.parse(code)
    lines = code.splitlines()
    by_line: dict[int, ast.stmt] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            by_line.setdefault(node.lineno, node)
    handler_lines = {n.lineno: n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)}
    # lines covered by a multi-line statement start
    continuation: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)) and node.end_lineno:
            continuation.update(range(node.lineno + 1, node.end_lineno + 1))

    out_lines = []
    for n, raw in enumerate(lines[:MAX_LINES], start=1):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#"):
            text = f"Comment: {s.lstrip('#').strip()}"
        elif n in by_line:
            text = _explain_stmt(by_line[n], level)
        elif n in handler_lines:
            h = handler_lines[n]
            text = f"Handles errors of type `{_short(h.type)}` raised in the try block" + (f", available as `{h.name}`." if h.name else ".") if h.type else "Catches any error raised in the try block (a bare except — usually too broad)."
        elif s.startswith("else"):
            text = "Runs when none of the previous conditions matched (or, after a loop/try, when it finished without break/error)."
        elif s.startswith("elif"):
            text = f"Otherwise, checks `{s[4:].rstrip(':').strip()}`."
        elif s.startswith("finally"):
            text = "Always runs at the end of the try statement, whether or not an error occurred (used for cleanup)."
        elif s.startswith("case "):
            text = f"A match case: runs when the subject matches `{s[5:].rstrip(':')}`."
        elif s.startswith("@"):
            text = f"Decorator `{s}` modifies the function or class defined below."
        elif n in continuation:
            text = "Continues the statement from the previous line."
        else:
            continue
        out_lines.append({"line": n, "code": raw, "explanation": text})

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            params = [a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs if a.arg not in ("self", "cls")]
            returns = [r for r in ast.walk(node) if isinstance(r, ast.Return) and r.value is not None]
            calls = sorted({_call_name(c) for c in ast.walk(node) if isinstance(c, ast.Call) and _call_name(c)} - {"print"})[:6]
            parts = [doc.split("\n")[0] if doc else f"`{node.name}` " + (f"works with {', '.join(f'`{p}`' for p in params)}" if params else "takes no inputs") + "."]
            if returns:
                parts.append(f"It returns {'values such as' if len(returns) > 1 else ''} `{_short(returns[0].value, 50)}`.")
            else:
                parts.append("It does not return a value (returns None).")
            if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == node.name for c in ast.walk(node)):
                parts.append("It is recursive (calls itself).")
            if calls and level != "beginner":
                parts.append(f"Calls: {', '.join(f'`{c}`' for c in calls)}.")
            functions.append({"name": node.name, "kind": "async function" if isinstance(node, ast.AsyncFunctionDef) else "function", "line": node.lineno, "explanation": " ".join(parts)})
        elif isinstance(node, ast.ClassDef):
            methods = [m.name for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
            doc = ast.get_docstring(node)
            functions.append({"name": node.name, "kind": "class", "line": node.lineno,
                              "explanation": (doc.split("\n")[0] + " " if doc else "") + (f"Methods: {', '.join(f'`{m}`' for m in methods)}." if methods else "Has no methods.")})

    variables: dict[str, dict[str, Any]] = {}
    for node in ast.walk(tree):
        targets, value = [], None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            targets, value = [node.target], None
        for t in targets:
            for nm in [x for x in ast.walk(t) if isinstance(x, ast.Name)]:
                if nm.id in variables or len(variables) >= 40:
                    continue
                if isinstance(node, (ast.For, ast.AsyncFor)):
                    expl = f"Loop variable; takes each value from `{_short(node.iter, 40)}` in turn."
                else:
                    typ = _infer_type(value)
                    expl = f"Holds {('a ' + typ) if typ else 'the result of'} `{_short(value, 50)}`."
                variables[nm.id] = {"name": nm.id, "kind": "variable", "line": nm.lineno, "explanation": expl}

    algorithm, time, space, note = _algorithm_py(tree, code)
    doc = ast.get_docstring(tree)
    top_funcs = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    top_classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    imports = sorted({a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} |
                     {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module})
    purpose_bits = [doc.split("\n")[0]] if doc else []
    if top_classes:
        purpose_bits.append(f"Defines the class{'es' if len(top_classes) > 1 else ''} {', '.join(f'`{c}`' for c in top_classes)}.")
    if top_funcs:
        purpose_bits.append(f"Defines {len(top_funcs)} function{'s' if len(top_funcs) > 1 else ''}: {', '.join(f'`{f}`' for f in top_funcs[:8])}.")
    if imports:
        purpose_bits.append(f"Relies on {', '.join(f'`{i}`' for i in imports[:8])}.")
    if re.search(r"\binput\(", code):
        purpose_bits.append("Reads input from the user.")
    if re.search(r"\bprint\(", code):
        purpose_bits.append("Prints results to the console.")
    if 'if __name__ == "__main__"' in code or "if __name__ == '__main__'" in code:
        purpose_bits.append("Can be run directly as a script.")
    purpose_bits.append(algorithm)
    return {"purpose": " ".join(purpose_bits), "lines": out_lines, "functions": functions, "variables": list(variables.values()),
            "algorithm": algorithm, "time_complexity": time, "space_complexity": space, "complexity_note": note}


# ---------------------------------------------------------------------------
# brace languages
# ---------------------------------------------------------------------------
PRINT_RE = re.compile(r"console\.(?:log|error|warn)|System\.out\.print|printf\s*\(|std::cout|cout\s*<<|fmt\.Print|puts\s*\(")
DECL_RE = {
    "js": re.compile(r"\b(const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::\s*([^=]+?))?\s*=\s*(.+?);?$"),
    "java": re.compile(r"^\s*(?:final\s+)?([\w<>\[\],.? ]+?)\s+([A-Za-z_]\w*)\s*=\s*(.+?);"),
    "c": re.compile(r"^\s*(?:const\s+|static\s+)*([\w:<>*&]+(?:\s*[*&])?)\s+\**([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*=\s*(.+?);"),
    "go": re.compile(r"(?:\bvar\s+([A-Za-z_]\w*)\s*([\w\[\]*.]+)?\s*=\s*(.+)$|^\s*([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)\s*:=\s*(.+)$)"),
}


def _explain_clike_line(s: str, fam: str, level: str, lang: str) -> str | None:
    b, adv = level == "beginner", level == "advanced"
    if s in ("}", "};", "})", "});", ")", "]", "});"):
        return "Closes the current block."
    if s.startswith(("//", "/*", "*")):
        return "Comment: " + s.lstrip("/*").rstrip("*/").strip()
    if re.match(r"#include\s*[<\"]([^>\"]+)", s):
        h = re.match(r"#include\s*[<\"]([^>\"]+)", s).group(1)  # type: ignore[union-attr]
        return f"Includes the header `{h}` so its declarations can be used." + (" Headers tell the compiler what functions exist." if b else "")
    if s.startswith("#define"):
        return "Defines a preprocessor macro (text substitution before compilation)."
    if re.match(r"(import|package|using)\b", s) or re.match(r"(const|let|var)\s+.+=\s*require\(", s):
        if s.startswith("package"):
            return f"Declares that this file belongs to the package `{s.split()[1].rstrip(';')}`."
        return f"Imports dependencies: `{s.rstrip(';')[:80]}`." + (" This makes code from other files or libraries available." if b else "")
    cm = CLASS_PATTERNS[fam].search(s)
    if cm:
        return f"Declares the type `{cm.group(1)}`." + (" A class/struct groups related data and functions." if b else "")
    if re.match(r"(\}\s*)?else\s+if\b", s):
        cond = re.search(r"if\s*(.*)", s).group(1).rstrip("{").strip()  # type: ignore[union-attr]
        return f"Otherwise, checks another condition: `{cond}`."
    if re.match(r"(\}\s*)?else\b", s):
        return "Runs when none of the previous conditions were true."
    if re.match(r"if\b", s):
        cond = re.sub(r"^if\s*", "", s).rstrip("{").strip()
        return f"Checks the condition `{cond}`; the block runs only if it is true."
    if re.match(r"for\b", s):
        if re.search(r"\b(of|in)\b", s) or ":" in s and fam == "java" or "range" in s:
            return f"Loops over each element: `{s.rstrip('{').strip()}`." + (" The block runs once per item." if b else "")
        return f"A counting loop: `{s.rstrip('{').strip()}` (initialise; condition; update)." + (" It repeats while the condition is true." if b else "")
    if re.match(r"while\b", s):
        cond = re.sub(r"^while\s*", "", s).rstrip("{").strip()
        return f"Repeats the block while `{cond}` is true."
    if re.match(r"do\b", s):
        return "Starts a do-while loop: the block runs at least once, then repeats while the condition holds."
    if re.match(r"switch\b", s):
        subj = re.sub(r"^switch\s*", "", s).rstrip("{").strip()
        return f"Chooses a branch based on the value of `{subj}`."
    if re.match(r"case\b|default\s*:", s):
        return f"A branch of the switch: `{s.rstrip(':')}`."
    if re.match(r"return\b", s):
        v = s[6:].strip().rstrip(";")
        return f"Returns `{v}` to the caller." if v else "Returns from the function."
    if re.match(r"(try)\b", s):
        return "Starts a block whose errors are handled by the following catch."
    if re.match(r"(\}\s*)?catch\b", s):
        return f"Handles errors thrown in the try block: `{s.strip('}').strip().rstrip('{').strip()}`."
    if re.match(r"(\}\s*)?finally\b", s):
        return "Always runs after try/catch, used for cleanup."
    if re.match(r"throw\b|panic\(", s):
        return "Throws an error, stopping normal execution until it is caught."
    if re.match(r"defer\b", s):
        return f"Schedules `{s[5:].strip()}` to run when the surrounding function returns."
    if re.match(r"go\s+\w", s):
        return "Starts a new goroutine (runs the call concurrently)."
    if re.match(r"break\b", s):
        return "Exits the nearest loop or switch."
    if re.match(r"continue\b", s):
        return "Skips to the next loop iteration."
    for p in FUNC_PATTERNS[fam]:
        fm = p.search(s)
        if fm and fm.group(1) not in CONTROL:
            params = re.search(r"\(([^)]*)\)", s)
            ptxt = params.group(1).strip() if params else ""
            return f"Defines the function `{fm.group(1)}`" + (f" with parameters `{ptxt}`." if ptxt else " with no parameters.") + (
                " A function is a reusable block of code." if b else "")
    if PRINT_RE.search(s):
        return "Prints output to the console."
    dm = DECL_RE[fam].search(s)
    if dm:
        if fam == "js":
            kind, name, typ, val = dm.groups()
            s2 = f"Declares {'a constant' if kind == 'const' else 'a variable'} `{name}`" + (f" of type `{typ.strip()}`" if typ else "") + f" and sets it to `{val[:60]}`."
            if adv and kind == "const":
                s2 += " `const` prevents reassignment, not mutation of the object."
            return s2
        if fam == "go":
            if dm.group(1):
                return f"Declares the variable `{dm.group(1)}` and sets it to `{dm.group(3)[:60]}`."
            return f"Declares and initialises `{dm.group(4)}` from `{dm.group(5)[:60]}` (type is inferred)."
        typ, name, val = dm.groups()
        return f"Declares `{name}` of type `{typ.strip()}` and sets it to `{val[:60]}`."
    if re.search(r"(?<![=!<>])=(?!=)", s) and not s.startswith("for"):
        lhs, rhs = s.split("=", 1)
        op = lhs[-1] if lhs and lhs[-1] in "+-*/%" else ""
        return f"Updates `{lhs.rstrip('+-*/% ').strip()}` " + (f"with `{op}=` `{rhs.strip().rstrip(';')[:60]}`." if op else f"to `{rhs.strip().rstrip(';')[:60]}`.")
    if re.search(r"\+\+|--", s):
        return f"Increments/decrements a counter: `{s.rstrip(';')}`."
    cm2 = re.match(r"([\w.$:>-]+)\s*\(", s)
    if cm2:
        return f"Calls `{cm2.group(1)}(…)`."
    return None


def _explain_clike(code: str, lang: str, level: str) -> dict[str, Any]:
    fam = _family(lang)
    lines = code.splitlines()
    masked = mask_source(code, lang).splitlines()
    out, functions, variables = [], [], {}
    for n, raw in enumerate(lines[:MAX_LINES], start=1):
        s = raw.strip()
        if not s:
            continue
        text = _explain_clike_line(s, fam, level, lang)
        if text:
            out.append({"line": n, "code": raw, "explanation": text})
        ms = masked[n - 1] if n - 1 < len(masked) else s
        for p in FUNC_PATTERNS[fam]:
            fm = p.search(ms)
            if fm and fm.group(1) not in CONTROL:
                params = re.search(r"\(([^)]*)\)", s)
                ptxt = params.group(1).strip() if params else ""
                functions.append({"name": fm.group(1), "kind": "function", "line": n,
                                  "explanation": f"`{fm.group(1)}` " + (f"takes `{ptxt}`." if ptxt else "takes no parameters.")})
                break
        cm = CLASS_PATTERNS[fam].search(ms)
        if cm:
            functions.append({"name": cm.group(1), "kind": "type", "line": n, "explanation": f"Type `{cm.group(1)}` declared here."})
        dm = DECL_RE[fam].search(s)
        if dm and len(variables) < 40:
            if fam == "go":
                names = (dm.group(1) or dm.group(4) or "").split(",")
                val = dm.group(3) or dm.group(5) or ""
            elif fam == "js":
                names, val = [dm.group(2)], dm.group(4)
            else:
                names, val = [dm.group(2)], dm.group(3)
            for nm in names:
                nm = nm.strip()
                if nm and nm not in variables and nm != "_":
                    variables[nm] = {"name": nm, "kind": "variable", "line": n, "explanation": f"Initialised to `{val.strip().rstrip(';')[:60]}`."}

    body = "\n".join(masked)
    # loop depth via braces
    depth, best, stack = 0, 0, []
    for ln in masked:
        is_loop = bool(re.search(r"\b(for|while)\b", ln))
        for ch in ln:
            if ch == "{":
                stack.append(is_loop)
                is_loop = False
                depth = sum(stack)
                best = max(best, depth)
            elif ch == "}" and stack:
                stack.pop()
                depth = sum(stack)
    fnames = [f["name"] for f in functions if f["kind"] == "function"]
    recursive = [f for f in fnames if len(re.findall(rf"(?<![\w.]){re.escape(f)}\s*\(", body)) >= 2]
    multi = [f for f in recursive if re.search(rf"{re.escape(f)}\s*\([^;]*{re.escape(f)}\s*\(", body)]
    halving = bool(re.search(r"/\s*2\b|>>\s*1|\bmid\b", body))
    sorts = bool(re.search(r"\bsort\s*\(|\.sort\(|Arrays\.sort|Collections\.sort|sort\.(Slice|Ints|Strings)", body))
    hashing = bool(re.search(r"\b(Map|Set|HashMap|HashSet|unordered_map|unordered_set|map\[|new Map|new Set|dict)\b", body))
    algo = []
    if halving and re.search(r"\bwhile\b", body):
        algo.append("binary search / halving")
    if multi:
        algo.append(f"tree recursion in `{multi[0]}`")
    elif recursive:
        algo.append(f"recursion in `{recursive[0]}`")
    if sorts:
        algo.append("sorting")
    if hashing:
        algo.append("hash-based lookups")
    if not algo:
        algo.append("nested iteration" if best >= 2 else "a single linear pass" if best == 1 else "straight-line logic")
    memo = bool(re.search(r"\bmemo\b|\bdp\b|\bcache\b", body))
    time = "O(2^n)" if multi and not memo else "O(log n)" if halving and best <= 1 and not sorts else "O(n log n)" if sorts and best <= 1 else (
        f"O(n^{best})" if best >= 2 else "O(n)" if best == 1 or recursive else "O(1)")
    space = "O(n) (call stack)" if recursive else "O(n)" if re.search(r"\bnew\b|malloc|make\(|\[\]|push|append|add\(", body) and best >= 1 else "O(1) extra"
    label = LANGUAGE_LABEL[lang]
    purpose = f"{label} code that " + (f"defines {', '.join(f'`{f}`' for f in fnames[:8])}" if fnames else "runs a sequence of statements") + \
              (" and prints output" if PRINT_RE.search(code) else "") + f". It uses {'; '.join(algo)}."
    return {"purpose": purpose, "lines": out, "functions": functions, "variables": list(variables.values()),
            "algorithm": "Uses " + "; ".join(algo) + ".", "time_complexity": time, "space_complexity": space,
            "complexity_note": "Estimated from loop nesting, recursion and well-known operations; n is the main input size. Treat as a guide."}


def local_explain(code: str, language: str, level: str) -> dict[str, Any]:
    if language == "python":
        try:
            return _explain_python(code, level)
        except SyntaxError as e:
            r = _explain_clike(code, "javascript", level)  # crude structural fallback
            r["purpose"] = f"The code has a syntax error on line {e.lineno} ({e.msg}), so only a rough explanation is possible. " + r["purpose"]
            return r
    return _explain_clike(code, language, level)


AI_EXPLAIN_SYSTEM = """You are a patient programming teacher. Explain code at the requested level (beginner: plain language, no jargon; intermediate: normal developer terms; advanced: precise, mention semantics, edge cases and performance).
Return JSON:
{"purpose": "overall purpose", "lines": [{"line": <int>, "code": "<exact source line>", "explanation": "..."}],
 "functions": [{"name": "...", "kind": "function|class|method", "line": <int>, "explanation": "..."}],
 "variables": [{"name": "...", "kind": "variable", "line": <int>, "explanation": "..."}],
 "algorithm": "algorithm/approach explanation", "time_complexity": "Big-O", "space_complexity": "Big-O",
 "complexity_note": "short justification"}
Explain every meaningful line (skip blank lines)."""


def run_explain(inp: ExplainIn, allow_ai: bool) -> dict[str, Any]:
    base = local_explain(inp.code, inp.language, inp.level)
    out = {**base, "language": inp.language, "level": inp.level, "ai_used": False, "ai_error": None, "created_at": datetime.now(timezone.utc)}
    if not allow_ai:
        return out
    try:
        d = ai.chat_json(AI_EXPLAIN_SYSTEM, f"Level: {inp.level}\nLanguage: {LANGUAGE_LABEL[inp.language]}\n```{inp.language}\n{ai.clip_code(inp.code)}\n```", max_tokens=6000)
    except ai.AIError as exc:
        out["ai_error"] = str(exc)
        return out
    src = inp.code.splitlines()

    def items(key: str, with_code: bool = False) -> list[dict[str, Any]]:
        res = []
        for x in d.get(key) or []:
            if not isinstance(x, dict):
                continue
            ln = ai.as_int(x.get("line"))
            if with_code:
                if not ln or ln > len(src):
                    continue
                res.append({"line": ln, "code": src[ln - 1], "explanation": ai.as_str(x.get("explanation"), "", 2000)})
            else:
                res.append({"name": ai.as_str(x.get("name"), "?", 100), "kind": ai.as_str(x.get("kind"), "symbol", 30),
                            "line": ln if ln and ln <= len(src) else None, "explanation": ai.as_str(x.get("explanation"), "", 2000)})
        return res

    out.update({
        "purpose": ai.as_str(d.get("purpose"), base["purpose"], 5000),
        "lines": items("lines", True) or base["lines"],
        "functions": items("functions") or base["functions"],
        "variables": items("variables") or base["variables"],
        "algorithm": ai.as_str(d.get("algorithm"), base["algorithm"], 5000),
        "time_complexity": ai.as_str(d.get("time_complexity"), base["time_complexity"], 100),
        "space_complexity": ai.as_str(d.get("space_complexity"), base["space_complexity"], 100),
        "complexity_note": ai.as_str(d.get("complexity_note"), base["complexity_note"], 1000),
        "ai_used": True,
    })
    return out
