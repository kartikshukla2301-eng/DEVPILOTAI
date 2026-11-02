"""Heuristic analyzer for brace-based languages: JavaScript, TypeScript, Java, C, C++, Go.

Works on a "masked" copy of the source (comments and string contents blanked)
so patterns do not match inside strings or comments. Rules that must look at
string contents (SQL, secrets, format strings) run on the raw source.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.analyzers import tools
from app.analyzers.base import (
    AnalysisContext,
    AnalyzerResult,
    FindingCollector,
    decision_points,
    duplicate_blocks,
    mask_source,
    scan_secrets,
)

JS = {"javascript", "typescript"}
JVM = {"java"}
CFAM = {"c", "cpp"}
GO = {"go"}
CLIKE = JS | JVM | CFAM | GO
CONTROL = {"if", "for", "while", "switch", "catch", "return", "else", "do", "function", "sizeof", "new", "typeof", "await", "elif", "case"}


@dataclass(frozen=True)
class Rule:
    id: str
    langs: frozenset
    category: str
    severity: str
    title: str
    description: str
    recommendation: str
    pattern: re.Pattern
    raw: bool = False          # match against raw (unmasked) line
    in_loop: bool = False      # only fire inside a loop body
    min_loop_depth: int = 1


def R(id, langs, cat, sev, title, desc, rec, pat, *, raw=False, in_loop=False, flags=0, min_loop_depth=1) -> Rule:
    return Rule(id, frozenset(langs), cat, sev, title, desc, rec, re.compile(pat, flags), raw, in_loop, min_loop_depth)


SQL_CONCAT = r"""(?i)["'`]\s*(?:select\s[^"'`]*\sfrom|insert\s+into|update\s+\w+\s+set|delete\s+from)\b[^"'`]*["'`]\s*\+|`\s*(?:select\s[^`]*\sfrom|insert\s+into|update\s+\w+\s+set|delete\s+from)\b[^`]*\$\{"""

RULES: list[Rule] = [
    # ---------------- security: all ----------------
    R("sql-concat", CLIKE, "security", "high", "Possible SQL injection",
      "The SQL statement is assembled by concatenating or interpolating values. If any value is user-controlled, the query can be altered.",
      "Use parameterized queries / prepared statements (e.g. `db.query('SELECT * FROM t WHERE id = ?', [id])`, `PreparedStatement`, `db.Query(q, args...)`).",
      SQL_CONCAT, raw=True),
    R("go-sql-sprintf", GO, "security", "high", "SQL built with fmt.Sprintf",
      "Formatting values into SQL text allows injection when any value is user-controlled.",
      "Pass values as query arguments: `db.Query(\"SELECT ... WHERE id = $1\", id)`.",
      r"""(?i)fmt\.Sprintf\(\s*"[^"]*\b(select|insert|update|delete)\b""", raw=True),
    # ---------------- security: JS/TS ----------------
    R("js-eval", JS, "security", "high", "Use of eval()", "eval() executes arbitrary strings as code; with user input this is code injection.",
      "Use JSON.parse for data, or explicit logic / lookup tables instead of evaluating strings.", r"(?<![\w.])eval\s*\("),
    R("js-new-function", JS, "security", "high", "Dynamic code via new Function()", "new Function() compiles strings into code at runtime, equivalent to eval().",
      "Avoid building code from strings; use closures or lookup tables.", r"\bnew\s+Function\s*\("),
    R("js-timer-string", JS, "security", "medium", "String passed to setTimeout/setInterval", "Passing a string makes the timer evaluate it like eval().",
      "Pass a function: `setTimeout(() => doWork(), 100)`.", r"\bset(?:Timeout|Interval)\s*\(\s*[\"'`]", raw=True),
    R("js-innerhtml", JS, "security", "high", "Assignment to innerHTML/outerHTML", "Writing HTML built from variables enables cross-site scripting (XSS) if any part is user-controlled.",
      "Use `textContent` for text, or sanitize with a library such as DOMPurify before inserting HTML.", r"\.(?:inner|outer)HTML\s*\+?=(?!=)"),
    R("js-document-write", JS, "security", "medium", "document.write / insertAdjacentHTML", "These APIs inject raw HTML and are common XSS sinks.",
      "Create elements with document.createElement and set textContent.", r"\bdocument\.write(?:ln)?\s*\(|\.insertAdjacentHTML\s*\("),
    R("js-dangerous-html", JS, "security", "medium", "dangerouslySetInnerHTML", "React's escape hatch for raw HTML bypasses its XSS protection.",
      "Render text normally, or sanitize the HTML with DOMPurify first.", r"dangerouslySetInnerHTML"),
    R("js-exec-concat", JS, "security", "critical", "Shell command built from variables", "child_process exec with interpolated values allows command injection.",
      "Use execFile/spawn with an argument array and no shell: `execFile('ls', ['-l', dir])`.",
      r"\bexec(?:Sync)?\s*\(\s*(?:`[^`]*\$\{|[\"'][^\"']*[\"']\s*\+|\w+\s*\+)", raw=True),
    R("js-weak-random", JS, "security", "medium", "Math.random() used for a security value", "Math.random() is predictable and must not generate tokens, passwords or IDs that need to be unguessable.",
      "Use `crypto.randomUUID()` or `crypto.getRandomValues()`.", r"(?i)(token|password|secret|salt|nonce|otp|key)\w*\s*[:=].*Math\.random\(", raw=True),
    R("js-token-storage", JS, "security", "low", "Auth token in localStorage", "Tokens in localStorage are readable by any script on the page, so an XSS bug leaks them.",
      "Prefer httpOnly, Secure, SameSite cookies for session tokens, and keep a strict CSP.", r"(?i)localStorage\.setItem\(\s*[\"'`][^\"'`]*(token|jwt|auth)", raw=True),
    # ---------------- security: Java ----------------
    R("java-runtime-exec", JVM, "security", "high", "Runtime.exec()", "Executing OS commands built from input enables command injection.",
      "Use ProcessBuilder with a fixed command and argument list, and validate inputs.", r"Runtime\.getRuntime\(\)\.exec\s*\("),
    R("java-deser", JVM, "security", "high", "Unsafe Java deserialization", "ObjectInputStream.readObject() on untrusted data can lead to remote code execution through gadget chains.",
      "Avoid native serialization for untrusted input; use JSON with explicit DTOs, or an ObjectInputFilter allow-list.", r"\bnew\s+ObjectInputStream\s*\(|\.readObject\s*\(\s*\)"),
    R("java-weak-hash", JVM, "security", "medium", "Weak hash algorithm", "MD5 and SHA-1 are broken for security purposes.",
      "Use SHA-256 or stronger; for passwords use BCrypt, SCrypt or Argon2.", r"""MessageDigest\.getInstance\(\s*"(?:MD5|SHA-?1)"\s*\)""", raw=True, flags=re.I),
    R("java-weak-random", JVM, "security", "low", "java.util.Random for security values", "java.util.Random is predictable.",
      "Use java.security.SecureRandom for tokens and keys.", r"(?i)(token|password|secret|salt|key)\w*\s*=.*new\s+Random\s*\(", raw=True),
    # ---------------- security: C/C++ ----------------
    R("c-gets", CFAM, "security", "critical", "Use of gets()", "gets() cannot limit input length and always allows buffer overflow. It was removed from C11.",
      "Use `fgets(buf, sizeof buf, stdin)`.", r"(?<![\w.])gets\s*\("),
    R("c-unsafe-str", CFAM, "security", "high", "Unbounded string function", "strcpy/strcat/sprintf do not check the destination size and can overflow buffers.",
      "Use bounded versions: snprintf, strncpy/strlcpy (and terminate), or std::string in C++.", r"(?<![\w.])(?:strcpy|strcat|sprintf|vsprintf)\s*\("),
    R("c-scanf-s", CFAM, "security", "medium", "scanf with unbounded %s", "`%s` without a width reads unlimited input into a fixed buffer.",
      "Specify a width (`%63s` for a 64-byte buffer) or use fgets.", r"""\bscanf\s*\(\s*"[^"]*%s""", raw=True),
    R("c-system", CFAM, "security", "high", "Use of system()", "system() runs a shell; any interpolated input can inject commands.",
      "Use execve/posix_spawn with an argument vector, and validate inputs.", r"(?<![\w.:])system\s*\("),
    R("c-format-string", CFAM, "security", "high", "Format string vulnerability", "Passing a variable as the format argument lets an attacker read or write memory with %x / %n.",
      "Always use a literal format: `printf(\"%s\", buf)`.", r"\b(?:printf|fprintf\s*\(\s*\w+\s*,|syslog\s*\(\s*\w+\s*,)\s*\(?\s*[A-Za-z_]\w*\s*\)"),
    R("c-rand", CFAM, "security", "low", "rand() is not cryptographically secure", "rand() is predictable and has poor distribution.",
      "Use a CSPRNG (getrandom(), /dev/urandom, or <random> with std::random_device for non-security use).", r"(?<![\w.])rand\s*\(\s*\)"),
    # ---------------- security: Go ----------------
    R("go-tls-skip", GO, "security", "high", "TLS certificate verification disabled", "InsecureSkipVerify: true accepts any certificate and allows man-in-the-middle attacks.",
      "Remove InsecureSkipVerify or configure RootCAs for your internal CA.", r"InsecureSkipVerify\s*:\s*true"),
    R("go-shell", GO, "security", "high", "Command executed through a shell", "Running `sh -c` with built strings enables command injection.",
      "Call the program directly with exec.Command(\"prog\", arg1, arg2).", r"""exec\.Command\(\s*"(?:sh|bash|cmd|cmd\.exe|powershell)\"""", raw=True),
    R("go-weak-hash", GO, "security", "medium", "Weak hash algorithm imported", "crypto/md5 and crypto/sha1 are broken for security use.",
      "Use crypto/sha256; for passwords use golang.org/x/crypto/bcrypt or argon2.", r""""crypto/(?:md5|sha1)\"""", raw=True),
    # ---------------- bugs ----------------
    R("assign-in-cond", JS | JVM | CFAM, "bug", "medium", "Assignment inside a condition", "`if (x = y)` assigns instead of comparing, so the condition depends on the assigned value.",
      "Use `==` / `===` to compare. If the assignment is intentional, wrap it in extra parentheses and compare explicitly.",
      r"\b(?:if|while)\s*\(\s*[A-Za-z_][\w.\[\]]*\s*=(?!=)"),
    R("empty-catch", JS | JVM | CFAM, "bug", "medium", "Empty catch block", "Errors are silently swallowed, hiding failures.",
      "Log the error, handle it, or rethrow it.", r"catch\s*(?:\([^)]*\))?\s*\{\s*\}"),
    R("off-by-one", JS | JVM | CFAM, "bug", "medium", "Possible off-by-one in loop bound", "The loop runs while `i <= length/size`, which indexes one element past the end.",
      "Use `<` when the bound is a length or size.", r"for\s*\([^;]*;\s*\w+\s*<=\s*[\w.]*(?:length|size\(\)|\.len\b|count|Count|sizeof\s*\(?\w+\)?)"),
    R("java-string-eq", JVM, "bug", "medium", "String compared with ==", "`==` compares object references, not string contents, so equal strings may compare false.",
      "Use `a.equals(b)` or `Objects.equals(a, b)`.", r"""==\s*"|"\s*==|!=\s*"|"\s*!=""", raw=True),
    R("js-foreach-async", JS, "bug", "medium", "async callback in forEach", "forEach does not wait for promises, so the loop finishes before the async work and errors go unhandled.",
      "Use `for (const x of items) { await ... }` or `await Promise.all(items.map(async x => ...))`.", r"\.forEach\s*\(\s*async\b"),
    R("js-debugger", JS, "bug", "low", "debugger statement", "A leftover `debugger` pauses execution when devtools are open.",
      "Remove the statement before shipping.", r"^\s*debugger\s*;?\s*$"),
    R("js-parseint-radix", JS, "bug", "low", "parseInt without radix", "Without a radix, inputs like '08' or '0x10' can be parsed unexpectedly.",
      "Pass the radix: `parseInt(value, 10)`, or use `Number(value)`.", r"\bparseInt\s*\(\s*[^,()]+\)"),
    R("js-nan-compare", JS, "bug", "high", "Comparison with NaN", "NaN is not equal to anything, including itself, so this comparison is always false (or always true for !==).",
      "Use `Number.isNaN(x)`.", r"[!=]==?\s*NaN\b|\bNaN\s*[!=]==?"),
    R("go-ignored-error", GO, "bug", "medium", "Error explicitly ignored", "The error return value is discarded with `_`, so failures go unnoticed.",
      "Handle the error: `if err != nil { return err }`.", r"\b\w+\s*,\s*_\s*:?=\s*[\w.]+\("),
    R("go-defer-loop", GO, "bug", "medium", "defer inside a loop", "Deferred calls run only when the function returns, so resources opened in the loop stay open until then.",
      "Move the loop body into a helper function, or close the resource explicitly each iteration.", r"^\s*defer\b", in_loop=True),
    # ---------------- quality ----------------
    R("js-loose-eq", JS, "quality", "low", "Loose equality (==)", "`==` performs type coercion (`'0' == 0` is true), which causes subtle bugs.",
      "Use strict equality `===` / `!==`.", r"(?<![=!<>])[!=]=(?!=)\s*(?!null\b|undefined\b)"),
    R("js-var", JS, "quality", "low", "Use of var", "`var` is function-scoped and hoisted, which can cause surprising behaviour.",
      "Use `const` by default, or `let` when the variable is reassigned.", r"(?<![\w.])var\s+[A-Za-z_$]"),
    R("js-console", JS, "quality", "info", "console.log left in code", "Debug logging can leak data and clutter output.",
      "Remove it or use a proper logger with levels.", r"\bconsole\.log\s*\("),
    R("ts-any", {"typescript"}, "quality", "low", "Use of `any`", "`any` disables type checking for the value.",
      "Use a precise type, a generic, or `unknown` with narrowing.", r":\s*any\b|\bas\s+any\b|<any>"),
    R("ts-ignore", {"typescript"}, "quality", "low", "@ts-ignore / @ts-nocheck", "Suppressing compiler errors hides real type problems.",
      "Fix the type error, or use `@ts-expect-error` with a comment explaining why.", r"@ts-(?:ignore|nocheck)", raw=True),
    R("java-broad-catch", JVM, "quality", "low", "Catching generic Exception", "Catching Exception/Throwable hides unexpected failures and makes error handling imprecise.",
      "Catch the specific exception types you can handle.", r"catch\s*\(\s*(?:final\s+)?(?:Exception|Throwable|RuntimeException)\s+\w+\s*\)"),
    R("java-printstacktrace", JVM, "quality", "low", "printStackTrace()", "Stack traces printed to stderr are lost in production and can leak internals.",
      "Use a logger: `log.error(\"message\", e)`.", r"\.printStackTrace\s*\(\s*\)"),
    R("java-boxing", JVM, "quality", "low", "Deprecated boxing constructor", "`new Integer(...)` and similar constructors are deprecated and always allocate.",
      "Use `Integer.valueOf(...)` or autoboxing.", r"\bnew\s+(?:Integer|Long|Double|Float|Short|Byte|Boolean|Character)\s*\("),
    R("java-size-zero", JVM, "quality", "info", "size() == 0 instead of isEmpty()", "isEmpty() states intent more clearly and can be faster for some collections.",
      "Use `collection.isEmpty()`.", r"\.size\(\)\s*==\s*0"),
    R("java-system-exit", JVM, "quality", "low", "System.exit() call", "System.exit kills the JVM, skipping cleanup and making code untestable.",
      "Throw an exception or return an exit code from main.", r"\bSystem\.exit\s*\("),
    R("cpp-using-std", {"cpp"}, "quality", "low", "using namespace std", "Importing all of std into the global namespace risks name collisions.",
      "Qualify names (`std::vector`) or import specific names (`using std::vector;`).", r"^\s*using\s+namespace\s+std\s*;"),
    R("go-panic", GO, "quality", "low", "panic() used for error handling", "panic should be reserved for unrecoverable programmer errors.",
      "Return an error value to the caller.", r"(?<![\w.])panic\s*\("),
    # ---------------- performance ----------------
    R("c-strlen-loop", CFAM, "performance", "medium", "strlen() in loop condition", "strlen is O(n) and is re-evaluated on every iteration, making the loop O(n^2).",
      "Compute the length once before the loop: `size_t len = strlen(s);`.", r"for\s*\([^;]*;[^;]*\bstrlen\s*\("),
    R("cpp-pass-by-value", {"cpp"}, "performance", "low", "Large object passed by value", "Containers and strings passed by value are copied on every call.",
      "Pass by const reference: `const std::vector<int>& v`.",
      r"[(,]\s*(?:const\s+)?(?:std::)?(?:vector|string|map|unordered_map|set|unordered_set|list|deque)\b(?:<[^&*()]*>)?\s+\w+\s*(?=[,)])"),
    R("cpp-endl-loop", {"cpp"}, "performance", "low", "std::endl inside a loop", "std::endl flushes the stream every time, which is slow in loops.",
      "Use '\\n' and flush once at the end.", r"std::endl|<<\s*endl\b", in_loop=True),
    R("js-await-loop", JS, "performance", "medium", "await inside a loop", "Each iteration waits for the previous one, so independent async work runs sequentially.",
      "If iterations are independent, run them concurrently: `await Promise.all(items.map(fn))`.", r"\bawait\b", in_loop=True),
    R("js-dom-query-loop", JS, "performance", "low", "DOM query inside a loop", "Querying the DOM repeatedly is expensive.",
      "Query once before the loop and reuse the reference.", r"\bdocument\.(?:querySelector(?:All)?|getElementById|getElementsBy\w+)\s*\(", in_loop=True),
    R("js-linear-search-loop", JS, "performance", "low", "Linear search inside a loop", "`.includes()` / `.indexOf()` / `.find()` on an array is O(n); inside a loop this becomes O(n*m).",
      "Build a Set or Map once before the loop for O(1) lookups.", r"\.(?:includes|indexOf|find|findIndex)\s*\(", in_loop=True),
    R("js-json-clone", JS, "performance", "low", "Deep clone via JSON round-trip", "JSON.parse(JSON.stringify(x)) is slow and drops Dates, Maps, undefined and functions.",
      "Use `structuredClone(x)`.", r"JSON\.parse\s*\(\s*JSON\.stringify\s*\("),
    R("java-regex-loop", JVM, "performance", "low", "Regex compiled inside a loop", "Pattern.compile / String.matches / replaceAll recompile the regex each call.",
      "Compile the Pattern once as a static final field.", r"Pattern\.compile\s*\(|\.matches\s*\(|\.replaceAll\s*\(|\.split\s*\(", in_loop=True),
    R("java-linear-search-loop", JVM, "performance", "low", "List lookup inside a loop", "List.contains/indexOf is O(n); inside a loop this becomes O(n*m).",
      "Use a HashSet / HashMap for lookups.", r"\.(?:contains|indexOf)\s*\(", in_loop=True),
    R("go-regex-loop", GO, "performance", "low", "Regex compiled inside a loop", "regexp.Compile/MustCompile is expensive.",
      "Compile once at package level: `var re = regexp.MustCompile(...)`.", r"regexp\.(?:Must)?Compile\s*\(", in_loop=True),
    R("go-append-loop", GO, "performance", "info", "Slice grown with append in a loop", "Without preallocation the slice is reallocated and copied as it grows.",
      "If the final size is known, preallocate: `out := make([]T, 0, n)`.", r"(\w+)\s*=\s*append\(\s*\1\s*,", in_loop=True),
]

# ---------------------------------------------------------------------------
# Structure detection
# ---------------------------------------------------------------------------
FUNC_PATTERNS = {
    "js": [
        re.compile(r"\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)\s*\("),
        re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*(?::\s*[^=]+?)?\s*=>|[A-Za-z_$][\w$]*\s*=>)"),
        re.compile(r"^\s*(?:(?:public|private|protected|static|async|readonly|override|get|set)\s+)*([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*(?::\s*[^{]+)?\{"),
    ],
    "java": [re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract|synchronized|native|default)\s+)*(?:<[^>]+>\s+)?[\w<>\[\],.? ]+\s+([A-Za-z_]\w*)\s*\([^;{]*\)\s*(?:throws\s+[\w.,\s]+)?\s*\{?\s*$")],
    "c": [re.compile(r"^\s*(?:(?:static|inline|extern|virtual|const|unsigned|signed|struct|constexpr|explicit)\s+)*[\w:<>*&,\s]+?[\s*&]+([A-Za-z_~][\w:]*)\s*\([^;]*\)\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?\{?\s*$")],
    "go": [re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*\(")],
}
CLASS_PATTERNS = {
    "js": re.compile(r"\b(?:class|interface|enum)\s+([A-Za-z_$][\w$]*)"),
    "java": re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_]\w*)"),
    "c": re.compile(r"\b(?:class|struct|union)\s+([A-Za-z_]\w*)\s*(?::[^{;]*)?\{?\s*$"),
    "go": re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+(?:struct|interface)\b"),
}
LOOP_HEAD = re.compile(r"\b(?:for|while)\b\s*\(|\bdo\s*\{|\bfor\s*(?:each\s*)?\(")
GO_LOOP_HEAD = re.compile(r"^\s*for\b")
JS_REGEX_LITERAL = re.compile(r"([=(,:!&|?{;\[]\s*|return\s+)(/(?![/*])(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[])+/[dgimsuyv]*)")


def _family(lang: str) -> str:
    return {"javascript": "js", "typescript": "js", "java": "java", "c": "c", "cpp": "c", "go": "go"}[lang]


def _mask_regex_literals(masked: str) -> str:
    return JS_REGEX_LITERAL.sub(lambda m: m.group(1) + " " * len(m.group(2)), masked)


@dataclass
class Block:
    kind: str  # loop | func | class | block
    line: int
    name: str = ""


def _structure(ctx: AnalysisContext, mlines: list[str], col: FindingCollector, res: AnalyzerResult) -> list[int]:
    """Walk braces. Returns loop depth per line; records functions/classes/nesting."""
    fam = _family(ctx.language)
    loop_depth_at: list[int] = []
    stack: list[Block] = []
    pending: Block | None = None
    funcs: list[tuple[str, int, int]] = []
    deep_reported = False
    nested_loop_reported: set[int] = set()

    braceless = False  # previous line was a loop header whose body follows without '{'
    for n, line in enumerate(mlines, start=1):
        depth_now = sum(1 for b in stack if b.kind == "loop") + (1 if braceless else 0)
        is_loop = bool(LOOP_HEAD.search(line) or (fam == "go" and GO_LOOP_HEAD.search(line)))
        # `for (...) { body; }` on one line: treat the line itself as inside the loop
        inline_body = is_loop and re.search(r"\{\s*\S", line) is not None
        loop_depth_at.append(depth_now + (1 if inline_body else 0))
        braceless = is_loop and "{" not in line and not line.strip().endswith(";")

        name = ""
        kind = None
        cm = CLASS_PATTERNS[fam].search(line)
        if cm:
            kind, name = "class", cm.group(1)
        else:
            for p in FUNC_PATTERNS[fam]:
                fm = p.search(line)
                if fm and fm.group(1) not in CONTROL:
                    kind, name = "func", fm.group(1)
                    break
        if is_loop:
            kind = "loop"
        if kind:
            pending = Block(kind, n, name)
            if kind == "class":
                res.classes += 1
            if kind == "loop" and depth_now + 1 >= 3 and n not in nested_loop_reported:
                nested_loop_reported.add(n)
                col.add("performance", "medium", "Deeply nested loops",
                        f"Loop nested {depth_now + 1} levels deep; runtime grows roughly as O(n^{depth_now + 1}).",
                        "Precompute lookups in a hash map/set or restructure the algorithm to reduce nesting.", n, rule="nested-loops")

        for ch in line:
            if ch == "{":
                if pending is not None:
                    stack.append(pending)
                    pending = None
                else:
                    stack.append(Block("block", n))
                nest = sum(1 for b in stack if b.kind in ("loop", "block"))
                res.max_nesting = max(res.max_nesting, nest)
                if nest >= 5 and not deep_reported:
                    deep_reported = True
                    col.add("quality", "medium", "Deeply nested code",
                            "Code is nested five or more blocks deep, which makes it hard to read and test.",
                            "Use early returns/continue, or extract inner blocks into functions.", n, rule="deep-nesting")
            elif ch == "}" and stack:
                b = stack.pop()
                if b.kind == "func":
                    funcs.append((b.name, b.line, n))
        if pending is not None and line.strip().endswith(";"):
            pending = None  # declaration / prototype, not a block opener

    # functions: length + complexity
    complexities = []
    for name, start, end in funcs:
        res.functions += 1
        body = "\n".join(mlines[start - 1:end])
        cc = decision_points(body, ctx.language) + 1
        complexities.append(cc)
        length = end - start + 1
        if length > 60:
            col.add("quality", "low", f"Long function `{name}`",
                    f"`{name}` spans {length} lines; long functions are harder to understand and test.",
                    "Split it into smaller functions with one responsibility each.", start, rule="long-function")
        if cc > 10:
            col.add("quality", "high" if cc > 20 else "medium", f"High complexity in `{name}`",
                    f"`{name}` has an estimated cyclomatic complexity of {cc} (decision points + 1).",
                    "Reduce branching: extract helpers, use guard clauses, replace switch chains with lookup tables.", start, rule="complexity")
        _naming(ctx, col, name, start, "func")
    if complexities:
        res.max_complexity = max(complexities)
        res.avg_complexity = round(sum(complexities) / len(complexities), 2)
    for n, line in enumerate(mlines, start=1):
        cm = CLASS_PATTERNS[fam].search(line)
        if cm:
            _naming(ctx, col, cm.group(1), n, "class")
    return loop_depth_at


def _naming(ctx: AnalysisContext, col: FindingCollector, name: str, line: int, kind: str) -> None:
    lang = ctx.language
    short = name.split("::")[-1]
    if kind == "class" and lang in ("java", "javascript", "typescript", "go") and not re.fullmatch(r"[A-Z][A-Za-z0-9]*", short):
        if lang == "go" and re.fullmatch(r"[a-z][A-Za-z0-9]*", short):
            return  # unexported Go type
        col.add("quality", "low", f"Type name `{short}` is not PascalCase",
                "Types and classes are conventionally named in PascalCase in this language.",
                f"Rename to `{''.join(p[:1].upper() + p[1:] for p in re.split(r'_+', short) if p)}`.", line, rule="naming-class")
    if kind == "func" and lang in ("java", "javascript", "typescript", "go") and "_" in short.strip("_") and not short.isupper():
        parts = [p for p in short.split("_") if p]
        camel = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
        col.add("quality", "low", f"Function `{short}` is not camelCase",
                f"{'Go uses MixedCaps' if lang == 'go' else 'camelCase is the convention'} for function names; underscores are unidiomatic.",
                f"Rename to `{camel}`.", line, rule="naming-func")


def _balance(mlines: list[str]) -> tuple[int, str] | None:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[tuple[str, int]] = []
    for n, line in enumerate(mlines, start=1):
        for ch in line:
            if ch in "([{":
                stack.append((ch, n))
            elif ch in ")]}":
                if not stack or stack[-1][0] != pairs[ch]:
                    return n, f"Unexpected '{ch}'"
                stack.pop()
    if stack:
        ch, n = stack[-1]
        return n, f"Unclosed '{ch}'"
    return None


def _unused(ctx: AnalysisContext, masked: str, mlines: list[str], col: FindingCollector) -> None:
    lang = ctx.language

    def count(name: str) -> int:
        return len(re.findall(rf"(?<![\w$.]){re.escape(name)}(?![\w$])", masked))

    if lang in JS:
        for n, line in enumerate(ctx.lines, start=1):
            m = re.match(r"\s*import\s+(?:type\s+)?(.+?)\s+from\s+['\"]", line)
            if m:
                spec = m.group(1)
                names = []
                dm = re.match(r"([A-Za-z_$][\w$]*)\s*(?:,|$)", spec)
                if dm:
                    names.append(dm.group(1))
                nm = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", spec)
                if nm:
                    names.append(nm.group(1))
                bm = re.search(r"\{([^}]*)\}", spec)
                if bm:
                    for part in bm.group(1).split(","):
                        part = part.strip().removeprefix("type ").strip()
                        if part:
                            names.append(part.split(" as ")[-1].strip())
                for nm_ in names:
                    if count(nm_) <= 1:
                        col.add("quality", "low", f"Unused import `{nm_}`", f"`{nm_}` is imported but never used.",
                                "Remove the unused import to reduce bundle size and noise.", n, rule="unused-import")
        for n, line in enumerate(mlines, start=1):
            for m in re.finditer(r"(?<!export )\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=;]+)?=", line):
                if count(m.group(1)) == 1:
                    col.add("quality", "low", f"Unused variable `{m.group(1)}`",
                            f"`{m.group(1)}` is assigned but never read.", "Remove it, or use the value.", n, rule="unused-variable")
    elif lang == "java":
        for n, line in enumerate(ctx.lines, start=1):
            m = re.match(r"\s*import\s+(?!static)[\w.]+\.([A-Z]\w*)\s*;", line)
            if m and count(m.group(1)) <= 1:
                col.add("quality", "low", f"Unused import `{m.group(1)}`", f"`{m.group(1)}` is imported but never used.",
                        "Remove the import.", n, rule="unused-import")
    elif lang == "go":
        in_block = False
        for n, line in enumerate(ctx.lines, start=1):
            s = line.strip()
            if s.startswith("import ("):
                in_block = True
                continue
            if in_block and s == ")":
                in_block = False
                continue
            m = re.match(r'(?:import\s+)?(?:([A-Za-z_]\w*|_|\.)\s+)?"([\w./-]+)"', s) if (in_block or s.startswith("import ")) else None
            if m:
                alias, path = m.group(1), m.group(2)
                if alias in ("_", "."):
                    continue
                pkg = alias or path.rstrip("/").split("/")[-1]
                pkg = re.sub(r"^go-|\.v\d+$|-go$", "", pkg) if not alias else pkg
                if re.fullmatch(r"v\d+", pkg):
                    pkg = path.split("/")[-2]
                if not re.search(rf"(?<![\w.]){re.escape(pkg)}\.", masked):
                    col.add("bug", "medium", f"Unused import \"{path}\"",
                            "Go refuses to compile files with unused imports.", "Remove the import.", n, rule="go-unused-import")
        for n, line in enumerate(mlines, start=1):
            for m in re.finditer(r"(?<![\w.])([A-Za-z_]\w*)\s*:=", line):
                v = m.group(1)
                if v != "_" and v != "err" and count(v) == 1:
                    col.add("bug", "medium", f"Variable `{v}` declared and not used",
                            "Go refuses to compile functions with unused local variables.", "Remove the variable or use it.", n, rule="go-unused-var")
        # unchecked err
        for n, line in enumerate(mlines, start=1):
            if re.search(r"(?<![\w.])err\s*:?=\s*", line) and not re.search(r"\bif\b.*err", line):
                nxt = next((mlines[k] for k in range(n, min(n + 3, len(mlines))) if mlines[k].strip()), "")
                if "err" not in nxt and "return" not in line:
                    col.add("bug", "medium", "Error value not checked",
                            "`err` is assigned but the next statement does not check it, so failures are silently ignored.",
                            "Check immediately: `if err != nil { return fmt.Errorf(\"...: %w\", err) }`.", n, rule="go-unchecked-err")
    elif lang in CFAM:
        for n, line in enumerate(mlines, start=1):
            for m in re.finditer(r"^\s*(?:const\s+)?(?:int|long|short|float|double|char|bool|auto|size_t|unsigned(?:\s+int)?|std::string|string)\s+([A-Za-z_]\w*)\s*(?:=[^;]*)?;", line):
                if count(m.group(1)) == 1:
                    col.add("quality", "low", f"Unused variable `{m.group(1)}`", f"`{m.group(1)}` is declared but never used.",
                            "Remove the declaration.", n, rule="unused-variable")
        allocs = [n for n, l in enumerate(mlines, start=1) if re.search(r"(?<![\w.])(?:malloc|calloc|realloc)\s*\(", l)]
        frees = sum(len(re.findall(r"(?<![\w.])free\s*\(", l)) for l in mlines)
        if allocs and len(allocs) > frees:
            col.add("bug", "medium", "Possible memory leak",
                    f"Found {len(allocs)} allocation(s) but only {frees} call(s) to free().",
                    "Make sure every malloc/calloc has a matching free on all paths, including error paths.", allocs[0], rule="c-leak")
        if ctx.language == "cpp":
            news = [n for n, l in enumerate(mlines, start=1) if re.search(r"=\s*new\s+\w", l)]
            deletes = sum(len(re.findall(r"\bdelete\b", l)) for l in mlines)
            if news and len(news) > deletes:
                col.add("bug", "medium", "Raw new without matching delete",
                        f"Found {len(news)} `new` expression(s) but {deletes} `delete`.",
                        "Prefer std::unique_ptr / std::make_unique, or containers, so memory is released automatically.", news[0], rule="cpp-leak")


def _string_concat_loop(ctx: AnalysisContext, mlines: list[str], loop_depth: list[int], col: FindingCollector) -> None:
    if ctx.language == "java":
        decl = re.compile(r"\bString\s+([A-Za-z_]\w*)\s*[=;]")
    elif ctx.language == "go":
        decl = re.compile(r"(?:\bvar\s+([A-Za-z_]\w*)\s+string\b|([A-Za-z_]\w*)\s*:=\s*\"\")")
    elif ctx.language == "cpp":
        decl = re.compile(r"\b(?:std::)?string\s+([A-Za-z_]\w*)")
    else:
        return
    names: set[str] = set()
    for line in ctx.lines:
        for m in decl.finditer(line):
            names.add(next(g for g in m.groups() if g))
    if not names:
        return
    for n, line in enumerate(mlines, start=1):
        if loop_depth[n - 1] <= 0:
            continue
        for v in names:
            if re.search(rf"(?<![\w.]){re.escape(v)}\s*\+=|(?<![\w.]){re.escape(v)}\s*=\s*{re.escape(v)}\s*\+", line):
                fix = {"java": "Use a StringBuilder and call append() inside the loop.",
                       "go": "Use strings.Builder and WriteString() inside the loop.",
                       "cpp": "Call reserve() up front or use std::ostringstream / append()."}[ctx.language]
                col.add("performance", "medium", "String concatenation inside a loop",
                        f"`{v}` is rebuilt every iteration, copying the whole string each time (quadratic for large inputs).",
                        fix, n, rule="str-concat-loop")


def _syntax(ctx: AnalysisContext, mlines: list[str], col: FindingCollector, res: AnalyzerResult) -> bool:
    """Return True if a syntax error was found."""
    lang = ctx.language
    if lang == "javascript":
        r = tools.node_syntax_check(ctx.code, "mjs" if re.search(r"^\s*(import|export)\b", ctx.code, re.M) else "cjs")
        if r is not None:
            res.tools_used.append("node --check")
            if r is not True:
                line, msg = r  # type: ignore[misc]
                col.add("bug", "critical", f"Syntax error: {msg[:120]}", f"The JavaScript parser rejected the file: {msg}",
                        "Fix the syntax at the indicated line (check brackets, commas and quotes).", line or None, rule="syntax-error", tool="node")
                return True
            return False
    if lang == "go":
        r = tools.gofmt_check(ctx.code)
        if r is not None:
            res.tools_used.append("gofmt")
            if r is not True:
                line, msg = r  # type: ignore[misc]
                col.add("bug", "critical", f"Syntax error: {msg[:120]}", f"The Go parser rejected the file: {msg}",
                        "Fix the syntax at the indicated line.", line, rule="syntax-error", tool="gofmt")
                return True
            return False
    bal = _balance(mlines)
    if bal:
        line, msg = bal
        col.add("bug", "critical", f"Syntax error: {msg}",
                f"Brackets are unbalanced ({msg} on line {line}). The file will not compile or parse.",
                "Check for a missing or extra bracket/brace/parenthesis near this line.", line, rule="syntax-brackets")
        return True
    return False


def _suggest(ctx: AnalysisContext, masked: str) -> str | None:
    """Apply a few safe, mechanical fixes. Never touches string or comment contents."""
    code = ctx.code
    edits: list[tuple[int, int, str]] = []
    if ctx.language in JS:
        for m in re.finditer(r"(?<![=!<>])([!=])=(?!=)", masked):
            tail = masked[m.end():m.end() + 12].lstrip()
            if tail.startswith(("null", "undefined")):
                continue
            edits.append((m.start(), m.end(), m.group(1) + "=="))
        for m in re.finditer(r"(?<![\w.$])var(?=\s+[A-Za-z_$])", masked):
            edits.append((m.start(), m.end(), "let"))
    elif ctx.language in CFAM:
        for m in re.finditer(r"(?<![\w.])gets\s*\(\s*([A-Za-z_]\w*)\s*\)", masked):
            edits.append((m.start(), m.end(), f"fgets({m.group(1)}, sizeof({m.group(1)}), stdin)"))
    elif ctx.language == "java":
        for m in re.finditer(r"\.size\(\)\s*==\s*0", masked):
            edits.append((m.start(), m.end(), ".isEmpty()"))
        for m in re.finditer(r"\bnew\s+(Integer|Long|Double|Float|Short|Byte|Boolean)\s*\(", masked):
            edits.append((m.start(), m.end(), f"{m.group(1)}.valueOf("))
    if not edits:
        return None
    out = code
    for s, e, rep in sorted(edits, reverse=True):
        out = out[:s] + rep + out[e:]
    out = "\n".join(l.rstrip() for l in out.splitlines()) + ("\n" if code.endswith("\n") else "")
    return out if out != code else None


def analyze_clike(ctx: AnalysisContext) -> AnalyzerResult:
    res = AnalyzerResult()
    col = FindingCollector(ctx)
    res.tools_used.append(f"devpilot-rules:{ctx.language}")
    masked = mask_source(ctx.code, ctx.language)
    if ctx.language in JS:
        masked = _mask_regex_literals(masked)
    mlines = masked.splitlines()
    while len(mlines) < len(ctx.lines):
        mlines.append("")

    ctx_cats = ctx.categories
    ctx.categories = ctx_cats | {"bug"}  # syntax errors are always reported
    has_syntax_error = _syntax(ctx, mlines, col, res)
    ctx.categories = ctx_cats

    loop_depth = _structure(ctx, mlines, col, res)

    for rule in RULES:
        if ctx.language not in rule.langs or rule.category not in ctx.categories:
            continue
        src = ctx.lines if rule.raw else mlines
        for n, line in enumerate(src, start=1):
            if rule.in_loop and loop_depth[n - 1] < rule.min_loop_depth:
                continue
            if rule.raw and not mlines[n - 1].strip():
                continue  # whole line is a comment
            if rule.pattern.search(line):
                col.add(rule.category, rule.severity, rule.title, rule.description, rule.recommendation, n, rule=rule.id)

    if "security" in ctx.categories:
        scan_secrets(col, ctx.lines)
    if not has_syntax_error and ({"quality", "bug"} & ctx.categories):
        _unused(ctx, masked, mlines, col)
    if "performance" in ctx.categories:
        _string_concat_loop(ctx, mlines, loop_depth, col)
    if "quality" in ctx.categories:
        for first, dup in duplicate_blocks(ctx.lines):
            col.add("quality", "low", "Duplicated code block",
                    f"Lines starting at {dup} repeat a block that first appears at line {first}.",
                    "Extract the shared logic into a function and call it from both places.", dup, rule="duplicate-code")
        long_lines = [n for n, l in enumerate(ctx.lines, start=1) if len(l) > 140]
        if long_lines:
            col.add("quality", "info", "Very long lines",
                    f"{len(long_lines)} line(s) exceed 140 characters (first at line {long_lines[0]}).",
                    "Wrap long expressions or extract variables for readability.", long_lines[0], rule="long-lines")
        for n, l in enumerate(ctx.lines, start=1):
            if re.search(r"(?://|/\*|#)\s*(TODO|FIXME|HACK|XXX)\b", l):
                col.add("quality", "info", "Unresolved TODO/FIXME", "A TODO/FIXME marker indicates unfinished work.",
                        "Resolve it or track it in your issue tracker.", n, rule="todo")

    res.findings = col.items
    res.suggested_code = _suggest(ctx, masked)
    return res
