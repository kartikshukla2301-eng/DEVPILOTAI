import { useCallback, useEffect, useState } from "react";
import { Gauge, ShieldCheck, Sparkles } from "lucide-react";
import { AIToggle } from "../components/AIToggle";
import { CodeWorkspace } from "../components/CodeWorkspace";
import { MOD_KEY } from "../components/layout/AppLayout";
import { OptimizeResults } from "../components/results/OptimizeResults";
import { Alert, Button, EmptyState, PageHeader, StatusChip } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useNotify } from "../context/NotificationContext";
import { api, errorMessage } from "../lib/api";
import { REVIEW_SAMPLES } from "../lib/samples";
import type { Language, OptimizeResult } from "../lib/types";
import { useDraft } from "../lib/useDraft";

export default function Optimizer() {
  const { settings } = useAuth();
  const { notify } = useNotify();
  const [code, setCode] = useDraft("opt.code", "");
  const [language, setLanguage] = useDraft<Language>("opt.lang", settings.default_language);
  const [filename, setFilename] = useDraft("opt.file", "");
  const [useAI, setUseAI] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OptimizeResult | null>(null);

  const run = useCallback(async () => {
    if (!code.trim()) return setError("Add some code to optimize.");
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<OptimizeResult>("/optimize", { code, language, filename: filename.trim() || null, use_ai: useAI });
      setResult(r.data);
      notify("success", "Optimization complete", { message: `${r.data.suggestions.length} suggestion(s)`, link: r.data.id ? `/history/optimize/${r.data.id}` : undefined });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [code, language, filename, useAI, notify]);

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
        eyebrow={<StatusChip tone="green">Optimization engine</StatusChip>}
        meta="before / after diff"
        title="Code Optimizer"
        description="Performance and readability improvements with a side-by-side comparison. Rewrites are applied to a copy; your original code is never overwritten."
        actions={<Button size="lg" className="glow-accent" loading={busy} icon={<Sparkles className="h-4 w-4" />} kbd={`${MOD_KEY}↵`} onClick={run}>{busy ? "Optimizing…" : "Optimize Code"}</Button>}
      />
      <div className="space-y-3">
        <CodeWorkspace code={code} setCode={setCode} language={language} setLanguage={setLanguage} filename={filename} setFilename={setFilename}
          sample={(l) => REVIEW_SAMPLES[l]} height="min(48vh, 480px)"
          toolbar={<>
            <span className="flex items-center gap-1.5 text-xs text-muted"><ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Original stays untouched</span>
            <div className="ml-auto"><AIToggle value={useAI} onChange={setUseAI} /></div>
          </>} />
        {error && <Alert tone="error">{error}</Alert>}
      </div>
      <div className="mt-6">
        {result ? <OptimizeResults result={result} /> : (
          <div className="card"><EmptyState icon={<Gauge className="h-6 w-6" />} title="No optimization yet" description="Run the optimizer to see suggested improvements and a side-by-side diff." /></div>
        )}
      </div>
    </>
  );
}
