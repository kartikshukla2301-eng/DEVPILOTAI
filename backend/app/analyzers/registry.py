"""Analyzer registry and scoring.

To add a language: implement `def analyze_x(ctx: AnalysisContext) -> AnalyzerResult`
and register it in ANALYZERS.
"""
from __future__ import annotations

import math
from typing import Callable

from app.analyzers.base import AnalysisContext, AnalyzerResult, LANGUAGE_EXT
from app.analyzers.clike import analyze_clike
from app.analyzers.python_analyzer import analyze_python
from app.schemas import SEVERITY_ORDER, Finding, ReviewMetrics

ANALYZERS: dict[str, Callable[[AnalysisContext], AnalyzerResult]] = {
    "python": analyze_python,
    "javascript": analyze_clike,
    "typescript": analyze_clike,
    "java": analyze_clike,
    "cpp": analyze_clike,
    "c": analyze_clike,
    "go": analyze_clike,
}

SEVERITY_WEIGHT = {"critical": 25.0, "high": 12.0, "medium": 5.0, "low": 1.5, "info": 0.25}
SEVERITY_CAP = {"critical": 59, "high": 79}

DISCLAIMER = (
    "Static analysis uses heuristics and pattern matching. It can miss real problems and can report false positives; "
    "it does not guarantee that code is bug-free or secure. AI-generated findings and suggestions are marked separately "
    "and should be reviewed by a human before use."
)


def _comment_prefixes(language: str) -> tuple[str, ...]:
    return ("#",) if language == "python" else ("//", "/*", "*", "*/")


def compute_metrics(ctx: AnalysisContext, res: AnalyzerResult) -> ReviewMetrics:
    prefixes = _comment_prefixes(ctx.language)
    code_lines = comment_lines = 0
    for line in ctx.lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith(prefixes):
            comment_lines += 1
        else:
            code_lines += 1
    return ReviewMetrics(
        lines_total=len(ctx.lines),
        lines_code=code_lines,
        lines_comment=comment_lines,
        functions=res.functions,
        classes=res.classes,
        max_complexity=res.max_complexity,
        avg_complexity=res.avg_complexity,
        max_nesting=res.max_nesting,
    )


def score_findings(findings: list[Finding], lines_code: int) -> tuple[int, str]:
    """Score 0-100. Penalties are softened for larger files (density-based) and capped by the worst severity."""
    penalty = sum(SEVERITY_WEIGHT[f.severity] for f in findings)
    size_factor = max(1.0, math.sqrt(max(lines_code, 1) / 50))  # 50 LOC baseline
    adjusted = penalty / size_factor
    score = 100 * math.exp(-adjusted / 45)
    for sev, cap in SEVERITY_CAP.items():
        if any(f.severity == sev for f in findings):
            score = min(score, cap)
    score_i = max(0, min(100, round(score)))
    grade = "A" if score_i >= 90 else "B" if score_i >= 80 else "C" if score_i >= 70 else "D" if score_i >= 60 else "F"
    return score_i, grade


def summarize(findings: list[Finding]) -> tuple[dict[str, int], dict[str, int], str | None]:
    sev = {k: 0 for k in SEVERITY_ORDER}
    cat = {"bug": 0, "quality": 0, "security": 0, "performance": 0}
    for f in findings:
        sev[f.severity] += 1
        cat[f.category] += 1
    worst = min((f.severity for f in findings), key=lambda s: SEVERITY_ORDER[s], default=None)
    return sev, cat, worst


def run_static_analysis(code: str, language: str, filename: str | None, categories: list[str]) -> tuple[AnalyzerResult, ReviewMetrics, AnalysisContext]:
    fname = filename or f"snippet.{LANGUAGE_EXT[language]}"
    ctx = AnalysisContext(code=code, language=language, filename=fname, categories=set(categories))
    res = ANALYZERS[language](ctx)
    res.findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.line or 0))
    return res, compute_metrics(ctx, res), ctx
