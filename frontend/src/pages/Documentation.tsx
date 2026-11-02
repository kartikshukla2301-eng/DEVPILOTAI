import { useCallback, useEffect, useState } from "react";
import { FileText, Sparkles } from "lucide-react";
import { AIToggle } from "../components/AIToggle";
import { CodeWorkspace } from "../components/CodeWorkspace";
import { MOD_KEY } from "../components/layout/AppLayout";
import { DocsResults } from "../components/results/DocsResults";
import { Alert, Button, EmptyState, PageHeader, StatusChip } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useNotify } from "../context/NotificationContext";
import { api, errorMessage } from "../lib/api";
import { EXPLAIN_SAMPLE } from "../lib/samples";
import type { DocsResult, Language } from "../lib/types";
import { useDraft } from "../lib/useDraft";

export default function Documentation() {
  const { settings } = useAuth();
  const { notify } = useNotify();
  const [code, setCode] = useDraft("docs.code", "");
  const [language, setLanguage] = useDraft<Language>("docs.lang", settings.default_language);
  const [filename, setFilename] = useDraft("docs.file", "");
  const [projectName, setProjectName] = useDraft("docs.name", "");
  const [useAI, setUseAI] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DocsResult | null>(null);

  const run = useCallback(async () => {
    if (!code.trim()) return setError("Add some code to document.");
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<DocsResult>("/documentation", { code, language, filename: filename.trim() || null, project_name: projectName.trim() || null, use_ai: useAI });
      setResult(r.data);
      notify("success", "Documentation generated", { message: projectName || filename || "Markdown ready to download", link: r.data.id ? `/history/documentation/${r.data.id}` : undefined });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }, [code, language, filename, projectName, useAI, notify]);

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
        eyebrow={<StatusChip tone="blue">Doc generator</StatusChip>}
        meta="markdown · downloadable"
        title="Documentation Generator"
        description="Generate Markdown docs with overview, classes, functions, parameters, return values, usage examples and dependencies."
        actions={<Button size="lg" className="glow-accent" loading={busy} icon={<Sparkles className="h-4 w-4" />} kbd={`${MOD_KEY}↵`} onClick={run}>{busy ? "Generating…" : "Generate Docs"}</Button>}
      />
      <div className="grid gap-5 xl:grid-cols-2">
        <div className="min-w-0 space-y-3 xl:sticky xl:top-20 xl:self-start">
          <CodeWorkspace code={code} setCode={setCode} language={language} setLanguage={setLanguage} filename={filename} setFilename={setFilename}
            sample={(l) => EXPLAIN_SAMPLE[l]} height="min(60vh, 600px)"
            toolbar={<>
              <input className="h-7 min-w-0 flex-1 rounded-md border border-border bg-surface-2 px-2.5 text-xs outline-none focus:border-accent" value={projectName} maxLength={100}
                onChange={(e) => setProjectName(e.target.value)} placeholder="Document title (optional), e.g. Payment utilities" aria-label="Document title" />
              <AIToggle value={useAI} onChange={setUseAI} />
            </>} />
          {error && <Alert tone="error">{error}</Alert>}
        </div>
        <div className="min-w-0">
          {result ? <DocsResults result={result} name={projectName || filename || "documentation"} /> : (
            <div className="card"><EmptyState icon={<FileText className="h-6 w-6" />} title="No documentation yet" description="Generated Markdown appears here with a live preview and a download button." /></div>
          )}
        </div>
      </div>
    </>
  );
}
