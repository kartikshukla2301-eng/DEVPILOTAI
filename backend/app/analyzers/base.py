"""Shared primitives for all analyzers."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.schemas import Finding

LANGUAGE_EXT = {
    "python": "py",
    "javascript": "js",
    "typescript": "ts",
    "java": "java",
    "cpp": "cpp",
    "c": "c",
    "go": "go",
}

LANGUAGE_LABEL = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "java": "Java",
    "cpp": "C++",
    "c": "C",
    "go": "Go",
}


@dataclass
class AnalysisContext:
    code: str
    language: str
    filename: str
    categories: set[str]
    lines: list[str] = field(init=False)

    def __post_init__(self) -> None:
        self.lines = self.code.splitlines()

    def snippet(self, line: int | None, context: int = 1) -> str | None:
        if not line or line < 1 or line > len(self.lines):
            return None
        start = max(1, line - context)
        end = min(len(self.lines), line + context)
        width = len(str(end))
        out = []
        for n in range(start, end + 1):
            marker = ">" if n == line else " "
            out.append(f"{marker} {str(n).rjust(width)} | {self.lines[n - 1]}")
        return "\n".join(out)


@dataclass
class AnalyzerResult:
    findings: list[Finding] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    functions: int = 0
    classes: int = 0
    max_complexity: int | None = None
    avg_complexity: float | None = None
    max_nesting: int = 0
    suggested_code: str | None = None


class FindingCollector:
    """Builds findings with stable ids and drops exact duplicates."""

    def __init__(self, ctx: AnalysisContext) -> None:
        self.ctx = ctx
        self.items: list[Finding] = []
        self._seen: set[tuple] = set()

    def add(
        self,
        category: str,
        severity: str,
        title: str,
        description: str,
        recommendation: str,
        line: int | None = None,
        *,
        column: int | None = None,
        end_line: int | None = None,
        rule: str | None = None,
        tool: str = "devpilot",
        source: str = "static",
    ) -> None:
        if category not in self.ctx.categories:
            return
        key = (category, title, line, rule)
        if key in self._seen:
            return
        self._seen.add(key)
        fid = hashlib.sha1(f"{tool}:{rule}:{title}:{line}:{column}".encode()).hexdigest()[:12]
        self.items.append(
            Finding(
                id=fid,
                category=category,  # type: ignore[arg-type]
                severity=severity,  # type: ignore[arg-type]
                title=title,
                description=description,
                recommendation=recommendation,
                line=line,
                end_line=end_line,
                column=column,
                snippet=self.ctx.snippet(line),
                rule=rule,
                source=source,  # type: ignore[arg-type]
                tool=tool,
            )
        )


# ----------------------------------------------------------------------------
# Source masking: blank out comments and string contents while preserving
# offsets and newlines, so regex rules don't fire inside strings or comments.
# ----------------------------------------------------------------------------
def mask_source(code: str, language: str) -> str:
    out = list(code)
    n = len(code)
    i = 0
    py = language == "python"
    backtick = language in ("javascript", "typescript", "go")

    def blank(a: int, b: int) -> None:
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if py and c == "#":
            j = code.find("\n", i)
            j = n if j == -1 else j
            blank(i, j)
            i = j
        elif not py and c == "/" and nxt == "/":
            j = code.find("\n", i)
            j = n if j == -1 else j
            blank(i, j)
            i = j
        elif not py and c == "/" and nxt == "*":
            j = code.find("*/", i + 2)
            j = n if j == -1 else j + 2
            blank(i, j)
            i = j
        elif py and code.startswith(('"""', "'''"), i):
            q = code[i : i + 3]
            j = code.find(q, i + 3)
            j = n if j == -1 else j + 3
            blank(i + 3, j - 3)
            i = j
        elif c in "\"'" or (backtick and c == "`"):
            j = i + 1
            raw = c == "`" and language == "go"  # Go raw strings have no escapes
            while j < n:
                if code[j] == "\\" and not raw:
                    j += 2
                    continue
                if code[j] == c:
                    break
                if code[j] == "\n" and c != "`":
                    break
                j += 1
            blank(i + 1, j)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def leading_ws(line: str) -> int:
    return len(line) - len(line.lstrip(" \t").replace("\t", "    "))


def duplicate_blocks(lines: list[str], window: int = 5, min_chars: int = 80) -> list[tuple[int, int]]:
    """Return (first_line, duplicate_line) pairs for repeated non-trivial windows."""
    norm = []
    for idx, raw in enumerate(lines, start=1):
        s = re.sub(r"\s+", " ", raw.strip())
        if s and s not in ("{", "}", "};", ")", "]", "pass", "else:", "} else {", "end"):
            norm.append((idx, s))
    seen: dict[str, int] = {}
    pairs: list[tuple[int, int]] = []
    last_dup_end = 0
    for k in range(len(norm) - window + 1):
        chunk = norm[k : k + window]
        text = "\n".join(s for _, s in chunk)
        if len(text) < min_chars:
            continue
        h = hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()
        first_line = chunk[0][0]
        if h in seen:
            if first_line > last_dup_end and first_line - seen[h] >= window:
                pairs.append((seen[h], first_line))
                last_dup_end = chunk[-1][0]
        else:
            seen[h] = first_line
    return pairs


SECRET_NAME = r"(?:password|passwd|pwd|secret|api[_-]?key|apikey|auth[_-]?token|access[_-]?token|token|private[_-]?key|client[_-]?secret|access[_-]?key)"
SECRET_ASSIGN = re.compile(
    rf"""(?i)\b[\w.]*{SECRET_NAME}[\w]*\b["']?\s*(?::=|=|:)\s*(?:[frbu]?)["'`]([^"'`\s]{{4,}})["'`]"""
)
PLACEHOLDER = re.compile(r"(?i)^(?:x+|\*+|changeme|change[-_]?me|your[-_].*|<.*>|\$\{.*\}|\{\{.*\}\}|example|test|dummy|placeholder|none|null|password|secret|todo)$")
AWS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")
GENERIC_TOKEN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|xox[bpoa]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35})\b")


def scan_secrets(col: FindingCollector, lines: list[str]) -> None:
    """Language-agnostic hardcoded credential detection."""
    for n, line in enumerate(lines, start=1):
        if PRIVATE_KEY.search(line):
            col.add("security", "critical", "Private key embedded in source",
                    "A PEM private key block appears in the source. Anyone with access to the code can impersonate the key owner.",
                    "Remove the key, rotate it immediately, and load it from a secrets manager or an environment-provided file path.",
                    n, rule="secret-private-key")
            continue
        if AWS_KEY.search(line):
            col.add("security", "critical", "AWS access key ID in source",
                    "A string matching the AWS access key ID format was found. Committed cloud keys are routinely harvested by automated scanners.",
                    "Revoke and rotate the key in IAM, then load credentials from the environment or an IAM role.",
                    n, rule="secret-aws-key")
            continue
        if GENERIC_TOKEN.search(line):
            col.add("security", "critical", "API token in source",
                    "A string matching a well-known API token format (OpenAI, GitHub, Slack or Google) was found.",
                    "Revoke the token and read it from an environment variable or secrets manager.",
                    n, rule="secret-token")
            continue
        m = SECRET_ASSIGN.search(line)
        if m and not PLACEHOLDER.match(m.group(1)):
            col.add("security", "high", "Hardcoded credential",
                    "A value that looks like a password, key or token is assigned as a string literal. Secrets in source end up in version control, logs and build artifacts.",
                    "Load the value from an environment variable or a secrets manager, and rotate the exposed secret.",
                    n, rule="secret-hardcoded")


def decision_points(text: str, language: str) -> int:
    if language == "python":
        pat = r"\b(?:if|elif|for|while|except|and|or|case)\b"
    else:
        pat = r"\b(?:if|for|while|case|catch)\b|&&|\|\||\?(?![.?])"
    return len(re.findall(pat, text))
