import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ChevronDown, Crosshair, Download, FileJson, Info, ListFilter, Sparkles, Wand2 } from "lucide-react";
import { downloadFromApi, saveText } from "../../lib/api";
import { CATEGORIES, SEVERITIES, SEVERITY_META, langExt, scoreColor } from "../../lib/constants";
import type { Category, Finding, Review, Severity } from "../../lib/types";
import { cn, formatDate } from "../../lib/utils";
import { CodeDiff } from "../CodeEditor";
import { RichText } from "../Markdown";
import { Alert, Button, ConfirmDialog, CopyButton, EmptyState, ModeBadge, ScoreRing, SourceBadge } from "../ui";

function healthLabel(score: number) {
  if (score >= 90) return { text: "Ready to merge", color: "#22c55e" };
  if (score >= 75) return { text: "Minor issues to tidy up", color: "#4ade80" };
  if (score >= 60) return { text: "Needs attention before merge", color: "#38bdf8" };
  return { text: "At risk: fix critical issues first", color: "#fb7185" };
}

function ActionItem({ f, open, onToggle, onJump }: { f: Finding; open: boolean; onToggle: () => void; onJump?: (line: number) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open) ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [open]);
  const m = SEVERITY_META[f.severity];
  return (
    <div ref={ref} className={cn("rounded-xl border bg-surface transition-colors", open ? "border-border-strong" : "border-border hover:border-border-strong")}>
      <button onClick={onToggle} className="flex w-full items-start gap-3 px-4 py-3.5 text-left" aria-expanded={open}>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.08em]", m.panel)}>{m.label}</span>
            <span className="text-[14px] font-semibold leading-snug">{f.title}</span>
          </div>
          {!open && <p className="mt-1.5 line-clamp-1 text-xs text-muted">{f.description}</p>}
        </div>
        <span className="shrink-0 font-mono text-[11px] text-subtle">{f.line ? `Ln ${f.line}` : "—"}</span>
        <ChevronDown className={cn("mt-0.5 h-4 w-4 shrink-0 text-subtle transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-3 px-4 pb-4 text-[13px] animate-fade-in">
          <p className="leading-relaxed text-muted"><RichText text={f.description} /></p>
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/[0.06] px-3.5 py-3">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-emerald-400">Recommended fix</p>
            <p className="mt-1 leading-relaxed"><RichText text={f.recommendation} /></p>
          </div>
          {f.snippet && (
            <pre className="overflow-x-auto rounded-lg border border-border bg-bg px-3 py-2.5 font-mono text-[11.5px] leading-[1.7]">
              {f.snippet.split("\n").map((ln, i) => (
                <div key={i} className={ln.startsWith(">") ? "-mx-3 px-3 text-text" : "text-subtle"} style={ln.startsWith(">") ? { background: `${m.color}18`, boxShadow: `inset 2px 0 0 ${m.color}` } : undefined}>{ln}</div>
              ))}
            </pre>
          )}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <SourceBadge source={f.source} />
              <span className="font-mono text-[10.5px] text-subtle">{f.source === "ai" ? "verify before acting" : `${f.tool}${f.rule ? ` · ${f.rule}` : ""}`}</span>
            </div>
            {f.line && onJump && <Button size="sm" variant="secondary" icon={<Crosshair className="h-3.5 w-3.5" />} onClick={() => onJump(f.line!)}>Show in editor</Button>}
          </div>
        </div>
      )}
    </div>
  );
}

interface Props {
  review: Review;
  onJump?: (line: number) => void;
  /** Finding to expand (e.g. clicked inside the editor). */
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  /** If provided, shows "Load fix into editor" (explicit user action; asks for confirmation). */
  onApplySuggested?: (code: string) => void;
}

export function ReviewResults({ review, onJump, selectedId, onSelect, onApplySuggested }: Props) {
  const [sev, setSev] = useState<Severity | "all">("all");
  const [cat, setCat] = useState<Category | "all">("all");
  const [localOpen, setLocalOpen] = useState<string | null>(review.findings[0]?.id ?? null);
  const [confirmApply, setConfirmApply] = useState(false);
  const openId = selectedId !== undefined ? selectedId : localOpen;
  const setOpen = (id: string | null) => (onSelect ? onSelect(id) : setLocalOpen(id));

  useEffect(() => {
    if (selectedId) { setSev("all"); setCat("all"); }
  }, [selectedId]);

  const filtered = useMemo(() => review.findings.filter((f) => (sev === "all" || f.severity === sev) && (cat === "all" || f.category === cat)), [review.findings, sev, cat]);
  const health = healthLabel(review.score);
  const base = review.filename.replace(/\.[^.]+$/, "") || "review";
  const m = review.metrics;

  return (
    <div className="space-y-4">
      {/* Health */}
      <section className="card p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="eyebrow">{review.ai_used ? "AI + static security & quality audit" : "Static security & quality audit"}</p>
            <h2 className="mt-1.5 font-display text-[22px] font-semibold tracking-[-0.015em]">Code Health: {review.score}/100</h2>
            <p className="mt-0.5 text-[13px] font-medium" style={{ color: health.color }}>{health.text}</p>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <ModeBadge ai={review.ai_used} error={review.ai_error} />
              <span className="truncate font-mono text-[10.5px] text-subtle">{review.filename} · {formatDate(review.created_at)}</span>
            </div>
          </div>
          <ScoreRing score={review.score} grade={review.grade} size={92} color={scoreColor(review.score)} />
        </div>
        <div className="mt-5 grid grid-cols-5 gap-2">
          {SEVERITIES.map((s) => (
            <button key={s} onClick={() => setSev(sev === s ? "all" : s)} title={`Filter by ${SEVERITY_META[s].label}`}
              className={cn("rounded-lg px-1 py-2.5 text-center transition-all", SEVERITY_META[s].panel, sev === s ? "ring-1 ring-current" : "opacity-90 hover:opacity-100", !review.summary[s] && "opacity-45")}>
              <p className="font-display text-xl font-semibold leading-none tabular-nums">{review.summary[s] ?? 0}</p>
              <p className="mt-1 font-mono text-[9px] font-semibold uppercase tracking-[0.08em]">{SEVERITY_META[s].label}</p>
            </button>
          ))}
        </div>
        {review.ai_summary && (
          <div className="mt-4 flex gap-2.5 rounded-lg border border-accent/25 bg-accent-soft px-3.5 py-3 text-[13px]">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-accent-text" />
            <p className="leading-relaxed"><span className="font-medium text-accent-text">AI assessment · </span><span className="text-muted">{review.ai_summary}</span></p>
          </div>
        )}
        {review.ai_error && <div className="mt-4"><Alert tone="warning" icon={<AlertTriangle className="h-4 w-4 text-amber-400" />} title="AI analysis unavailable">{review.ai_error}. Showing static analysis results only.</Alert></div>}
      </section>

      {/* Action items */}
      <section>
        <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 px-1">
          <p className="eyebrow">Prioritized action items</p>
          <div className="flex items-center gap-2">
            <ListFilter className="h-3.5 w-3.5 text-subtle" />
            <select className="rounded-md border border-border bg-surface px-2 py-1 text-xs text-muted outline-none" value={cat} onChange={(e) => setCat(e.target.value as Category | "all")} aria-label="Filter by category">
              <option value="all">All categories</option>
              {CATEGORIES.filter((c) => review.categories.includes(c.value)).map((c) => <option key={c.value} value={c.value}>{c.label} ({review.category_summary[c.value] ?? 0})</option>)}
            </select>
            <span className="font-mono text-[11px] text-accent-text">{filtered.length} of {review.findings.length}</span>
          </div>
        </div>
        {review.findings.length === 0 ? (
          <div className="card"><EmptyState icon={<Sparkles className="h-5 w-5" />} title="No issues detected" description="The selected checks found nothing to report. This does not guarantee the code is bug-free." /></div>
        ) : filtered.length === 0 ? (
          <div className="card px-4 py-8 text-center text-[13px] text-muted">No findings match these filters. <button className="text-accent-text hover:underline" onClick={() => { setSev("all"); setCat("all"); }}>Clear filters</button></div>
        ) : (
          <div className="space-y-2">
            {filtered.map((f) => <ActionItem key={f.id} f={f} open={openId === f.id} onToggle={() => setOpen(openId === f.id ? null : f.id)} onJump={onJump} />)}
          </div>
        )}
      </section>

      {/* Suggested code */}
      <section className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3.5">
          <div>
            <h3 className="flex items-center gap-2 text-[15px] font-semibold"><Wand2 className="h-4 w-4 text-accent-text" /> Suggested corrected code</h3>
            <p className="mt-0.5 text-xs text-muted">
              {review.suggested_code
                ? review.suggested_code_source === "ai" ? "AI-generated. Review carefully before use." : "Automatic safe fixes (Ruff autofix, formatting, mechanical rewrites)."
                : "No automatic fix is available for these findings."}
            </p>
          </div>
          {review.suggested_code && (
            <div className="flex flex-wrap gap-2">
              <CopyButton text={review.suggested_code} label="Copy" />
              <Button size="sm" variant="outline" icon={<Download className="h-3.5 w-3.5" />} onClick={() => saveText(review.suggested_code!, `${base}.fixed.${langExt(review.language)}`)}>Download</Button>
              {onApplySuggested && <Button size="sm" onClick={() => setConfirmApply(true)}>Load into editor</Button>}
            </div>
          )}
        </div>
        {review.suggested_code ? (
          <div className="p-3"><CodeDiff original={review.code} modified={review.suggested_code} language={review.language} height={380} /></div>
        ) : (
          <p className="px-5 py-4 text-[13px] text-muted">Apply each recommended fix above by hand{review.ai_used ? "" : ", or enable AI to get a full corrected version"}.</p>
        )}
      </section>

      {/* Telemetry */}
      <section className="card p-5">
        <p className="eyebrow mb-3">Post-analysis telemetry</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            ["Lines of code", m.lines_code, `${m.lines_comment} comment`],
            ["Functions", m.functions, `${m.classes} class/type`],
            ["Max complexity", m.max_complexity ?? "n/a", m.avg_complexity != null ? `avg ${m.avg_complexity}` : "cyclomatic"],
            ["Max nesting", m.max_nesting, "block depth"],
          ].map(([k, v, s]) => (
            <div key={String(k)} className="rounded-lg border border-border bg-surface-2 px-3 py-2.5">
              <p className="font-display text-xl font-semibold tabular-nums">{v}</p>
              <p className="mt-0.5 text-[11px] text-muted">{k}</p>
              <p className="font-mono text-[10px] text-subtle">{s}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
          <p className="font-mono text-[10.5px] text-subtle">tools: {review.tools_used.join(" · ")}</p>
          <div className="flex gap-2">
            {review.saved && review.id ? (
              <>
                <Button size="sm" variant="ghost" icon={<Download className="h-3.5 w-3.5" />} onClick={() => downloadFromApi(`/history/reviews/${review.id}/export?format=md`, `${base}-review.md`)}>Report (.md)</Button>
                <Button size="sm" variant="ghost" icon={<FileJson className="h-3.5 w-3.5" />} onClick={() => downloadFromApi(`/history/reviews/${review.id}/export?format=json`, `${base}-review.json`)}>Export JSON</Button>
              </>
            ) : (
              <Button size="sm" variant="ghost" icon={<FileJson className="h-3.5 w-3.5" />} onClick={() => saveText(JSON.stringify(review, null, 2), `${base}-review.json`, "application/json")}>Download JSON</Button>
            )}
          </div>
        </div>
        <p className="mt-2 text-[11px] text-subtle">{review.saved ? "Saved to your review history." : "Not saved: history saving was off for this run."}</p>
      </section>

      <p className="flex gap-2 px-1 text-[11px] leading-relaxed text-subtle"><Info className="mt-px h-3.5 w-3.5 shrink-0" />{review.disclaimer}</p>

      <ConfirmDialog open={confirmApply} onClose={() => setConfirmApply(false)} confirmLabel="Replace editor content" title="Load suggested code into the editor?"
        message="This replaces the code in the editor with the suggested version. Your saved report keeps the original code. You can undo with Ctrl+Z in the editor."
        onConfirm={() => { onApplySuggested?.(review.suggested_code!); setConfirmApply(false); }} />
    </div>
  );
}
