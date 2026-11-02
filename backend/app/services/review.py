from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from app.analyzers.base import LANGUAGE_EXT, LANGUAGE_LABEL
from app.analyzers.registry import DISCLAIMER, run_static_analysis, score_findings, summarize
from app.schemas import SEVERITY_ORDER, Finding, ReviewIn
from app.services import ai

AI_REVIEW_SYSTEM = """You are a meticulous senior code reviewer. You receive source code and a list of issues already found by static analysis tools.
Report ONLY additional, concrete problems that the static tools missed (logic errors, edge cases, race conditions, security flaws, performance problems, maintainability).
Do not repeat issues already listed. Do not invent problems. Each finding must reference a real line number in the code.
Return JSON:
{
  "summary": "2-4 sentence overall assessment",
  "findings": [{"category": "bug|quality|security|performance", "severity": "critical|high|medium|low|info",
                "title": "short title", "description": "what is wrong and why it matters",
                "recommendation": "how to fix", "line": <int or null>}],
  "suggested_code": "the full corrected version of the code, or empty string if no changes are needed"
}
Limit to the 12 most important findings."""


def _ai_review(code: str, language: str, categories: list[str], static: list[Finding]) -> dict[str, Any]:
    listed = [{"line": f.line, "title": f.title, "category": f.category} for f in static[:60]]
    user = (
        f"Language: {LANGUAGE_LABEL[language]}\nFocus categories: {', '.join(categories)}\n"
        f"Already reported by static analysis:\n{json.dumps(listed)}\n\n"
        f"Code (line numbers start at 1):\n```{language}\n{ai.clip_code(code)}\n```"
    )
    return ai.chat_json(AI_REVIEW_SYSTEM, user, max_tokens=4000)


def _parse_ai_findings(data: dict[str, Any], categories: set[str], n_lines: int, ctx) -> list[Finding]:
    out: list[Finding] = []
    for raw in (data.get("findings") or [])[:12]:
        if not isinstance(raw, dict):
            continue
        cat = str(raw.get("category", "")).lower()
        sev = str(raw.get("severity", "")).lower()
        if cat not in categories or sev not in SEVERITY_ORDER:
            continue
        line = ai.as_int(raw.get("line"))
        if line and line > n_lines:
            line = None
        title = ai.as_str(raw.get("title"), "AI finding", 160)
        out.append(Finding(
            id="ai-" + hashlib.sha1(f"{title}:{line}".encode()).hexdigest()[:10],
            category=cat, severity=sev, title=title,  # type: ignore[arg-type]
            description=ai.as_str(raw.get("description"), "", 2000),
            recommendation=ai.as_str(raw.get("recommendation"), "", 2000),
            line=line, snippet=ctx.snippet(line), source="ai", tool="ai", rule=None,
        ))
    return out


def run_review(inp: ReviewIn, allow_ai: bool) -> dict[str, Any]:
    res, metrics, ctx = run_static_analysis(inp.code, inp.language, inp.filename, inp.categories)
    findings = list(res.findings)
    ai_used, ai_summary, ai_error = False, None, None
    suggested, suggested_src = res.suggested_code, ("static" if res.suggested_code else None)

    if allow_ai:
        try:
            data = _ai_review(inp.code, inp.language, inp.categories, findings)
            ai_findings = _parse_ai_findings(data, set(inp.categories), len(ctx.lines), ctx)
            static_keys = {(f.line, f.category) for f in findings}
            findings += [f for f in ai_findings if (f.line, f.category) not in static_keys]
            ai_summary = ai.as_str(data.get("summary"), "", 3000) or None
            code_suggestion = ai.as_str(data.get("suggested_code"), "", 100_000).strip()
            if code_suggestion and code_suggestion != inp.code.strip():
                suggested, suggested_src = code_suggestion, "ai"
            ai_used = True
        except ai.AIError as exc:
            ai_error = str(exc)

    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.line or 0))
    score, grade = score_findings(findings, metrics.lines_code)
    sev, cat, worst = summarize(findings)
    filename = inp.filename or f"snippet.{LANGUAGE_EXT[inp.language]}"
    title = inp.title or f"{LANGUAGE_LABEL[inp.language]} review — {filename}"
    return {
        "title": title,
        "filename": filename,
        "language": inp.language,
        "categories": inp.categories,
        "score": score,
        "grade": grade,
        "summary": sev,
        "category_summary": cat,
        "max_severity": worst,
        "total_findings": len(findings),
        "findings": [f.model_dump() for f in findings],
        "metrics": metrics.model_dump(),
        "tools_used": res.tools_used + (["ai"] if ai_used else []),
        "ai_used": ai_used,
        "ai_summary": ai_summary,
        "ai_error": ai_error,
        "suggested_code": suggested,
        "suggested_code_source": suggested_src,
        "code": inp.code,
        "created_at": datetime.now(timezone.utc),
        "disclaimer": DISCLAIMER,
    }
