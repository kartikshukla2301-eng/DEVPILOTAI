import { CheckCircle2, ListOrdered, MapPin, ShieldCheck, Sparkles, Wrench } from "lucide-react";
import type { DebugResult } from "../../lib/types";
import { CodeDiff } from "../CodeEditor";
import { RichText } from "../Markdown";
import { Alert, CopyButton, EmptyState, ModeBadge } from "../ui";

const CONF = {
  high: { color: "#22c55e", label: "High", pct: "≈ 90%+" },
  medium: { color: "#f59e0b", label: "Medium", pct: "≈ 60–80%" },
  low: { color: "#94a3b8", label: "Low", pct: "< 50%" },
};

export function DebugResults({ result, code, filename }: { result: DebugResult; code: string; filename?: string }) {
  const conf = CONF[result.confidence];
  const added = result.suggested_code ? result.suggested_code.split("\n").length - code.split("\n").length : 0;
  return (
    <div className="space-y-4">
      {/* Root cause banner */}
      <section className="card flex flex-wrap items-center gap-4 p-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-500/12 text-emerald-400 ring-1 ring-inset ring-emerald-500/30">
          <CheckCircle2 className="h-6 w-6" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-display text-lg font-semibold">Root Cause Identified</h2>
            <span className="rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ring-1 ring-inset" style={{ color: conf.color, background: `${conf.color}14`, boxShadow: `inset 0 0 0 1px ${conf.color}40` }}>
              Confidence: {conf.label}
            </span>
          </div>
          <p className="mt-0.5 text-[13px] text-muted">{result.ai_used ? "Diagnosed by AI, cross-checked with static analysis" : "Matched against the local error knowledge base and static analysis"}</p>
        </div>
        {result.location && (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-surface-2 px-3 py-2 font-mono text-[11.5px]">
            <MapPin className="h-4 w-4 text-rose-400" />
            <span className="text-subtle">File:</span><span className="text-accent-text">{filename || "snippet"}</span><span className="text-subtle">:</span><span className="text-rose-400">{result.location.line}</span>
          </div>
        )}
      </section>

      {/* Classification */}
      <section className="card relative overflow-hidden p-5 pl-6">
        <span className="absolute inset-y-0 left-0 w-1 bg-rose-400/80" />
        {result.ai_error && <div className="mb-4"><Alert tone="warning" title="AI unavailable">{result.ai_error}. Showing the local diagnosis.</Alert></div>}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[0.1em] text-rose-400"><Wrench className="h-3.5 w-3.5" /> Error classification</p>
          <ModeBadge ai={result.ai_used} error={result.ai_error} />
        </div>
        <h3 className="mt-2 font-display text-[26px] font-semibold leading-tight tracking-[-0.02em]">{result.error_type}</h3>
        <p className="mt-3 text-[14px] leading-relaxed text-muted"><RichText text={result.explanation} /></p>

        <div className="mt-4 rounded-lg border border-border bg-surface-2 p-3.5">
          <p className="eyebrow mb-1.5">Probable root cause</p>
          <div className="space-y-1.5 text-[13px] leading-relaxed">
            {result.root_cause.split("\n").filter(Boolean).map((ln, i) => (
              <p key={i} className={ln.startsWith("- ") ? "pl-3 text-muted" : ""}><RichText text={ln.replace(/^- /, "• ")} /></p>
            ))}
          </div>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-surface-2 px-3.5 py-3">
            <p className="font-mono text-[10px] uppercase tracking-wider text-subtle">Location</p>
            <p className="mt-1 font-display text-lg font-semibold text-amber-400">{result.location ? `Line ${result.location.line}` : "Not reported"}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2 px-3.5 py-3">
            <p className="font-mono text-[10px] uppercase tracking-wider text-subtle">Automatic fix</p>
            <p className="mt-1 font-display text-lg font-semibold" style={{ color: result.suggested_code ? "#22c55e" : "#94a3b8" }}>{result.suggested_code ? "Patch ready" : "Manual steps"}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2 px-3.5 py-3">
            <p className="font-mono text-[10px] uppercase tracking-wider text-subtle">Confidence</p>
            <p className="mt-1 font-display text-lg font-semibold" style={{ color: conf.color }}>{conf.label} <span className="text-xs font-normal text-subtle">{conf.pct}</span></p>
          </div>
        </div>

        {result.location && (
          <pre className="mt-4 overflow-x-auto rounded-lg border border-border bg-bg py-2 font-mono text-[12px] leading-[1.75]">
            {result.location.context.split("\n").map((ln, i) => {
              const n = Number(ln.split(":")[0]);
              const hit = n === result.location!.line;
              return (
                <div key={i} className={hit ? "flex items-center justify-between bg-rose-500/10 px-3 text-text shadow-[inset_2px_0_0_#fb7185]" : "px-3 text-subtle"}>
                  <span>{ln}</span>{hit && <span className="ml-4 shrink-0 rounded bg-rose-500/15 px-1.5 font-sans text-[10.5px] text-rose-400">Crash point</span>}
                </div>
              );
            })}
          </pre>
        )}
      </section>

      {/* Patch */}
      <section className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3.5">
          <h3 className="flex items-center gap-2 text-[15px] font-semibold">
            <Sparkles className="h-4 w-4 text-emerald-400" /> {result.ai_used ? "AI-Suggested Patch" : "Validated Patch"}
            {result.suggested_code && <span className="rounded-full bg-surface-3 px-2 py-0.5 font-mono text-[10.5px] text-muted">{added >= 0 ? `+${added}` : added} lines</span>}
          </h3>
          {result.suggested_code && <CopyButton text={result.suggested_code} label="Copy patch" />}
        </div>
        {result.suggested_code ? (
          <div className="p-3">
            <p className="mb-2 px-1 text-xs text-muted">{result.ai_used ? "Generated by AI. Verify before applying." : "Mechanical fix from the knowledge base; Python fixes are checked to parse."} Left: your code · Right: patched.</p>
            <CodeDiff original={code} modified={result.suggested_code} language={result.language} height={320} />
          </div>
        ) : (
          <EmptyState className="py-8" icon={<Wrench className="h-5 w-5" />} title="No automatic patch for this error"
            description="Follow the debugging steps below. With an AI key configured, DevPilot can propose a full corrected version." />
        )}
      </section>

      {/* Steps */}
      <section className="card p-5">
        <h3 className="mb-4 flex items-center gap-2 text-[15px] font-semibold"><ListOrdered className="h-4 w-4 text-accent-text" /> Step-by-step debugging</h3>
        <ol className="space-y-3">
          {result.steps.map((s, i) => (
            <li key={i} className="flex gap-3 text-[13.5px]">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-accent/15 font-mono text-[11px] font-semibold text-accent-text ring-1 ring-inset ring-accent/30">{i + 1}</span>
              <span className="pt-0.5 leading-relaxed"><RichText text={s} /></span>
            </li>
          ))}
        </ol>
      </section>

      {/* Prevention */}
      <section className="card p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-[15px] font-semibold"><ShieldCheck className="h-4 w-4 text-sky-400" /> Prevention & long-term resilience</h3>
          <span className="font-mono text-[10.5px] text-subtle">{result.prevention_tips.length} recommendation{result.prevention_tips.length === 1 ? "" : "s"}</span>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {result.prevention_tips.map((t, i) => (
            <div key={i} className="flex gap-3 rounded-lg border border-border bg-surface-2 p-3.5 text-[13px] leading-relaxed">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              <RichText text={t} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
