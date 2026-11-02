import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Brush, Bug, FileText, Sparkles, SquareTerminal, Wand2, Zap } from "lucide-react";
import { AIToggle } from "../components/AIToggle";
import { CodeWorkspace } from "../components/CodeWorkspace";
import { MOD_KEY } from "../components/layout/AppLayout";
import { DebugResults } from "../components/results/DebugResults";
import { Alert, Button, EmptyState, PageHeader, Select, StatusChip } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useNotify } from "../context/NotificationContext";
import { api, errorMessage } from "../lib/api";
import { LANGUAGES } from "../lib/constants";
import { DEBUG_SAMPLES } from "../lib/samples";
import type { DebugResult, Language } from "../lib/types";
import { useDraft } from "../lib/useDraft";

export default function Debugger() {
  const { settings } = useAuth();
  const { notify } = useNotify();
  const [code, setCode] = useDraft("debug.code", "");
  const [language, setLanguage] = useDraft<Language>("debug.lang", settings.default_language);
  const [filename, setFilename] = useDraft("debug.file", "");
  const [errorText, setErrorText] = useDraft("debug.error", "");
  const [context, setContext] = useDraft("debug.context", "");
  const [useAI, setUseAI] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DebugResult | null>(null);
  const [analyzedCode, setAnalyzedCode] = useState("");
  const [latency, setLatency] = useState<number | null>(null);

  const loadSample = () => {
    const s = DEBUG_SAMPLES[language];
    setCode(s.code);
    setErrorText(s.error);
    setContext("");
    setFilename("");
  };

  const run = useCallback(async () => {
    if (!code.trim()) return setError("Paste the code that produces the error.");
    if (!errorText.trim()) return setError("Paste the error message or stack trace.");
    setBusy(true);
    setError(null);
    const t0 = performance.now();
    try {
      const r = await api.post<DebugResult>("/debug", { code, language, filename: filename.trim() || null, error_message: errorText, context, use_ai: useAI });
      setLatency((performance.now() - t0) / 1000);
      setResult(r.data);
      setAnalyzedCode(code);
      notify("success", `Diagnosed: ${r.data.error_type}`, { message: r.data.suggested_code ? "A patch is available." : "See the debugging steps.", link: r.data.id ? `/history/debug/${r.data.id}` : undefined });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [code, language, filename, errorText, context, useAI, notify]);

  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !busy) { e.preventDefault(); run(); }
    };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [run, busy]);

  const errLines = errorText.split("\n").filter((l) => l.trim()).length;

  return (
    <>
      <PageHeader
        eyebrow={<StatusChip tone="accent" pulse>{useAI ? "Heuristic + AI engine" : "Heuristic engine active"}</StatusChip>}
        meta={result?.id ? `session id: #${result.id.slice(-8)}` : "new session"}
        title="Smart Debugging Assistant"
        description="Paste stack traces, runtime errors or broken snippets to diagnose root causes and get validated patches."
        actions={
          <div className="flex gap-2">
            <div className="flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-2.5">
              <Zap className="h-5 w-5 text-emerald-400" />
              <div><p className="eyebrow text-[9.5px]">Solve latency</p><p className="font-display text-lg font-semibold tabular-nums">{latency != null ? `${latency.toFixed(2)}s` : "—"}</p></div>
            </div>
            <div className="flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-2.5">
              <Sparkles className="h-5 w-5 text-sky-400" />
              <div><p className="eyebrow text-[9.5px]">Confidence</p><p className="font-display text-lg font-semibold capitalize text-sky-400">{result?.confidence ?? "—"}</p></div>
            </div>
          </div>
        }
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <div className="min-w-0 space-y-4">
          <section className="card p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-[14px] font-semibold"><SquareTerminal className="h-4 w-4 text-muted" /> Execution environment</h3>
              <Button size="sm" variant="ghost" icon={<Wand2 className="h-3.5 w-3.5" />} onClick={loadSample}>Load example</Button>
            </div>
            <Select value={language} onChange={(e) => setLanguage(e.target.value as Language)} aria-label="Language">
              {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
            </Select>
          </section>

          <section className="card overflow-hidden">
            <div className="flex items-center justify-between px-4 pb-2 pt-4">
              <h3 className="flex items-center gap-2 text-[14px] font-semibold"><AlertCircle className="h-4 w-4 text-rose-400" /> Error output / terminal stack trace</h3>
              {errorText && <button onClick={() => setErrorText("")} className="flex items-center gap-1 text-xs text-subtle hover:text-text"><Brush className="h-3.5 w-3.5" /> Clear</button>}
            </div>
            <div className="mx-4 mb-4 overflow-hidden rounded-lg border border-border bg-bg">
              <div className="flex items-center justify-between border-b border-border px-3 py-1.5 font-mono text-[11px]">
                <span className="flex items-center gap-2 text-rose-400"><span className="h-2 w-2 rounded-full bg-rose-400" /> STDERR capture</span>
                <span className="text-subtle">{errLines} line{errLines === 1 ? "" : "s"} parsed</span>
              </div>
              <textarea value={errorText} onChange={(e) => setErrorText(e.target.value)} spellCheck={false} maxLength={20000} aria-label="Error message"
                placeholder={"Traceback (most recent call last):\n  File \"main.py\", line 4, in <module>\nNameError: name 'x' is not defined"}
                className="block min-h-36 w-full resize-y bg-transparent px-3 py-2.5 font-mono text-[12px] leading-relaxed text-rose-300 outline-none placeholder:text-subtle light:text-rose-700" />
            </div>
          </section>

          <CodeWorkspace code={code} setCode={setCode} language={language} setLanguage={setLanguage} filename={filename} setFilename={setFilename}
            height={330} highlightLine={result && analyzedCode === code ? result.location?.line : null} />

          <section className="card p-4">
            <h3 className="mb-2 flex items-center gap-2 text-[14px] font-semibold"><FileText className="h-4 w-4 text-muted" /> Context & environment notes</h3>
            <textarea className="input min-h-20 resize-y" value={context} onChange={(e) => setContext(e.target.value)} maxLength={5000}
              placeholder="Optional: what you expected, recent changes, inputs, when it happens…" />
          </section>

          {error && <Alert tone="error">{error}</Alert>}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <AIToggle value={useAI} onChange={setUseAI} />
          </div>
          <Button size="lg" className="glow-accent h-13 w-full text-base" loading={busy} icon={<Sparkles className="h-5 w-5" />} kbd={`${MOD_KEY}↵`} onClick={run}>
            {busy ? "Diagnosing…" : "Diagnose & Generate Fix"}
          </Button>
        </div>

        <div className="min-w-0">
          {result ? <DebugResults result={result} code={analyzedCode} filename={filename} /> : (
            <div className="card h-full min-h-96">
              <EmptyState className="h-full" icon={<Bug className="h-6 w-6" />} title="Awaiting a stack trace"
                description="Provide the failing code and the exact error output. DevPilot classifies the error, pinpoints the crash line and proposes a patch." />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
