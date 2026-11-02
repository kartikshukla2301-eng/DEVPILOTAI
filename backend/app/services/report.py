"""Render saved review reports for export."""
from __future__ import annotations

from typing import Any

from app.analyzers.base import LANGUAGE_LABEL
from app.analyzers.registry import DISCLAIMER

SEV_ICON = {"critical": "🟥", "high": "🟧", "medium": "🟨", "low": "🟦", "info": "⬜"}


def review_markdown(r: dict[str, Any]) -> str:
    created = r.get("created_at")
    lines = [
        f"# {r.get('title', 'Code review')}", "",
        f"- **File:** `{r.get('filename')}`",
        f"- **Language:** {LANGUAGE_LABEL.get(r.get('language', ''), r.get('language'))}",
        f"- **Date:** {created:%Y-%m-%d %H:%M UTC}" if created else "",
        f"- **Score:** {r.get('score')}/100 (grade {r.get('grade')})",
        f"- **Analysis:** {', '.join(r.get('categories', []))}",
        f"- **Tools:** {', '.join(r.get('tools_used', []))}",
        f"- **AI-assisted:** {'yes' if r.get('ai_used') else 'no (local static analysis)'}",
        "", "## Summary", "",
        "| Severity | Count |", "|---|---|",
    ]
    for sev, n in (r.get("summary") or {}).items():
        lines.append(f"| {SEV_ICON.get(sev, '')} {sev.capitalize()} | {n} |")
    if r.get("ai_summary"):
        lines += ["", "### AI assessment", "", r["ai_summary"]]
    m = r.get("metrics") or {}
    if m:
        lines += ["", "## Metrics", "",
                  f"- Lines: {m.get('lines_total')} total, {m.get('lines_code')} code, {m.get('lines_comment')} comment",
                  f"- Functions: {m.get('functions')}, classes: {m.get('classes')}",
                  f"- Max complexity: {m.get('max_complexity') if m.get('max_complexity') is not None else 'n/a'}, max nesting: {m.get('max_nesting')}"]
    lines += ["", "## Findings", ""]
    findings = r.get("findings") or []
    if not findings:
        lines.append("No issues were detected by the selected checks.")
    for i, f in enumerate(findings, start=1):
        src = "AI suggestion" if f.get("source") == "ai" else f"Static analysis ({f.get('tool')}{', ' + f['rule'] if f.get('rule') else ''})"
        lines += [
            f"### {i}. {SEV_ICON.get(f['severity'], '')} [{f['severity'].upper()}] {f['title']}", "",
            f"- **Category:** {f['category']}  ",
            f"- **Location:** `{r.get('filename')}`" + (f" line {f['line']}" if f.get("line") else ""),
            f"- **Source:** {src}", "",
            f.get("description", ""), "",
            f"**Recommendation:** {f.get('recommendation', '')}", "",
        ]
        if f.get("snippet"):
            lines += ["```", f["snippet"], "```", ""]
    if r.get("suggested_code"):
        lines += ["## Suggested code", "",
                  f"_Source: {'AI-generated — review carefully' if r.get('suggested_code_source') == 'ai' else 'automatic safe fixes'}_", "",
                  f"```{r.get('language', '')}", r["suggested_code"].rstrip(), "```", ""]
    lines += ["## Original code", "", f"```{r.get('language', '')}", (r.get("code") or "").rstrip(), "```", "", "---", "", f"_{DISCLAIMER}_", ""]
    return "\n".join(x for x in lines if x is not None)
