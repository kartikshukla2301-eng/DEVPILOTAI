"""Python analyzer: AST rules + Ruff (lint) + Bandit (security) + Radon (complexity)."""
from __future__ import annotations

import ast
import builtins
import re

from app.analyzers import tools
from app.analyzers.base import AnalysisContext, AnalyzerResult, FindingCollector, duplicate_blocks, scan_secrets

BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__builtins__", "__spec__", "__package__", "__loader__", "__path__", "__class__"}

LOOP_TYPES = (ast.For, ast.AsyncFor, ast.While)
COMPOUND = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Match) if hasattr(ast, "Match") else (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
SQL_RE = re.compile(r"(?i)\b(select\s.+\sfrom|insert\s+into|update\s+\w+\s+set|delete\s+from|drop\s+table|create\s+table)\b")


# ---------------------------------------------------------------------------
# Ruff / Bandit mapping
# ---------------------------------------------------------------------------
def _ruff_classify(code: str) -> tuple[str, str]:
    if code.startswith("E9") or code in {"F821", "F822", "F823", "F631", "F632", "F633", "F701", "F702", "F704", "F706", "F707"}:
        return "bug", "high"
    if code in {"F401", "F841", "F811", "B007", "E741", "PLW0120"}:
        return ("bug", "medium") if code == "F811" else ("quality", "low")
    if code.startswith("F5") or code.startswith("F6"):
        return "bug", "medium"
    if code == "E722" or code in {"B006", "B008", "B023", "B020", "B015", "B018", "B024", "B026", "B012"}:
        return "bug", "medium"
    if code.startswith("B"):
        return ("quality", "low") if code in {"B904", "B905", "B009", "B010", "B011"} else ("bug", "low")
    if code.startswith("PERF"):
        return "performance", "low"
    if code.startswith("PLW2901"):
        return "bug", "low"
    if code.startswith(("UP", "ERA", "E731", "PIE", "C4")):
        return "quality", "info"
    if code.startswith("F"):
        return "bug", "low"
    return "quality", "low"


RUFF_ADVICE = {
    "F401": "Remove the unused import, or re-export it explicitly via __all__ if it is part of the public API.",
    "F841": "Remove the assignment or use the value. If it is intentionally unused, name it `_`.",
    "F821": "Define the name before use, fix the spelling, or add the missing import.",
    "F811": "Rename one of the definitions; the later one silently replaces the earlier one.",
    "E722": "Catch specific exceptions (e.g. `except ValueError:`). A bare except also traps KeyboardInterrupt and SystemExit.",
    "E711": "Compare to None with `is None` / `is not None`.",
    "E712": "Use the value directly (`if flag:`) instead of comparing with True/False.",
    "E721": "Use `isinstance(obj, T)` instead of comparing types.",
    "B006": "Use `None` as the default and create the mutable object inside the function body.",
    "B008": "Move the call out of the default argument; defaults are evaluated once at definition time.",
    "B007": "Rename the unused loop variable to `_`.",
    "B023": "Bind the loop variable via a default argument (`lambda x=x: ...`) to capture its current value.",
    "B904": "Use `raise ... from err` to preserve the original traceback.",
    "PERF401": "Use a list comprehension instead of appending in a loop.",
    "PERF203": "Move the try/except outside the loop when possible; it adds overhead per iteration.",
    "PERF102": "Iterate `.values()` or `.keys()` directly when you only need one of them.",
    "SIM108": "Use a conditional expression to simplify the assignment.",
    "ERA001": "Delete commented-out code; version control preserves history.",
}

RUFF_SKIP = {"SIM105"}  # try/except/pass is reported by py-swallowed-exception

BANDIT_ADVICE = {
    "B102": "Avoid exec(). Use explicit dispatch (a dict of functions) or a safe parser.",
    "B307": "Avoid eval(). Use ast.literal_eval() for literals, json.loads() for data, or explicit parsing.",
    "B301": "Never unpickle untrusted data. Use JSON or a schema-validated format instead.",
    "B302": "Never unmarshal untrusted data. Use JSON or a schema-validated format instead.",
    "B403": "Only use pickle on trusted data; prefer JSON for data exchange.",
    "B303": "Use hashlib.sha256() or stronger. For passwords use bcrypt, scrypt or argon2.",
    "B324": "Use hashlib.sha256() or stronger, or pass usedforsecurity=False for non-security checksums.",
    "B311": "Use the `secrets` module (secrets.token_urlsafe, secrets.randbelow) for security-sensitive values.",
    "B105": "Load the secret from an environment variable or secrets manager.",
    "B106": "Load the secret from an environment variable or secrets manager.",
    "B107": "Avoid hardcoded default passwords; require them from configuration.",
    "B108": "Use tempfile.mkstemp() / TemporaryDirectory() instead of fixed /tmp paths.",
    "B201": "Never run Flask with debug=True in production; it enables remote code execution via the debugger.",
    "B501": "Keep TLS certificate verification enabled (verify=True).",
    "B506": "Use yaml.safe_load() instead of yaml.load().",
    "B602": "Avoid shell=True. Pass arguments as a list: subprocess.run(['cmd', arg]).",
    "B603": "Validate any untrusted input passed to subprocess and use absolute executable paths.",
    "B604": "Avoid shell=True. Pass arguments as a list.",
    "B605": "Replace os.system() with subprocess.run([...]) without a shell.",
    "B607": "Use the absolute path of the executable to avoid PATH hijacking.",
    "B608": "Use parameterized queries (cursor.execute(sql, params)) instead of string formatting.",
    "B104": "Bind to a specific interface (e.g. 127.0.0.1) unless public exposure is intended.",
    "B113": "Always pass a timeout to HTTP requests to avoid hanging forever.",
    "B110": "Log or handle the exception instead of silently passing.",
}


class _Visitor(ast.NodeVisitor):
    def __init__(self, col: FindingCollector, ctx: AnalysisContext, fallback_lint: bool, fallback_sec: bool):
        self.col = col
        self.ctx = ctx
        self.fallback_lint = fallback_lint
        self.fallback_sec = fallback_sec
        self.loop_depth = 0
        self.max_loop_depth_reported: set[int] = set()
        self.func_stack: list[ast.AST] = []
        self.nesting = 0
        self.max_nesting = 0
        self.functions = 0
        self.classes = 0
        self.string_vars: set[str] = set()
        self.list_vars: set[str] = set()
        self.imported: dict[str, int] = {}
        self.loaded: set[str] = set()
        self.defined: set[str] = set(BUILTINS)
        self.with_lines: set[int] = set()

    # -- generic nesting tracking
    def generic_visit(self, node: ast.AST) -> None:
        compound = isinstance(node, COMPOUND)
        if compound:
            self.nesting += 1
            if self.nesting > self.max_nesting:
                self.max_nesting = self.nesting
            if self.nesting == 5 and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.col.add("quality", "medium", "Deeply nested code",
                             "Code is nested five or more blocks deep, which makes it hard to read and test.",
                             "Use guard clauses (early return/continue) or extract the inner block into a helper function.",
                             node.lineno, rule="deep-nesting")
        super().generic_visit(node)
        if compound:
            self.nesting -= 1

    # -- definitions
    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            name = (a.asname or a.name).split(".")[0]
            self.imported.setdefault(name, node.lineno)
            self.defined.add(name)
            if self.fallback_sec and a.name in ("pickle", "cPickle", "marshal", "shelve"):
                self.col.add("security", "low", f"Import of {a.name}",
                             f"The {a.name} module can execute arbitrary code when loading untrusted data.",
                             BANDIT_ADVICE["B403"], node.lineno, rule="py-pickle-import")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for a in node.names:
            if a.name == "*":
                self.col.add("quality", "low", "Wildcard import",
                             f"`from {node.module} import *` pollutes the namespace and hides where names come from.",
                             "Import the specific names you need.", node.lineno, rule="py-star-import")
                continue
            name = a.asname or a.name
            self.imported.setdefault(name, node.lineno)
            self.defined.add(name)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.functions += 1
        self.defined.add(node.name)
        args = node.args
        for a in args.posonlyargs + args.args + args.kwonlyargs:
            self.defined.add(a.arg)
        if args.vararg:
            self.defined.add(args.vararg.arg)
        if args.kwarg:
            self.defined.add(args.kwarg.arg)

        if self.fallback_lint:
            for d in args.defaults + [d for d in args.kw_defaults if d is not None]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)) or (
                    isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id in ("list", "dict", "set")
                ):
                    self.col.add("bug", "medium", "Mutable default argument",
                                 f"`{node.name}` uses a mutable default. It is created once and shared across calls, so changes leak between calls.",
                                 RUFF_ADVICE["B006"], d.lineno, rule="B006")
            if not re.fullmatch(r"_{0,2}[a-z][a-z0-9_]*_{0,2}", node.name) and not node.name.startswith("test"):
                self.col.add("quality", "low", "Function name is not snake_case",
                             f"PEP 8 recommends snake_case for function names; `{node.name}` does not follow it.",
                             "Rename the function using lowercase words separated by underscores.", node.lineno, rule="N802")

        end = getattr(node, "end_lineno", node.lineno) or node.lineno
        length = end - node.lineno + 1
        if length > 60:
            self.col.add("quality", "low", "Long function",
                         f"`{node.name}` spans {length} lines. Long functions usually do several things and are harder to test.",
                         "Split it into smaller functions with a single responsibility each.", node.lineno, rule="long-function")
        if len(args.args) + len(args.kwonlyargs) + len(args.posonlyargs) > 6:
            self.col.add("quality", "low", "Too many parameters",
                         f"`{node.name}` takes {len(args.args) + len(args.kwonlyargs)} parameters.",
                         "Group related parameters into a dataclass or config object.", node.lineno, rule="too-many-params")

        # recursion without an obvious base case
        calls_self = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == node.name for n in ast.walk(node)
        )
        if calls_self:
            has_branch = any(isinstance(n, (ast.If, ast.IfExp, ast.Match if hasattr(ast, "Match") else ast.If)) for n in ast.walk(node))
            if not has_branch:
                self.col.add("bug", "high", "Recursion without a base case",
                             f"`{node.name}` calls itself but contains no conditional, so it will recurse until RecursionError.",
                             "Add a base case that returns without recursing.", node.lineno, rule="py-unbounded-recursion")

        # unreachable statements after return/raise
        self._check_unreachable(node.body)

        self.func_stack.append(node)
        saved_loop = self.loop_depth
        self.loop_depth = 0
        self.generic_visit(node)
        self.loop_depth = saved_loop
        self.func_stack.pop()

    visit_FunctionDef = _check_function
    visit_AsyncFunctionDef = _check_function

    def _check_unreachable(self, body: list[ast.stmt]) -> None:
        for i, stmt in enumerate(body[:-1]):
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                nxt = body[i + 1]
                self.col.add("quality", "low", "Unreachable code",
                             f"Code after `{type(stmt).__name__.lower()}` on line {stmt.lineno} can never run.",
                             "Remove the dead code or fix the control flow.", nxt.lineno, rule="py-unreachable")
                break

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes += 1
        self.defined.add(node.name)
        if self.fallback_lint and not re.fullmatch(r"_?[A-Z][A-Za-z0-9]*", node.name):
            self.col.add("quality", "low", "Class name is not PascalCase",
                         f"PEP 8 recommends CapWords for class names; `{node.name}` does not follow it.",
                         "Rename the class using CapitalizedWords.", node.lineno, rule="N801")
        self.generic_visit(node)

    # -- names
    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.loaded.add(node.id)
        else:
            self.defined.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        root = node
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            self.loaded.add(root.id)
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.defined.update(node.names)
        self.col.add("quality", "low", "Use of global statement",
                     "Mutating module-level state from functions creates hidden coupling and makes testing harder.",
                     "Pass values as parameters and return results, or encapsulate state in a class.", node.lineno, rule="py-global")

    def visit_Assign(self, node: ast.Assign) -> None:
        for t in node.targets:
            if isinstance(t, ast.Name):
                if isinstance(node.value, (ast.JoinedStr,)) or (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                    self.string_vars.add(t.id)
                if isinstance(node.value, ast.List) or (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "list"):
                    self.list_vars.add(t.id)
                if isinstance(node.value, ast.Name) and node.value.id == t.id:
                    self.col.add("bug", "low", "Self-assignment",
                                 f"`{t.id} = {t.id}` has no effect.", "Remove the statement or assign the intended value.",
                                 node.lineno, rule="py-self-assign")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if self.loop_depth and isinstance(node.op, ast.Add) and isinstance(node.target, ast.Name):
            v = node.value
            is_str = node.target.id in self.string_vars or isinstance(v, ast.JoinedStr) or (
                isinstance(v, ast.Constant) and isinstance(v.value, str))
            if is_str:
                self.col.add("performance", "medium", "String concatenation inside a loop",
                             f"`{node.target.id} += ...` inside a loop creates a new string on every iteration, which can be quadratic.",
                             "Collect the pieces in a list and call `''.join(parts)` once after the loop.",
                             node.lineno, rule="py-str-concat-loop")
        self.generic_visit(node)

    # -- loops
    def _visit_loop(self, node: ast.For | ast.AsyncFor | ast.While) -> None:
        self.loop_depth += 1
        if self.loop_depth >= 3 and node.lineno not in self.max_loop_depth_reported:
            self.max_loop_depth_reported.add(node.lineno)
            self.col.add("performance", "medium", "Deeply nested loops",
                         f"Loop nested {self.loop_depth} levels deep; runtime grows roughly as O(n^{self.loop_depth}).",
                         "Precompute lookups in a dict/set, or restructure the algorithm to avoid the inner loops.",
                         node.lineno, rule="py-nested-loops")
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) \
                and node.iter.func.id == "range" and len(node.iter.args) == 1:
            arg = node.iter.args[0]
            if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "len":
                self.col.add("quality", "info", "range(len(...)) iteration",
                             "Iterating over indices is less readable than iterating over items.",
                             "Use `for item in seq:` or `for i, item in enumerate(seq):`.", node.lineno, rule="py-range-len")
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            has_exit = any(isinstance(n, (ast.Break, ast.Return, ast.Raise)) for n in ast.walk(node)) or any(
                isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
                and getattr(n.func, "id", getattr(n.func, "attr", "")) in ("exit", "_exit") for n in ast.walk(node))
            if not has_exit:
                self.col.add("bug", "medium", "Infinite loop",
                             "`while True` has no break, return or raise, so it can never terminate normally.",
                             "Add an exit condition or a break statement.", node.lineno, rule="py-infinite-loop")
        self._check_unreachable(node.body)
        self.generic_visit(node)
        self.loop_depth -= 1

    visit_For = _visit_loop
    visit_AsyncFor = _visit_loop
    visit_While = _visit_loop

    def visit_Compare(self, node: ast.Compare) -> None:
        if self.loop_depth:
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)) and (
                    isinstance(comp, ast.List) or (isinstance(comp, ast.Name) and comp.id in self.list_vars)
                ):
                    self.col.add("performance", "low", "Membership test on a list inside a loop",
                                 "`x in list` is O(n). Inside a loop this becomes O(n*m).",
                                 "Convert the list to a set once before the loop for O(1) lookups.", node.lineno, rule="py-list-membership")
        if self.fallback_lint:
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(comp, ast.Constant) and comp.value is None:
                    self.col.add("quality", "low", "Comparison to None with ==", "`== None` can be overridden by __eq__.",
                                 RUFF_ADVICE["E711"], node.lineno, rule="E711")
        self.generic_visit(node)

    # -- exceptions
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None and self.fallback_lint:
            self.col.add("bug", "medium", "Bare except clause",
                         "A bare `except:` catches everything, including KeyboardInterrupt and SystemExit.",
                         RUFF_ADVICE["E722"], node.lineno, rule="E722")
        if len(node.body) == 1 and isinstance(node.body[0], (ast.Pass,)) or (
            len(node.body) == 1 and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
            and node.body[0].value.value is Ellipsis
        ):
            self.col.add("bug", "medium", "Exception silently swallowed",
                         "The handler does nothing, so failures disappear without a trace and bugs become hard to diagnose.",
                         "Log the exception, handle it meaningfully, or let it propagate.", node.lineno, rule="py-swallowed-exception")
        if node.name:
            self.defined.add(node.name)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                for n in ast.walk(item.optional_vars):
                    if isinstance(n, ast.Name):
                        self.defined.add(n.id)
        self.generic_visit(node)

    visit_AsyncWith = visit_With

    # -- calls
    def visit_Call(self, node: ast.Call) -> None:
        fname = ""
        if isinstance(node.func, ast.Name):
            fname = node.func.id
        elif isinstance(node.func, ast.Attribute):
            base = node.func.value
            prefix = base.id + "." if isinstance(base, ast.Name) else ""
            fname = prefix + node.func.attr
        attr = fname.rsplit(".", 1)[-1]

        # SQL injection via string building passed to execute()
        if attr in ("execute", "executemany", "executescript", "raw", "read_sql", "read_sql_query") and node.args:
            q = node.args[0]
            dynamic = isinstance(q, ast.JoinedStr) or (isinstance(q, ast.BinOp) and isinstance(q.op, (ast.Add, ast.Mod))) or (
                isinstance(q, ast.Call) and isinstance(q.func, ast.Attribute) and q.func.attr == "format")
            if dynamic:
                text = ast.get_source_segment(self.ctx.code, q) or ""
                if SQL_RE.search(text) or isinstance(q, ast.JoinedStr):
                    self.col.add("security", "high", "Possible SQL injection",
                                 "The SQL statement is built with string formatting/concatenation and passed to execute(). If any part comes from user input, an attacker can alter the query.",
                                 BANDIT_ADVICE["B608"] + " Example: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
                                 node.lineno, rule="py-sql-injection")
            if self.loop_depth:
                self.col.add("performance", "medium", "Database query inside a loop",
                             "Running a query per iteration (the N+1 pattern) multiplies round-trips to the database.",
                             "Fetch all needed rows in one query (WHERE id IN (...)) or use executemany().", node.lineno, rule="py-query-in-loop")

        if self.loop_depth:
            if fname in ("re.compile", "re.match", "re.search", "re.findall", "re.sub") and node.args and isinstance(node.args[0], ast.Constant):
                if fname == "re.compile":
                    self.col.add("performance", "low", "Regex compiled inside a loop",
                                 "The pattern is recompiled every iteration (the cache helps but has overhead and a size limit).",
                                 "Compile the pattern once at module level and reuse it.", node.lineno, rule="py-regex-loop")
            if attr in ("sort",) or fname == "sorted":
                self.col.add("performance", "medium", "Sorting inside a loop",
                             "Sorting on every iteration costs O(n log n) each time.",
                             "Sort once outside the loop, or use heapq / bisect to maintain order incrementally.", node.lineno, rule="py-sort-loop")
            if attr == "insert" and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0:
                self.col.add("performance", "medium", "list.insert(0, ...) inside a loop",
                             "Inserting at the front of a list shifts every element: O(n) per insert.",
                             "Use collections.deque and appendleft(), or append and reverse once at the end.", node.lineno, rule="py-insert-front")
            if fname in ("copy.deepcopy", "deepcopy"):
                self.col.add("performance", "low", "deepcopy inside a loop",
                             "copy.deepcopy is slow; calling it repeatedly can dominate runtime.",
                             "Copy once outside the loop or copy only the fields you modify.", node.lineno, rule="py-deepcopy-loop")

        if fname == "open" and not self._inside_with(node):
            self.col.add("bug", "low", "File opened without a context manager",
                         "If an exception occurs before close(), the file handle leaks.",
                         "Use `with open(path) as fh:` so the file is always closed.", node.lineno, rule="py-open-no-with")

        if self.fallback_sec:
            self._security_call(node, fname, attr)
        self.generic_visit(node)

    def _inside_with(self, node: ast.AST) -> bool:
        return node.lineno in self.with_lines

    def _security_call(self, node: ast.Call, fname: str, attr: str) -> None:
        add = self.col.add
        if fname in ("eval", "exec"):
            add("security", "high", f"Use of {fname}()", f"{fname}() runs arbitrary code; with user-controlled input this is remote code execution.",
                BANDIT_ADVICE["B307" if fname == "eval" else "B102"], node.lineno, rule="B307" if fname == "eval" else "B102")
        elif fname in ("pickle.loads", "pickle.load", "cPickle.loads", "marshal.loads", "shelve.open"):
            add("security", "high", "Unsafe deserialization", "Unpickling data can execute arbitrary code if the data is attacker-controlled.",
                BANDIT_ADVICE["B301"], node.lineno, rule="B301")
        elif fname == "yaml.load" and not any(k.arg == "Loader" for k in node.keywords):
            add("security", "high", "yaml.load without a safe Loader", "yaml.load can construct arbitrary Python objects.",
                BANDIT_ADVICE["B506"], node.lineno, rule="B506")
        elif fname in ("os.system", "os.popen"):
            add("security", "high", f"Shell command via {fname}", "Commands run through the shell are vulnerable to injection.",
                BANDIT_ADVICE["B605"], node.lineno, rule="B605")
        elif fname.startswith("subprocess.") and any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords):
            add("security", "high", "subprocess with shell=True", "shell=True passes the command through the shell, enabling injection.",
                BANDIT_ADVICE["B602"], node.lineno, rule="B602")
        elif fname in ("hashlib.md5", "hashlib.sha1"):
            add("security", "medium", "Weak hash algorithm", f"{fname} is broken for security purposes (collisions are practical).",
                BANDIT_ADVICE["B324"], node.lineno, rule="B324")
        elif fname.startswith("random.") and attr in ("random", "randint", "choice", "randrange", "getrandbits"):
            add("security", "low", "Non-cryptographic random generator", "The `random` module is predictable and unsuitable for tokens or passwords.",
                BANDIT_ADVICE["B311"], node.lineno, rule="B311")
        elif fname == "tempfile.mktemp":
            add("security", "medium", "Insecure temporary file", "mktemp() is race-prone.", BANDIT_ADVICE["B108"], node.lineno, rule="B306")
        if any(k.arg == "verify" and isinstance(k.value, ast.Constant) and k.value.value is False for k in node.keywords):
            add("security", "high", "TLS verification disabled", "verify=False allows man-in-the-middle attacks.",
                BANDIT_ADVICE["B501"], node.lineno, rule="B501")


def _with_call_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.With, ast.AsyncWith)):
            for item in n.items:
                for sub in ast.walk(item.context_expr):
                    if hasattr(sub, "lineno"):
                        lines.add(sub.lineno)
        # `return open(...)` / passing to a function is ownership transfer; don't flag
        if isinstance(n, (ast.Return,)) and n.value is not None:
            for sub in ast.walk(n.value):
                if hasattr(sub, "lineno"):
                    lines.add(sub.lineno)
    return lines


def analyze_python(ctx: AnalysisContext) -> AnalyzerResult:
    res = AnalyzerResult()
    col = FindingCollector(ctx)
    res.tools_used.append("python-ast")

    try:
        tree = ast.parse(ctx.code, filename=ctx.filename)
    except SyntaxError as e:
        col.ctx.categories = col.ctx.categories | {"bug"}
        col.add("bug", "critical", f"Syntax error: {e.msg}",
                f"Python could not parse the file: {e.msg}. No further analysis is possible until this is fixed.",
                "Fix the syntax at the indicated location. Common causes: missing colon, unbalanced brackets, wrong indentation.",
                e.lineno, column=e.offset, rule="syntax-error", tool="python-ast")
        res.findings = col.items
        return res

    ruff_results = tools.ruff_check(ctx.code) if ({"bug", "quality", "performance"} & ctx.categories) else []
    bandit_results = tools.bandit_check(ctx.code) if "security" in ctx.categories else []
    if ruff_results is not None and ({"bug", "quality", "performance"} & ctx.categories):
        res.tools_used.append("ruff")
    if bandit_results is not None and "security" in ctx.categories:
        res.tools_used.append("bandit")

    visitor = _Visitor(col, ctx, fallback_lint=ruff_results is None, fallback_sec=bandit_results is None)
    visitor.with_lines = _with_call_lines(tree)
    visitor.visit(tree)
    res.functions, res.classes, res.max_nesting = visitor.functions, visitor.classes, visitor.max_nesting

    if ruff_results is None:
        # fallback: unused imports (very conservative)
        for name, line in visitor.imported.items():
            if name not in visitor.loaded and f"'{name}'" not in ctx.code and f'"{name}"' not in ctx.code:
                col.add("quality", "low", f"Unused import `{name}`", f"`{name}` is imported but never used.",
                        RUFF_ADVICE["F401"], line, rule="F401")

    for r in ruff_results or []:
        code = r.get("code") or "E999"
        if code in RUFF_SKIP:
            continue
        cat, sev = _ruff_classify(code)
        loc = r.get("location") or {}
        fix = (r.get("fix") or {}).get("message")
        advice = RUFF_ADVICE.get(code) or fix or "See the linked rule documentation for the recommended fix."
        col.add(cat, sev, r.get("message", code).split("\n")[0][:160],
                f"{r.get('message', '')} (Ruff rule {code}).", advice,
                loc.get("row"), column=loc.get("column"), rule=code, tool="ruff")

    bandit_lines: set[int] = set()
    for b in bandit_results or []:
        tid = b.get("test_id", "")
        if tid == "B101":
            continue  # assert usage is normal outside production hardening
        sev = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}.get(b.get("issue_severity", "LOW"), "low")
        if b.get("issue_confidence") == "LOW" and sev != "high":
            sev = "info"
        if tid in ("B102", "B307", "B301", "B602", "B605") and b.get("issue_confidence") == "HIGH":
            sev = "high"
        if tid == "B110":
            continue  # covered by py-swallowed-exception
        if tid in ("B105", "B106", "B107"):
            sev = "high"
        ln = b.get("line_number")
        bandit_lines.add(ln)
        title = b.get("test_name", tid).replace("_", " ").capitalize()
        if title.lower() == "blacklist":
            title = (b.get("issue_text") or tid).split(".")[0][:120]
        col.add("security", sev, title,
                f"{b.get('issue_text', '')} (Bandit {tid}, confidence {b.get('issue_confidence', '?').lower()}).",
                BANDIT_ADVICE.get(tid, "Review the flagged code; see " + b.get("more_info", "the Bandit docs") + "."),
                ln, rule=tid, tool="bandit")

    if "security" in ctx.categories:
        before = len(col.items)
        scan_secrets(col, ctx.lines)
        # drop secret findings on lines bandit already reported
        col.items = col.items[:before] + [f for f in col.items[before:] if f.line not in bandit_lines]
        # drop our SQL finding where bandit already found it
        col.items = [f for f in col.items if not (f.rule == "py-sql-injection" and f.line in bandit_lines)]

    # complexity
    cc = tools.radon_complexity(ctx.code)
    if cc is not None:
        res.tools_used.append("radon")
        if cc:
            res.max_complexity = max(c for _, _, c in cc)
            res.avg_complexity = round(sum(c for _, _, c in cc) / len(cc), 2)
        for name, line, c in cc:
            if c > 10:
                col.add("quality", "high" if c > 20 else "medium", f"High cyclomatic complexity in `{name}`",
                        f"`{name}` has a cyclomatic complexity of {c} (above 10 is hard to test; above 20 is very risky).",
                        "Break the function into smaller pieces, replace conditional chains with lookup tables or polymorphism.",
                        line, rule="complexity", tool="radon")

    if "quality" in ctx.categories:
        for first, dup in duplicate_blocks(ctx.lines):
            col.add("quality", "low", "Duplicated code block",
                    f"Lines starting at {dup} repeat a block that first appears at line {first}.",
                    "Extract the shared logic into a function and call it from both places.", dup, rule="duplicate-code")

    res.findings = col.items
    if tools.tool_available("ruff"):
        fixed = tools.ruff_fix(ctx.code)
        if fixed and fixed.strip() != ctx.code.strip():
            res.suggested_code = fixed
    return res
