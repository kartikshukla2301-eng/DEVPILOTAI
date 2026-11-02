import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpenText, GraduationCap, Sparkles } from "lucide-react";
import { AIToggle } from "../components/AIToggle";
import type { CodeEditorHandle } from "../components/CodeEditor";
import { CodeWorkspace } from "../components/CodeWorkspace";
import { MOD_KEY } from "../components/layout/AppLayout";
import { ExplainResults } from "../components/results/ExplainResults";
import { Alert, Button, EmptyState, PageHeader, StatusChip } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useNotify } from "../context/NotificationContext";
import { api, errorMessage } from "../lib/api";
import { EXPLAIN_SAMPLE } from "../lib/samples";
import type { ExplainResult, Language, Level } from "../lib/types";
import { useDraft } from "../lib/useDraft";
import { cn } from "../lib/utils";

const LEVELS: { value: Level; title: string; sub: string }[] = [
  { value: "beginner", title: "Beginner", sub: "Plain language" },
  { value: "intermediate", title: "Intermediate", sub: "Developer terms" },
  { value: "advanced", title: "Advanced", sub: "Semantics & cost" },
];

export default function Explainer() {
  const { settings } = useAuth();
  const { notify } = useNotify();
  const [code, setCode] = useDraft("explain.code", "");
  const [language, setLanguage] = useDraft<Language>("explain.lang", settings.default_language);
  const [filename, setFilename] = useDraft("explain.file", "");
  const [level, setLevel] = useDraft<Level>("explain.level", settings.explanation_level);
  const [useAI, setUseAI] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExplainResult | null>(null);
  const [active, setActive] = useState<number | null>(null);
  const editor = useRef<CodeEditorHandle>(null);

  const run = useCallback(async () => {
    if (!code.trim()) return setError("Add some code to explain.");
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<ExplainResult>("/explain", { code, language, level, filename: filename.trim() || null, use_ai: useAI });
      setResult(r.data);
      setActive(null);
      notify("success", "Explanation ready", { message: `${r.data.lines.length} lines explained · ${r.data.time_complexity}`, link: r.data.id ? `/history/explain/${r.data.id}` : undefined });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [code, language, level, filename, useAI, notify]);

  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !busy) { e.preventDefault(); run(); }
    };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [run, busy]);

  return (
    <>
      <PageHeader
        eyebrow={<StatusChip tone="accent">Semantic AST engine</StatusChip>}
        meta={result ? `${result.lines.length} lines · ${result.time_complexity}` : "line-by-line · big-O"}
        title="Code Explainer & Walkthrough"
        description="Understand unfamiliar code: purpose, line-by-line walkthrough, functions, variables, algorithm and estimated time and space complexity."
        actions={<Button size="lg" className="glow-accent" loading={busy} icon={<Sparkles className="h-4 w-4" />} kbd={`${MOD_KEY}↵`} onClick={run}>{busy ? "Explaining…" : "Explain Code"}</Button>}
      />

      <section className="card mb-5 flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-2 text-[13px] text-muted"><GraduationCap className="h-4 w-4 text-accent-text" /> Explanation level</span>
          <div className="inline-flex rounded-lg border border-border bg-bg p-0.5" role="tablist" aria-label="Explanation level">
            {LEVELS.map((l) => (
              <button key={l.value} role="tab" aria-selected={level === l.value} onClick={() => setLevel(l.value)}
                className={cn("rounded-md px-3.5 py-1.5 text-left transition-colors", level === l.value ? "bg-surface-3 ring-1 ring-border-strong" : "hover:bg-surface-3/50")}>
                <span className={cn("block text-[13px] font-medium", level === l.value ? "text-text" : "text-muted")}>{l.title}</span>
                <span className="block font-mono text-[10px] text-subtle">{l.sub}</span>
              </button>
            ))}
          </div>
        </div>
        <AIToggle value={useAI} onChange={setUseAI} />
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="min-w-0 space-y-3 xl:sticky xl:top-20 xl:self-start">
          <CodeWorkspace ref={editor} code={code} setCode={setCode} language={language} setLanguage={setLanguage} filename={filename} setFilename={setFilename}
            sample={(l) => EXPLAIN_SAMPLE[l]} height="min(64vh, 640px)" highlightLine={active} />
          {error && <Alert tone="error">{error}</Alert>}
        </div>
        <div className="min-w-0">
          {result ? <ExplainResults result={result} activeLine={active} onLine={(l) => { setActive(l); editor.current?.revealLine(l); }} /> : (
            <div className="card"><EmptyState icon={<BookOpenText className="h-6 w-6" />} title="Nothing explained yet"
              description="Paste code or load a sample, choose a level and click Explain Code. Click any explained line to jump to it in the editor." /></div>
          )}
        </div>
      </div>
    </>
  );
}
