"""Debugging assistant: local error-pattern knowledge base + optional AI."""
from __future__ import annotations

import ast
import difflib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.analyzers.base import LANGUAGE_LABEL, mask_source
from app.analyzers.registry import run_static_analysis
from app.schemas import DebugIn
from app.services import ai

PY_STDLIB_COMMON = {"math", "os", "sys", "json", "re", "random", "time", "datetime", "collections", "itertools",
                    "functools", "pathlib", "string", "statistics", "csv", "typing", "copy", "heapq", "bisect", "subprocess"}


# ---------------------------------------------------------------------------
# error location
# ---------------------------------------------------------------------------
def extract_line(error: str, language: str, n_lines: int) -> int | None:
    pats: list[str]
    if language == "python":
        found = re.findall(r'File "[^"]*", line (\d+)', error)
        if found:
            # prefer the innermost frame that belongs to the user's snippet (not site-packages)
            frames = re.findall(r'File "([^"]*)", line (\d+)', error)
            user = [int(ln) for f, ln in frames if "site-packages" not in f and "lib/python" not in f.replace("\\", "/").lower()]
            cand = (user or [int(x) for x in found])[-1]
            return cand if 1 <= cand <= n_lines else None
        pats = [r"line (\d+)"]
    elif language in ("javascript", "typescript"):
        pats = [r"\(\S*?:(\d+):\d+\)", r"\S+\.[cm]?[jt]sx?:(\d+)", r"\((\d+),\d+\)", r"line (\d+)"]
    elif language == "java":
        pats = [r"\.java:(\d+)", r"line (\d+)"]
    elif language == "go":
        pats = [r"\.go:(\d+)", r"line (\d+)"]
    else:
        pats = [r"\.(?:c|cc|cpp|cxx|h|hpp):(\d+)", r":(\d+):\d+:", r"line (\d+)"]
    for p in pats:
        for m in re.finditer(p, error):
            ln = int(m.group(1))
            if 1 <= ln <= n_lines:
                return ln
    return None


# ---------------------------------------------------------------------------
# fixers: return modified code or None
# ---------------------------------------------------------------------------
def _identifiers(code: str, language: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_$][\w$]*", mask_source(code, language)))


def _replace_word(code: str, old: str, new: str, line: int | None) -> str:
    lines = code.splitlines()
    pat = re.compile(rf"(?<![\w$.]){re.escape(old)}(?![\w$])")
    targets = [line - 1] if line else range(len(lines))
    changed = False
    for i in targets:
        if 0 <= i < len(lines) and pat.search(lines[i]):
            lines[i] = pat.sub(new, lines[i])
            changed = True
    if not changed:  # error line was wrong; fix everywhere
        lines = [pat.sub(new, ln) for ln in lines]
    return "\n".join(lines) + ("\n" if code.endswith("\n") else "")


def fix_undefined_name(name: str, code: str, language: str, line: int | None) -> tuple[str | None, str]:
    idents = _identifiers(code, language) - {name}
    match = difflib.get_close_matches(name, sorted(idents), n=1, cutoff=0.75)
    if match:
        return _replace_word(code, name, match[0], line), f"`{name}` looks like a misspelling of `{match[0]}`, which is defined in the code."
    if language == "python" and name in PY_STDLIB_COMMON:
        return f"import {name}\n" + code, f"`{name}` is a standard-library module that was used without being imported."
    return None, f"`{name}` is used but never defined or imported in the visible code."


def _py_parses(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def fix_python_syntax(code: str, line: int | None) -> str | None:
    """Try a few mechanical repairs and keep the first that makes the code parse."""
    lines = code.splitlines()
    cands: list[str] = []
    if "\t" in code:
        cands.append(code.expandtabs(4))
    if line and 1 <= line <= len(lines):
        i = line - 1
        ln = lines[i]
        s = ln.rstrip()
        if re.match(r"\s*(if|elif|else|for|while|def|class|try|except|finally|with)\b", s) and not s.endswith(":"):
            cands.append("\n".join(lines[:i] + [s + ":"] + lines[i + 1:]))
        for opener, closer in (("(", ")"), ("[", "]"), ("{", "}")):
            if s.count(opener) > s.count(closer):
                cands.append("\n".join(lines[:i] + [s + closer * (s.count(opener) - s.count(closer))] + lines[i + 1:]))
        if i > 0 and lines[i - 1].rstrip().endswith(":"):
            ind = len(lines[i - 1]) - len(lines[i - 1].lstrip())
            cands.append("\n".join(lines[:i] + [" " * (ind + 4) + ln.lstrip()] + lines[i + 1:]))
        if i > 0:
            prev = lines[i - 1].rstrip()
            for opener, closer in (("(", ")"), ("[", "]"), ("{", "}")):
                if prev.count(opener) > prev.count(closer):
                    cands.append("\n".join(lines[: i - 1] + [prev + closer] + lines[i - 1:][1:]))
        ind = len(ln) - len(ln.lstrip())
        if ind:
            for k in range(i - 1, -1, -1):
                pi = len(lines[k]) - len(lines[k].lstrip())
                if lines[k].strip() and pi < ind:
                    cands.append("\n".join(lines[:i] + [" " * pi + ln.lstrip()] + lines[i + 1:]))
                    break
    for c in cands:
        if _py_parses(c):
            return c + ("\n" if code.endswith("\n") and not c.endswith("\n") else "")
    return None


def fix_missing_semicolon(code: str, line: int | None, before_token: bool) -> str | None:
    if not line:
        return None
    lines = code.splitlines()
    i = line - 1
    if before_token or (0 <= i < len(lines) and not lines[i].strip()):
        k = i - 1
        while k >= 0 and not lines[k].strip():
            k -= 1
        i = k
    if not (0 <= i < len(lines)):
        return None
    s = lines[i].rstrip()
    if s.endswith((";", "{", "}", ",")):
        if before_token:
            return None
        k = i - 1
        while k >= 0 and not lines[k].strip():
            k -= 1
        if k < 0 or lines[k].rstrip().endswith((";", "{", "}")):
            return None
        i, s = k, lines[k].rstrip()
    lines[i] = s + ";"
    return "\n".join(lines) + ("\n" if code.endswith("\n") else "")


def fix_optional_chaining(code: str, line: int | None, prop: str) -> str | None:
    if not line:
        return None
    lines = code.splitlines()
    i = line - 1
    if not (0 <= i < len(lines)):
        return None
    new = re.sub(rf"(?<!\?)\.({re.escape(prop)})\b", r"?.\1", lines[i], count=1) if prop else lines[i]
    if new == lines[i]:
        new = re.sub(rf"\[\s*(['\"]){re.escape(prop)}\1\s*\]", rf"?.[\1{prop}\1]", lines[i], count=1)
    if new == lines[i]:
        return None
    lines[i] = new
    return "\n".join(lines) + ("\n" if code.endswith("\n") else "")


def fix_python_keyerror(code: str, line: int | None, key: str) -> str | None:
    if not line:
        return None
    lines = code.splitlines()
    i = line - 1
    if not (0 <= i < len(lines)):
        return None
    pat = re.compile(rf"(\w[\w.]*)\[\s*(['\"]){re.escape(key)}\2\s*\](?!\s*=[^=])")
    new = pat.sub(lambda m: f"{m.group(1)}.get({m.group(2)}{key}{m.group(2)})", lines[i])
    if new == lines[i]:
        return None
    lines[i] = new
    return "\n".join(lines) + ("\n" if code.endswith("\n") else "")


def fix_go_unused_import(code: str, pkg: str) -> str | None:
    lines = code.splitlines()
    out = [ln for ln in lines if not re.fullmatch(rf'\s*(?:import\s+)?(?:\w+\s+)?"{re.escape(pkg)}"\s*', ln)]
    if len(out) == len(lines):
        return None
    return "\n".join(out) + ("\n" if code.endswith("\n") else "")


def fix_python_division(code: str, line: int | None) -> str | None:
    if not line:
        return None
    lines = code.splitlines()
    i = line - 1
    if not (0 <= i < len(lines)):
        return None
    m = re.search(r"(?<![/*])/\s*([A-Za-z_][\w.]*|\([^()]+\))", lines[i])
    if not m or m.group(1).isdigit():
        return None
    denom = m.group(1)
    ind = re.match(r"\s*", lines[i]).group(0)
    stripped = lines[i].strip()
    if stripped.startswith("return "):
        guard = [f"{ind}if {denom} == 0:", f"{ind}    return 0  # TODO: choose the right value for an empty/zero denominator"]
    else:
        guard = [f"{ind}if {denom} == 0:", f'{ind}    raise ValueError("{denom} must not be zero")']
    new = lines[:i] + guard + lines[i:]
    candidate = "\n".join(new) + ("\n" if code.endswith("\n") else "")
    return candidate if _py_parses(candidate) else None


# ---------------------------------------------------------------------------
# knowledge base
# ---------------------------------------------------------------------------
@dataclass
class Ctx:
    code: str
    language: str
    error: str
    line: int | None
    m: re.Match


@dataclass
class Pattern:
    langs: set[str]
    regex: str
    error_type: str
    explain: Callable[[Ctx], str]
    cause: Callable[[Ctx], str]
    steps: list[str]
    prevent: list[str]
    fixer: Callable[[Ctx], tuple[str | None, str | None]] | None = None
    confidence: str = "medium"
    compiled: re.Pattern = field(init=False)

    def __post_init__(self) -> None:
        self.compiled = re.compile(self.regex, re.I | re.M)


def _const(s: str) -> Callable[[Ctx], str]:
    return lambda c: s


def _undefined_fixer(group: int = 1):
    def f(c: Ctx) -> tuple[str | None, str | None]:
        code, note = fix_undefined_name(c.m.group(group), c.code, c.language, c.line)
        return code, note
    return f


ALL = {"python", "javascript", "typescript", "java", "cpp", "c", "go"}
JS = {"javascript", "typescript"}
CF = {"c", "cpp"}

PATTERNS: list[Pattern] = [
    # ------------------------------ Python
    Pattern({"python"}, r"NameError: name '(\w+)' is not defined", "NameError",
            lambda c: f"Python tried to look up the name `{c.m.group(1)}` but it does not exist in the current scope.",
            lambda c: "", [
                "Check the spelling and capitalisation of the name on the reported line.",
                "Make sure the variable is assigned before this line runs (assignments inside an if/for may not have executed).",
                "If it is a module or function from a library, add the matching import.",
                "If it is defined inside another function, pass it as a parameter or return it."],
            ["Use an editor with linting (Ruff/Pylance) to catch undefined names before running.",
             "Initialise variables before conditional branches that use them."],
            _undefined_fixer(), "high"),
    Pattern({"python"}, r"UnboundLocalError: (?:local variable '(\w+)' referenced before assignment|cannot access local variable '(\w+)')", "UnboundLocalError",
            lambda c: f"`{c.m.group(1) or c.m.group(2)}` is assigned somewhere in the function, so Python treats it as local everywhere in that function, but it is read before that assignment runs.",
            lambda c: "A local assignment shadows a global/outer variable of the same name, or the assignment is inside a branch that did not execute.",
            ["Initialise the variable at the top of the function.",
             "If you intend to modify a module-level variable, declare `global name` (or better, pass it in and return the new value).",
             "For closures, use `nonlocal name`."],
            ["Avoid reusing names of outer variables for locals.", "Prefer returning values over mutating globals."], None, "high"),
    Pattern({"python"}, r"TypeError: '(NoneType)' object is not (subscriptable|iterable|callable)", "TypeError (None value)",
            lambda c: f"A value that is `None` was used as if it were {'a list/dict' if c.m.group(2) == 'subscriptable' else 'iterable' if c.m.group(2) == 'iterable' else 'a function'}.",
            lambda c: "A function returned None (often because it has no return statement, or uses an in-place method such as list.sort() that returns None), and the result was then used.",
            ["Find which expression on the reported line evaluates to None (print or inspect it in a debugger).",
             "Check the function that produced it: does every code path `return` a value?",
             "Remember `list.sort()`, `list.append()`, `dict.update()` return None; use `sorted(x)` if you need the result.",
             "Add an explicit check: `if value is None: ...` before using it."],
            ["Add type hints with Optional[...] and run a type checker (mypy/pyright).", "Return early with a clear error when inputs are missing."]),
    Pattern({"python"}, r"AttributeError: '(\w+)' object has no attribute '(\w+)'", "AttributeError",
            lambda c: f"The code accessed `.{c.m.group(2)}` on a value of type `{c.m.group(1)}`, which has no such attribute or method.",
            lambda c: ("The value is None, usually because a previous call returned nothing." if c.m.group(1) == "NoneType"
                       else f"Either `{c.m.group(2)}` is misspelled, or the variable holds a different type than expected (`{c.m.group(1)}`)."),
            ["Print `type(obj)` and `dir(obj)` right before the failing line to see what the object really is.",
             "Check the spelling of the attribute against the class/library documentation.",
             "If the object can be None, guard it with `if obj is not None:`."],
            ["Use type hints and an IDE with autocompletion.", "Avoid reusing one variable for values of different types."]),
    Pattern({"python"}, r"TypeError: can only concatenate str \(not \"(\w+)\"\) to str|TypeError: unsupported operand type\(s\) for ([^:]+): '(\w+)' and '(\w+)'", "TypeError (operand types)",
            lambda c: "An operator was applied to two values whose types do not support it together (for example adding a string and a number).",
            lambda c: "One of the values has a different type than expected — commonly input() returning a string, or a number that needs to be formatted into text.",
            ["Identify the operands on the reported line and print their types.",
             "Convert explicitly: `int(text)` / `float(text)` for arithmetic, or `str(n)` / an f-string for text.",
             "Prefer f-strings for building messages: `f\"Total: {total}\"`."],
            ["Validate and convert input at the boundary (right after reading it).", "Use type hints to document expected types."], None, "high"),
    Pattern({"python"}, r"TypeError: (\w+)\(\) (?:takes|missing) ([^\n]+)", "TypeError (wrong arguments)",
            lambda c: f"`{c.m.group(1)}()` was called with the wrong number of arguments ({c.m.group(2).strip()}).",
            lambda c: "The call site and the function definition disagree about parameters. For methods, a common cause is forgetting `self` in the definition, or calling an instance method on the class.",
            ["Compare the call on the reported line with the function's `def` line.",
             "For methods, ensure the first parameter is `self` and call it on an instance (`obj.method()`).",
             "Use keyword arguments to make calls explicit."],
            ["Keep signatures small; use keyword-only arguments for optional settings."], None, "high"),
    Pattern({"python"}, r"IndexError: (list|tuple|string) index out of range", "IndexError",
            lambda c: f"The code accessed a {c.m.group(1)} position that does not exist.",
            lambda c: "The index is ≥ the length (or the sequence is empty). Typical causes: off-by-one loop bounds such as `range(len(x) + 1)`, using `x[i + 1]` at the last element, or assuming input is non-empty.",
            ["Print `len(seq)` and the index right before the failing line.",
             "Check loop bounds: valid indices are 0 … len(seq) - 1.",
             "Handle the empty case explicitly (`if not seq: ...`).",
             "Prefer iterating directly over items (`for item in seq`) to avoid index arithmetic."],
            ["Iterate over items or use enumerate() instead of manual indices.", "Validate inputs before indexing."]),
    Pattern({"python"}, r"KeyError: ['\"]?([^'\"\n]+)['\"]?", "KeyError",
            lambda c: f"The dictionary has no key `{c.m.group(1)}`.",
            lambda c: "The key is misspelled, has a different type (e.g. '1' vs 1) or was never inserted.",
            ["Print `d.keys()` before the failing line to see what is actually present.",
             "Use `d.get(key, default)` when the key may be missing.",
             "Check the key's type and spelling (including case and whitespace)."],
            ["Use dict.get() or collections.defaultdict for optional keys.", "Validate external data (JSON/API) with a schema such as Pydantic."],
            lambda c: (fix_python_keyerror(c.code, c.line, c.m.group(1)), "Replaced direct indexing with .get() on the failing line; decide whether None is an acceptable default.")),
    Pattern({"python"}, r"ZeroDivisionError", "ZeroDivisionError",
            _const("A number was divided (or taken modulo) by zero."),
            _const("The denominator evaluated to 0 — often an empty list (len() == 0), a counter that was never incremented, or unvalidated input."),
            ["Find the denominator on the reported line and print its value.",
             "Decide what the correct result is when it is zero (0, None, raise a clear error).",
             "Add a guard before dividing."],
            ["Validate inputs that are used as divisors.", "Handle empty collections explicitly before computing averages."],
            lambda c: (fix_python_division(c.code, c.line), "Added a guard before the division; adjust the zero-case behaviour to what your program needs."), "high"),
    Pattern({"python"}, r"(ModuleNotFoundError|ImportError): No module named '([\w.]+)'", "ModuleNotFoundError",
            lambda c: f"Python could not find the module `{c.m.group(2)}`.",
            lambda c: "The package is not installed in the interpreter/virtual environment that runs the code, the name is misspelled, or a local file shadows/should provide it.",
            ["Check which interpreter is running: `python -c \"import sys; print(sys.executable)\"`.",
             "Install the package into that environment: `python -m pip install <package>` (the pip name can differ from the import name, e.g. `pip install pillow` for `import PIL`).",
             "Activate your virtual environment before running.",
             "Ensure no local file is named like a library (e.g. `random.py`)."],
            ["Pin dependencies in requirements.txt / pyproject.toml.", "Always run inside a virtual environment."], None, "high"),
    Pattern({"python"}, r"(IndentationError|TabError): ([^\n]+)", "IndentationError",
            lambda c: f"Python found inconsistent indentation: {c.m.group(2)}.",
            _const("Blocks are mis-indented, or tabs and spaces are mixed."),
            ["Re-indent the block using 4 spaces per level.",
             "Make sure every line inside a block uses the same indentation.",
             "Configure your editor to insert spaces for tabs."],
            ["Use an auto-formatter (Ruff format / Black).", "Enable 'render whitespace' in your editor."],
            lambda c: (fix_python_syntax(c.code, c.line), "Re-indented the offending line so the file parses."), "high"),
    Pattern({"python"}, r"SyntaxError: ([^\n]+)", "SyntaxError",
            lambda c: f"Python could not parse the code: {c.m.group(1)}.",
            _const("A typo in the structure of the code: a missing colon, bracket, quote or comma, or a keyword used incorrectly."),
            ["Look at the reported line and the line just before it — the real mistake is often on the previous line.",
             "Check for unbalanced (), [], {} and quotes.",
             "Make sure `if/for/while/def/class` lines end with a colon."],
            ["Use an editor with syntax highlighting and bracket matching.", "Run a formatter frequently."],
            lambda c: (fix_python_syntax(c.code, c.line), "Applied a mechanical syntax repair that makes the file parse; check it matches your intent."), "high"),
    Pattern({"python"}, r"RecursionError", "RecursionError",
            _const("A function called itself (directly or indirectly) more times than Python allows (~1000 frames)."),
            _const("The recursion has no base case, the base case is never reached, or the input is too deep for recursion."),
            ["Find the recursive function and verify it has a base case that returns without recursing.",
             "Check that each recursive call moves the input closer to the base case.",
             "For deep inputs, rewrite iteratively with an explicit stack, or memoize with functools.lru_cache."],
            ["Write tests for the smallest inputs (the base cases).", "Prefer iteration for linear recursion."]),
    Pattern({"python"}, r"ValueError: invalid literal for int\(\) with base \d+: '([^']*)'", "ValueError (int conversion)",
            lambda c: f"`int()` received the text `{c.m.group(1)}`, which is not a valid integer.",
            _const("The input contains non-digit characters (spaces, decimals, empty string)."),
            ["Strip whitespace: `int(text.strip())`.", "Use `float()` for decimal values.", "Wrap conversion in try/except ValueError and re-prompt or report a clear error."],
            ["Validate user input before converting."], None, "high"),
    Pattern({"python"}, r"FileNotFoundError: \[Errno 2\] No such file or directory: '([^']+)'", "FileNotFoundError",
            lambda c: f"The file `{c.m.group(1)}` does not exist at the path being used.",
            _const("Relative paths are resolved against the current working directory, which is often not the script's folder."),
            ["Print `os.getcwd()` to see the working directory.",
             "Build paths relative to the script: `Path(__file__).parent / 'data.csv'`.",
             "Check spelling and file extension."],
            ["Use pathlib and absolute paths derived from __file__.", "Check `path.exists()` and give a clear error."], None, "high"),
    # ------------------------------ JavaScript / TypeScript
    Pattern(JS, r"ReferenceError: (\w+) is not defined", "ReferenceError",
            lambda c: f"`{c.m.group(1)}` is used but no variable, function or import with that name exists in scope.",
            lambda c: "", ["Check spelling and capitalisation.", "Make sure the variable is declared (const/let) before use and in an enclosing scope.",
                           "If it comes from a module, import it. In Node ESM, `require` and `__dirname` are not available."],
            ["Enable ESLint `no-undef`.", "Use TypeScript for compile-time name checking."], _undefined_fixer(), "high"),
    Pattern(JS, r"TypeError: Cannot read propert(?:y|ies) of (undefined|null)(?: \(reading '([^']+)'\))?", "TypeError (undefined/null access)",
            lambda c: f"The code tried to read `{c.m.group(2) or 'a property'}` from a value that is `{c.m.group(1)}`.",
            _const("An object is missing: data not loaded yet (async), a wrong property path, an API returning a different shape, or an array index past the end."),
            ["Log the object right before the failing line.", "Check whether the data is fetched asynchronously and used before it arrives.",
             "Use optional chaining (`obj?.prop`) and defaults (`?? fallback`) where absence is valid.",
             "Fix the root cause if the value should never be missing."],
            ["Validate API responses (e.g. zod).", "Enable TypeScript `strictNullChecks`."],
            lambda c: (fix_optional_chaining(c.code, c.line, c.m.group(2) or ""), "Added optional chaining on the failing access; this avoids the crash but you should still confirm why the value is missing."), "high"),
    Pattern(JS, r"TypeError: ([\w.$\[\]'\"]+) is not a function", "TypeError (not a function)",
            lambda c: f"`{c.m.group(1)}` was called like a function, but its value is not a function.",
            _const("A typo in the method name, a wrong import (default vs named), the value being undefined, or calling a method on the wrong type (e.g. .map on an object)."),
            ["Log `typeof` the value before calling it.", "Check default vs named import: `import x from` vs `import { x } from`.",
             "Check the method exists on that type (e.g. NodeList has no .map; use Array.from)."],
            ["Use TypeScript for call-site checking."], None, "high"),
    Pattern(JS, r"SyntaxError: (Unexpected token[^\n]*|Unexpected end of input|missing \) after argument list|Invalid or unexpected token|Unexpected identifier[^\n]*)", "SyntaxError",
            lambda c: f"The JavaScript parser failed: {c.m.group(1)}.",
            _const("Unbalanced brackets/quotes, a missing comma, or invalid JSON passed to JSON.parse."),
            ["Check the reported line and the one before it for missing brackets, commas or quotes.",
             "If the error came from JSON.parse, log the raw string; it may be HTML or empty."],
            ["Use Prettier/ESLint to catch syntax errors on save."], None, "medium"),
    Pattern(JS, r"RangeError: Maximum call stack size exceeded", "RangeError (stack overflow)",
            _const("A function called itself (directly or indirectly) too many times."),
            _const("Infinite recursion: a missing base case, a setter that sets itself, or a React component that updates state during render."),
            ["Inspect the stack trace for the repeating function.", "Ensure the recursion has a reachable base case.", "In React, move state updates into effects or event handlers."],
            ["Prefer iteration for deep structures."], None, "high"),
    Pattern(JS, r"UnhandledPromiseRejection|Uncaught \(in promise\)", "Unhandled promise rejection",
            _const("A promise was rejected and nothing caught the error."),
            _const("An async call failed without `await` inside try/catch or a `.catch()` handler."),
            ["Wrap awaited calls in try/catch.", "Add `.catch()` to promise chains.", "Inspect the original error message printed with the rejection."],
            ["Enable `@typescript-eslint/no-floating-promises`."]),
    Pattern({"typescript"}, r"TS2322: Type '([^']+)' is not assignable to type '([^']+)'", "TS2322 type mismatch",
            lambda c: f"A value of type `{c.m.group(1)}` was assigned where `{c.m.group(2)}` is required.",
            _const("The value's type does not match the declared type."),
            ["Check the declaration and the assigned value.", "Narrow the type (typeof/instanceof checks) or convert the value.", "Update the declared type if it is wrong."],
            ["Keep types close to data sources."], None, "high"),
    # ------------------------------ Java
    Pattern({"java"}, r"java\.lang\.NullPointerException(?:: ([^\n]+))?", "NullPointerException",
            lambda c: "The code used a reference that is null." + (f" JVM detail: {c.m.group(1)}" if c.m.group(1) else ""),
            _const("An object was never initialised, a method returned null, or a collection/map lookup returned null."),
            ["Look at the first `at` line of the stack trace that points to your code.",
             "Identify which reference on that line is null (Java 14+ helpful NPE messages name it).",
             "Initialise the field/variable, or check `if (x != null)` / use `Objects.requireNonNull(x, \"x\")`.",
             "Consider returning Optional<T> for values that can be absent."],
            ["Annotate with @Nullable/@NonNull and enable static checks.", "Initialise fields in constructors."]),
    Pattern({"java"}, r"ArrayIndexOutOfBoundsException:? (?:Index )?(-?\d+)(?: out of bounds for length (\d+))?", "ArrayIndexOutOfBoundsException",
            lambda c: f"Index {c.m.group(1)} was used on an array" + (f" of length {c.m.group(2)}." if c.m.group(2) else "."),
            _const("Loop bounds use `<=` instead of `<`, or the index is computed incorrectly."),
            ["Valid indices are 0 … length-1.", "Check loop conditions for `<= arr.length`.", "Print the index and length before the access."],
            ["Use enhanced for loops when you do not need indices."], None, "high"),
    Pattern({"java"}, r"(?:java\.lang\.)?NumberFormatException: For input string: \"([^\"]*)\"", "NumberFormatException",
            lambda c: f"`Integer.parseInt` (or similar) received `{c.m.group(1)}`, which is not a valid number.",
            _const("Input contains spaces, decimals, or is empty."),
            ["Trim the input: `s.trim()`.", "Use Double.parseDouble for decimals.", "Catch NumberFormatException and report a clear message."],
            ["Validate input before parsing."], None, "high"),
    Pattern({"java"}, r"ConcurrentModificationException", "ConcurrentModificationException",
            _const("A collection was modified while it was being iterated."),
            _const("Calling list.remove()/add() inside a for-each loop over the same list."),
            ["Use an explicit Iterator and iterator.remove().", "Or use `list.removeIf(x -> ...)`.", "Or collect changes and apply them after the loop."],
            ["Prefer streams/removeIf for filtering."], None, "high"),
    Pattern({"java"}, r"ClassCastException: (?:class )?([\w.$]+) cannot be cast to (?:class )?([\w.$]+)", "ClassCastException",
            lambda c: f"An object of type `{c.m.group(1)}` was cast to the incompatible type `{c.m.group(2)}`.",
            _const("A raw/untyped collection or a wrong assumption about an object's runtime type."),
            ["Check with `instanceof` before casting.", "Use generics so the compiler enforces types."], ["Avoid raw types."], None, "high"),
    Pattern({"java"}, r"error: cannot find symbol[\s\S]*?symbol:\s+(?:variable|method|class) (\w+)", "Compile error: cannot find symbol",
            lambda c: f"The compiler cannot find `{c.m.group(1)}`.",
            lambda c: "", ["Check spelling and capitalisation.", "Add the missing import.", "Ensure the variable is declared in scope."],
            ["Use an IDE with auto-import."], _undefined_fixer(), "high"),
    Pattern({"java"}, r"error: ';' expected", "Compile error: ';' expected",
            _const("A statement is missing its terminating semicolon."), _const("The previous statement was not terminated."),
            ["Add `;` at the end of the statement on (or just before) the reported line."], ["Let the IDE format code on save."],
            lambda c: (fix_missing_semicolon(c.code, c.line, False), "Added the missing semicolon."), "high"),
    Pattern({"java"}, r"error: missing return statement", "Compile error: missing return statement",
            _const("A non-void method has a code path that ends without returning a value."),
            _const("An if/else or switch does not return on every branch."),
            ["Add a return (or throw) at the end of the method, or in the missing branch."], ["Keep a single exit path where practical."], None, "high"),
    Pattern({"java"}, r"error: incompatible types: ([^\n]+)", "Compile error: incompatible types",
            lambda c: f"Type mismatch: {c.m.group(1)}.", _const("A value of one type is used where another is required."),
            ["Convert explicitly (e.g. Integer.parseInt, String.valueOf).", "Fix the declared type."], ["Prefer precise types."], None, "high"),
    # ------------------------------ C / C++
    Pattern(CF, r"Segmentation fault|SIGSEGV|core dumped", "Segmentation fault",
            _const("The program accessed memory it does not own."),
            _const("Dereferencing NULL or an uninitialised pointer, writing past the end of an array/buffer, using memory after free(), or stack overflow from deep recursion."),
            ["Compile with `-g -fsanitize=address,undefined` and run again; ASan prints the exact line.",
             "Or run under `gdb ./prog` then `run` and `bt` to see the call stack.",
             "Check every pointer is initialised and every array index is < size.",
             "Run `valgrind ./prog` to detect invalid reads/writes and leaks."],
            ["Always initialise pointers (to NULL) and check malloc results.", "Prefer std::vector/std::string and .at() in C++."]),
    Pattern(CF, r"undefined reference to `?'?([\w:~<>]+)", "Linker error: undefined reference",
            lambda c: f"The linker cannot find the definition of `{c.m.group(1)}`.",
            _const("The function is declared but not defined, the source file defining it is not compiled/linked, or a library flag (e.g. -lm) is missing."),
            ["Make sure the defining .c/.cpp file is part of the build command.", "Add needed libraries (e.g. `-lm` for math.h, `-pthread`).",
             "Check the signature matches between declaration and definition.", "For `main`, make sure it is spelled correctly."],
            ["Use a build system (CMake/Make)."], None, "high"),
    Pattern(CF, r"error: expected ';' (?:before|after|at end of) ([^\n]*)", "Compile error: expected ';'",
            _const("A statement or declaration is missing a semicolon."), _const("The previous line was not terminated (class/struct definitions also need `};`)."),
            ["Add `;` at the end of the line before the reported position."], ["Use clang-format."],
            lambda c: (fix_missing_semicolon(c.code, c.line, "before" in c.m.group(0)), "Added the missing semicolon."), "high"),
    Pattern(CF, r"(?:'(\w+)' undeclared|use of undeclared identifier '(\w+)'|'(\w+)' was not declared in this scope)", "Compile error: undeclared identifier",
            lambda c: f"`{c.m.group(1) or c.m.group(2) or c.m.group(3)}` is used without being declared.",
            lambda c: "", ["Check spelling.", "Declare the variable before use.", "Include the header that declares it (e.g. <stdio.h>, <string.h>, <vector>).", "In C++, qualify std names (std::cout)."],
            ["Enable -Wall -Wextra."],
            lambda c: fix_undefined_name(c.m.group(1) or c.m.group(2) or c.m.group(3), c.code, c.language, c.line), "high"),
    Pattern(CF, r"implicit declaration of function '(\w+)'", "Implicit function declaration",
            lambda c: f"`{c.m.group(1)}` was called before any declaration was seen.",
            _const("A missing #include, or the function is defined after it is used without a prototype."),
            ["Include the right header (e.g. <stdlib.h> for malloc, <string.h> for strlen).", "Add a prototype above the call or move the definition up."],
            ["Compile with -Werror=implicit-function-declaration."], None, "high"),
    # ------------------------------ Go
    Pattern({"go"}, r"invalid memory address or nil pointer dereference", "nil pointer dereference",
            _const("A nil pointer, map, or interface was dereferenced."),
            _const("A function returned (nil, err) and the error was ignored, or a struct pointer/map was never initialised."),
            ["Find the first frame in your code in the goroutine trace.", "Check the error returned just before the value was created.",
             "Initialise maps with make() and pointers with &T{}."],
            ["Always check `if err != nil` before using the other return values."], None, "high"),
    Pattern({"go"}, r"index out of range \[(\d+)\] with length (\d+)", "index out of range",
            lambda c: f"Index {c.m.group(1)} was used on a slice of length {c.m.group(2)}.",
            _const("Loop bounds or index calculation are off by one, or the slice is shorter than assumed."),
            ["Valid indices are 0 … len-1.", "Use `for i, v := range s` instead of manual indices.", "Check `len(s)` before indexing."],
            ["Validate input lengths."], None, "high"),
    Pattern({"go"}, r"all goroutines are asleep - deadlock", "deadlock",
            _const("Every goroutine is blocked, so the program can never make progress."),
            _const("Sending on an unbuffered channel with no receiver, receiving on a channel nobody writes to/closes, or WaitGroup counts that never reach zero."),
            ["Check every channel send has a matching receiver running concurrently.", "close() channels that are ranged over.", "Match wg.Add/wg.Done calls."],
            ["Run with `-race` and keep channel ownership clear."], None, "high"),
    Pattern({"go"}, r"\"([\w./-]+)\" imported and not used|imported and not used: \"([\w./-]+)\"", "Compile error: unused import",
            lambda c: f"The package `{c.m.group(1) or c.m.group(2)}` is imported but not used. Go treats this as an error.",
            _const("Leftover import after refactoring."), ["Remove the import, or use goimports to manage imports automatically."], ["Run goimports on save."],
            lambda c: (fix_go_unused_import(c.code, c.m.group(1) or c.m.group(2)), "Removed the unused import."), "high"),
    Pattern({"go"}, r"(?:declared and not used: (\w+)|(\w+) declared (?:and|but) not used)", "Compile error: unused variable",
            lambda c: f"`{c.m.group(1) or c.m.group(2)}` is declared but never used. Go treats this as an error.",
            _const("A leftover variable, or a value that was meant to be used later."),
            ["Use the variable, remove it, or assign to `_` if you only need side effects."], ["Keep functions short so unused values are obvious."], None, "high"),
    Pattern({"go"}, r"undefined: (\w+)", "Compile error: undefined",
            lambda c: f"`{c.m.group(1)}` is not defined in this package.", lambda c: "",
            ["Check spelling and capitalisation (exported names start with a capital letter).", "Import the package that defines it.", "Make sure all package files are included in the build."],
            ["Use gopls in your editor."], _undefined_fixer(), "high"),
    # ------------------------------ generic
    Pattern(ALL, r"(?:timed? ?out|ETIMEDOUT|ECONNREFUSED|Connection refused)", "Connection / timeout error",
            _const("A network or database connection could not be established in time."),
            _const("The service is not running, the host/port is wrong, a firewall blocks it, or credentials/URL are misconfigured."),
            ["Confirm the service is running and reachable (ping/telnet/curl).", "Check host, port and protocol in configuration.", "Add timeouts and retries with backoff."],
            ["Externalise connection settings into environment variables."]),
    Pattern(ALL, r"(?:Permission denied|EACCES|Access is denied)", "Permission denied",
            _const("The process lacks permission for a file, port or resource."),
            _const("File permissions, a privileged port (<1024), or a file locked by another process."),
            ["Check the file/dir permissions and the user running the process.", "Use a port above 1024 for development.", "Close other programs that hold the file."],
            ["Run with least privilege; do not use sudo/admin as a workaround."]),
]


def _static_hints(code: str, language: str, line: int | None) -> list[str]:
    try:
        res, _, _ = run_static_analysis(code, language, None, ["bug", "security"])
    except Exception:  # analysis must never break debugging
        return []
    hints = []
    for f in res.findings:
        if f.line and (line is None or abs(f.line - line) <= 3) and f.severity in ("critical", "high", "medium"):
            hints.append(f"Line {f.line}: {f.title} — {f.description}")
    return hints[:5]


def local_debug(inp: DebugIn) -> dict[str, Any]:
    code, lang, err = inp.code, inp.language, inp.error_message
    lines = code.splitlines()
    line = extract_line(err, lang, len(lines))
    hints = _static_hints(code, lang, line)

    chosen: Pattern | None = None
    match: re.Match | None = None
    for p in PATTERNS:
        if lang in p.langs:
            m = p.compiled.search(err)
            if m:
                chosen, match = p, m
                break

    location = None
    if line:
        start, end = max(1, line - 2), min(len(lines), line + 2)
        location = {"line": line, "code": lines[line - 1], "context": "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))}

    if chosen and match:
        c = Ctx(code, lang, err, line, match)
        explanation = chosen.explain(c)
        cause = chosen.cause(c)
        fixed, fix_note = (None, None)
        if chosen.fixer:
            try:
                fixed, fix_note = chosen.fixer(c)
            except Exception:
                fixed, fix_note = None, None
        if not cause:
            cause = fix_note or "The name is not defined in the visible code."
        elif fix_note and fixed:
            cause += f" Suggested change: {fix_note}"
        steps = list(chosen.steps)
        if line:
            steps.insert(0, f"Go to line {line}: `{lines[line - 1].strip()[:120]}`.")
        if hints:
            cause += "\n\nStatic analysis also flagged nearby code:\n- " + "\n- ".join(hints)
        return {
            "error_type": chosen.error_type, "explanation": explanation, "root_cause": cause, "location": location,
            "steps": steps, "suggested_code": fixed if fixed and fixed != code else None,
            "prevention_tips": chosen.prevent, "confidence": chosen.confidence if line or fixed else "medium",
        }

    first = next((ln.strip() for ln in reversed(err.strip().splitlines()) if ln.strip()), err.strip())[:300]
    cause = "This error does not match a known pattern in the local knowledge base."
    if hints:
        cause += " Static analysis flagged code that may be related:\n- " + "\n- ".join(hints)
    steps = [
        f"Read the last line of the error carefully: `{first}`.",
        "Find the first stack-trace frame that points to your own code and open that line.",
        "Reproduce the failure with the smallest input possible.",
        "Print or inspect the values of the variables used on that line just before it runs.",
        "Check recent changes to that area of the code.",
    ]
    if line:
        steps.insert(1, f"The error references line {line}: `{lines[line - 1].strip()[:120]}`.")
    return {
        "error_type": re.split(r"[:\n]", first)[0][:80] or "Unknown error",
        "explanation": f"The program reported: {first}", "root_cause": cause, "location": location, "steps": steps,
        "suggested_code": None, "prevention_tips": ["Add tests for this scenario once fixed.", "Log inputs and context around failure points."],
        "confidence": "low",
    }


AI_DEBUG_SYSTEM = """You are an expert debugging assistant. Given code, an error message and optional context, diagnose the problem precisely.
Return JSON:
{"error_type": "short name", "explanation": "what the error means in plain language",
 "root_cause": "the most probable root cause in THIS code", "line": <int or null>,
 "steps": ["ordered debugging/fix steps"], "suggested_code": "full corrected code",
 "prevention_tips": ["tips"], "confidence": "high|medium|low"}"""


def run_debug(inp: DebugIn, allow_ai: bool) -> dict[str, Any]:
    base = local_debug(inp)
    out = {**base, "language": inp.language, "ai_used": False, "ai_error": None, "created_at": datetime.now(timezone.utc)}
    if not allow_ai:
        return out
    user = (f"Language: {LANGUAGE_LABEL[inp.language]}\nError message:\n{inp.error_message[:6000]}\n\n"
            f"Additional context: {inp.context[:2000] or 'none'}\n\nCode:\n```{inp.language}\n{ai.clip_code(inp.code)}\n```")
    try:
        d = ai.chat_json(AI_DEBUG_SYSTEM, user, max_tokens=3500)
    except ai.AIError as exc:
        out["ai_error"] = str(exc)
        return out
    lines = inp.code.splitlines()
    line = ai.as_int(d.get("line"))
    location = base["location"]
    if line and line <= len(lines):
        location = {"line": line, "code": lines[line - 1],
                    "context": "\n".join(f"{n}: {lines[n - 1]}" for n in range(max(1, line - 2), min(len(lines), line + 2) + 1))}
    conf = str(d.get("confidence", "medium")).lower()
    out.update({
        "error_type": ai.as_str(d.get("error_type"), base["error_type"], 120),
        "explanation": ai.as_str(d.get("explanation"), base["explanation"], 5000),
        "root_cause": ai.as_str(d.get("root_cause"), base["root_cause"], 5000),
        "location": location,
        "steps": ai.as_str_list(d.get("steps")) or base["steps"],
        "suggested_code": ai.as_str(d.get("suggested_code"), "", 100_000).strip() or base["suggested_code"],
        "prevention_tips": ai.as_str_list(d.get("prevention_tips")) or base["prevention_tips"],
        "confidence": conf if conf in ("high", "medium", "low") else "medium",
        "ai_used": True,
    })
    return out
