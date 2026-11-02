import { useState } from "react";
import { Boxes, Clock, Cpu, Database, ListTree, Variable } from "lucide-react";
import type { ExplainResult } from "../../lib/types";
import { cn } from "../../lib/utils";
import { RichText } from "../Markdown";
import { Alert, Badge, EmptyState, ModeBadge, Tabs } from "../ui";

const LEVEL_LABEL = { beginner: "Beginner", intermediate: "Intermediate", advanced: "Advanced" } as const;

export function ExplainResults({ result, onLine, activeLine }: { result: ExplainResult; onLine?: (line: number) => void; activeLine?: number | null }) {
  const [tab, setTab] = useState<"lines" | "variables">("lines");
  const firstSentence = result.algorithm.replace(/^Uses\s+/i, "").split(/[.;]/)[0];
  const synopsisTitle = firstSentence ? firstSentence.charAt(0).toUpperCase() + firstSentence.slice(1) : "Code walkthrough";
  return (
    <div className="space-y-4">
      {/* Architectural synopsis */}
      <section className="card hero-gradient p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <p className="eyebrow">Architectural synopsis</p>
          <div className="flex gap-2"><Badge tone="blue" mono>{LEVEL_LABEL[result.level]}</Badge><ModeBadge ai={result.ai_used} error={result.ai_error} /></div>
        </div>
        <h2 className="mt-2 font-display text-[22px] font-semibold leading-tight tracking-[-0.015em]">{synopsisTitle}</h2>
        {result.ai_error && <div className="mt-3"><Alert tone="warning" title="AI unavailable">{result.ai_error}. Showing the local structural explanation.</Alert></div>}
        <p className="mt-3 text-[14px] leading-relaxed text-muted"><RichText text={result.purpose} /></p>
        <div className="mt-4 grid gap-2 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-surface-2/80 p-3.5">
            <p className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-subtle">Time complexity <Clock className="h-3.5 w-3.5 text-emerald-400" /></p>
            <p className="mt-1.5 font-mono text-lg font-semibold text-emerald-400">{result.time_complexity}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/80 p-3.5">
            <p className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-subtle">Space complexity <Database className="h-3.5 w-3.5 text-sky-400" /></p>
            <p className="mt-1.5 font-mono text-lg font-semibold text-sky-400">{result.space_complexity}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface-2/80 p-3.5">
            <p className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-subtle">Symbols <Cpu className="h-3.5 w-3.5 text-accent-text" /></p>
            <p className="mt-1.5 font-mono text-lg font-semibold text-accent-text">{result.functions.length} fn · {result.variables.length} var</p>
          </div>
        </div>
        <p className="mt-3 text-[13px] leading-relaxed"><span className="font-medium">Algorithm: </span><span className="text-muted"><RichText text={result.algorithm} /></span></p>
        <p className="mt-1 text-[11px] text-subtle">{result.complexity_note}</p>
      </section>

      {/* Functions as an ordered walkthrough */}
      <section className="card p-5">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="flex items-center gap-2 text-[15px] font-semibold"><Boxes className="h-4 w-4 text-accent-text" /> Functions & types</h3>
            <p className="mt-0.5 text-xs text-muted">What each building block does, in source order</p>
          </div>
          <span className="font-mono text-[11px] text-subtle">{result.functions.length} found</span>
        </div>
        {result.functions.length === 0 ? <p className="text-[13px] text-muted">No functions or types are defined; the code runs top to bottom.</p> : (
          <ol className="space-y-2.5">
            {[...result.functions].sort((a, b) => (a.line ?? 0) - (b.line ?? 0)).map((s, i) => (
              <li key={s.name + i} className="flex gap-3.5 rounded-lg border border-border bg-surface-2 p-3.5">
                <span className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-mono text-xs font-semibold", i % 2 ? "bg-accent/15 text-accent-text" : "bg-surface-3 text-text")}>{i + 1}</span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="font-mono text-[13.5px] font-semibold">{s.name}</code>
                    <Badge mono>{s.kind}</Badge>
                    {s.line && <button onClick={() => onLine?.(s.line!)} className="rounded-full bg-sky-400/10 px-2 py-0.5 font-mono text-[10px] text-sky-400 hover:bg-sky-400/20">Line {s.line}</button>}
                  </div>
                  <p className="mt-1 text-[13px] leading-relaxed text-muted"><RichText text={s.explanation} /></p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Line-by-line + variables */}
      <section className="card overflow-hidden">
        <div className="px-3">
          <Tabs value={tab} onChange={setTab} tabs={[
            { value: "lines", label: <span className="flex items-center gap-1.5"><ListTree className="h-3.5 w-3.5" /> Line by line</span>, count: result.lines.length },
            { value: "variables", label: <span className="flex items-center gap-1.5"><Variable className="h-3.5 w-3.5" /> Variables</span>, count: result.variables.length },
          ]} />
        </div>
        <div className="max-h-[620px] overflow-y-auto">
          {tab === "lines" && (result.lines.length ? (
            <ul>
              {result.lines.map((l) => (
                <li key={l.line}>
                  <button onClick={() => onLine?.(l.line)}
                    className={cn("grid w-full grid-cols-[2.75rem_minmax(0,1fr)] gap-3 border-b border-border px-4 py-2.5 text-left last:border-0 hover:bg-surface-3/60",
                      activeLine === l.line && "bg-accent-soft shadow-[inset_2px_0_0_var(--accent)]")}>
                    <span className="pt-0.5 text-right font-mono text-[11px] text-subtle">{l.line}</span>
                    <span className="min-w-0">
                      <code className="block truncate font-mono text-[12px] text-text/90">{l.code.trim()}</code>
                      <span className="mt-1 block text-[13px] leading-relaxed text-muted"><RichText text={l.explanation} /></span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : <EmptyState icon={<ListTree className="h-5 w-5" />} title="No lines to explain" />)}
          {tab === "variables" && (result.variables.length ? (
            <ul>
              {result.variables.map((s, i) => (
                <li key={s.name + i} className="flex gap-3 border-b border-border px-5 py-3 last:border-0">
                  <code className="w-32 shrink-0 truncate pt-0.5 font-mono text-[12.5px] font-semibold text-accent-text">{s.name}</code>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] leading-relaxed text-muted"><RichText text={s.explanation} /></p>
                    {s.line && <button onClick={() => onLine?.(s.line!)} className="mt-0.5 font-mono text-[10.5px] text-sky-400 hover:underline">line {s.line}</button>}
                  </div>
                </li>
              ))}
            </ul>
          ) : <EmptyState icon={<Variable className="h-5 w-5" />} title="No variables found" />)}
        </div>
      </section>
    </div>
  );
}
