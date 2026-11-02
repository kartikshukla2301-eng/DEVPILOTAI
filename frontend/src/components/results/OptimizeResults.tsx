import { useState } from "react";
import { BookOpen, Download, Gauge, Puzzle, ShieldCheck, Sparkles } from "lucide-react";
import { saveText } from "../../lib/api";
import { langExt } from "../../lib/constants";
import type { OptimizeResult, Suggestion } from "../../lib/types";
import { CodeDiff } from "../CodeEditor";
import { RichText } from "../Markdown";
import { Alert, Badge, Button, Card, CopyButton, EmptyState, ModeBadge, Segmented } from "../ui";

const KIND = {
  performance: { label: "Performance", icon: Gauge, tone: "accent" as const },
  readability: { label: "Readability", icon: BookOpen, tone: "blue" as const },
  pattern: { label: "Better pattern", icon: Puzzle, tone: "green" as const },
};
const IMPACT = { high: "red", medium: "yellow", low: "neutral" } as const;

function SuggestionItem({ s }: { s: Suggestion }) {
  const K = KIND[s.kind];
  return (
    <li className="rounded-lg border border-border bg-surface-2/50 p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <K.icon className="h-4 w-4 text-muted" />
        <span className="text-[13px] font-medium">{s.title}</span>
        <Badge tone={K.tone}>{K.label}</Badge>
        <Badge tone={IMPACT[s.impact]}>{s.impact} impact</Badge>
        {s.line && <Badge>line {s.line}</Badge>}
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-muted"><RichText text={s.description} /></p>
      {(s.before || s.after) && (
        <div className="mt-3 grid gap-2 md:grid-cols-2">
          {s.before && <div><p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-red-400">Before</p><pre className="overflow-x-auto rounded-md border border-red-500/20 bg-red-500/5 p-2.5 font-mono text-xs">{s.before}</pre></div>}
          {s.after && <div><p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-emerald-400">After</p><pre className="overflow-x-auto rounded-md border border-emerald-500/20 bg-emerald-500/5 p-2.5 font-mono text-xs">{s.after}</pre></div>}
        </div>
      )}
    </li>
  );
}

export function OptimizeResults({ result }: { result: OptimizeResult }) {
  const [filter, setFilter] = useState<"all" | Suggestion["kind"]>("all");
  const shown = result.suggestions.filter((s) => filter === "all" || s.kind === filter);
  return (
    <div className="space-y-4">
      <Card padded={false}>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3.5">
          <h2 className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-4 w-4 text-accent" /> Before / after comparison</h2>
          <div className="flex flex-wrap items-center gap-2">
            <ModeBadge ai={result.ai_used} error={result.ai_error} />
            {result.changed && <CopyButton text={result.optimized_code} label="Copy optimized" />}
            {result.changed && <Button size="sm" variant="outline" icon={<Download className="h-3.5 w-3.5" />} onClick={() => saveText(result.optimized_code, `optimized.${langExt(result.language)}`)}>Download</Button>}
          </div>
        </div>
        <div className="space-y-3 p-5">
          {result.ai_error && <Alert tone="warning" title="AI unavailable">{result.ai_error}. Showing local optimization rules.</Alert>}
          <p className="text-[13px] leading-relaxed text-muted">{result.summary}</p>
          <p className="flex items-center gap-1.5 text-xs text-subtle"><ShieldCheck className="h-3.5 w-3.5" /> Your original code is never overwritten. The optimized version is a separate copy for you to review.</p>
          {result.changed ? (
            <CodeDiff original={result.original_code} modified={result.optimized_code} language={result.language} height={440} />
          ) : (
            <Alert tone="info" title="No automatic rewrite applied">The suggestions below describe changes to make by hand.</Alert>
          )}
        </div>
      </Card>
      <Card title={`Suggestions (${result.suggestions.length})`}
        action={<Segmented size="sm" value={filter} onChange={setFilter} options={[
          { value: "all", label: "All" }, { value: "performance", label: "Performance" }, { value: "readability", label: "Readability" }, { value: "pattern", label: "Patterns" },
        ]} />}>
        {shown.length ? <ul className="space-y-2">{shown.map((s, i) => <SuggestionItem key={i} s={s} />)}</ul> : (
          <EmptyState icon={<Sparkles className="h-5 w-5" />} title="Nothing to suggest here" description="No issues of this type were detected." />
        )}
      </Card>
    </div>
  );
}
