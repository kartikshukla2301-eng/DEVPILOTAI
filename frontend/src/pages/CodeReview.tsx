import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Brush, Bug, FolderPlus, Gauge, Play, RotateCcw, ScanSearch, ShieldAlert } from "lucide-react";
import { AIToggle } from "../components/AIToggle";
import type { CodeEditorHandle } from "../components/CodeEditor";
import { CodeWorkspace } from "../components/CodeWorkspace";
import { MOD_KEY } from "../components/layout/AppLayout";
import { ProjectModal } from "../components/ProjectModal";
import { ReviewResults } from "../components/results/ReviewResults";
import { Alert, Button, EmptyState, PageHeader, StatusChip, Toggle } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useNotify } from "../context/NotificationContext";
import { api, errorMessage } from "../lib/api";
import { CATEGORIES } from "../lib/constants";
import { REVIEW_SAMPLES } from "../lib/samples";
import type { Category, Finding, Language, Project, Review } from "../lib/types";
import { useDraft } from "../lib/useDraft";
import { cn } from "../lib/utils";

const CAT_ICON: Record<Category, typeof Bug> = { bug: Bug, quality: Brush, security: ShieldAlert, performance: Gauge };
const ALL_CATS: Category[] = ["bug", "quality", "security", "performance"];

export default function CodeReview() {
  const { settings } = useAuth();
  const { notify } = useNotify();
  const [params, setParams] = useSearchParams();
  const [code, setCode] = useDraft("review.code", "");
  const [language, setLanguage] = useDraft<Language>("review.lang", settings.default_language);
  const [filename, setFilename] = useDraft("review.file", "");
  const [categories, setCategories] = useDraft<Category[]>("review.cats", ALL_CATS);
  const [projectId, setProjectId] = useDraft("review.project", "");
  const [useAI, setUseAI] = useState(true);
  const [save, setSave] = useState(true);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectOpen, setProjectOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [highlight, setHighlight] = useState<number | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const editor = useRef<CodeEditorHandle>(null);

  useEffect(() => {
    api.get<Project[]>("/projects").then((r) => {
      setProjects(r.data);
      if (projectId && !r.data.some((p) => p.id === projectId)) setProjectId("");
    }).catch(() => undefined);
    if (params.get("focus") === "security") {
      setCategories(["security"]);
      setParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleCat = (c: Category) => setCategories(categories.includes(c) ? categories.filter((x) => x !== c) : [...categories, c]);

  const run = useCallback(async () => {
    if (!code.trim()) return setError("Add some code to review first.");
    if (!categories.length) return setError("Select at least one analysis type.");
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<Review>("/code-review/analyze", {
        code, language, filename: filename.trim() || null, categories, project_id: projectId || null, use_ai: useAI, save,
      });
      setReview(r.data);
      setSelected(r.data.findings[0]?.id ?? null);
      setHighlight(null);
      const crit = r.data.summary.critical + r.data.summary.high;
      notify(crit ? "warning" : "success", `Review complete · score ${r.data.score}/100`, {
        message: `${r.data.findings.length} finding(s)${crit ? `, ${crit} critical/high` : ""} in ${r.data.filename}`,
        link: r.data.id ? `/history/review/${r.data.id}` : undefined,
      });
    } catch (e) {
      setError(errorMessage(e));
      notify("error", "Review failed", { message: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  }, [code, language, filename, categories, projectId, useAI, save, notify]);

  // Ctrl/⌘ + Enter runs the review
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && !busy) { e.preventDefault(); run(); }
    };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [run, busy]);

  const jump = (line: number) => {
    setHighlight(line);
    editor.current?.revealLine(line);
  };
  const onZoneClick = (f: Finding) => {
    setSelected(f.id);
    if (f.line) setHighlight(f.line);
  };

  const stale = review != null && review.code !== code;

  return (
    <>
      <PageHeader
        eyebrow={<StatusChip tone="accent" pulse>Intelligent code review</StatusChip>}
        meta={review ? `last run · ${review.filename}` : "workspace"}
        title="Code Review Workspace"
        description="Static analysis for bugs, quality, security and performance, with optional AI review. Findings appear inline in the editor and in the inspector."
        actions={<>
          {review && <Button variant="outline" icon={<RotateCcw className="h-4 w-4" />} onClick={() => { setReview(null); setHighlight(null); }}>Reset</Button>}
          <Button size="lg" loading={busy} className="glow-accent" icon={<Play className="h-4 w-4" />} kbd={`${MOD_KEY}↵`} onClick={run}>{busy ? "Analyzing…" : review ? "Re-run Review" : "Run Full Review"}</Button>
        </>}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(380px,5fr)]">
        <div className="min-w-0 space-y-3 xl:sticky xl:top-20 xl:self-start">
          <CodeWorkspace ref={editor} code={code} setCode={setCode} language={language} setLanguage={setLanguage} filename={filename} setFilename={setFilename}
            sample={(l) => REVIEW_SAMPLES[l]} height="min(66vh, 680px)" findings={review && !stale ? review.findings : undefined}
            inlineFindings onFindingClick={onZoneClick} highlightLine={highlight}
            toolbar={<>
              {CATEGORIES.map((c) => {
                const Icon = CAT_ICON[c.value];
                const on = categories.includes(c.value);
                return (
                  <button key={c.value} onClick={() => toggleCat(c.value)} aria-pressed={on} title={c.description}
                    className={cn("flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition-colors",
                      on ? "border-accent/50 bg-accent/12 text-accent-text" : "border-border text-subtle hover:text-text")}>
                    <Icon className="h-3.5 w-3.5" />{c.label}
                  </button>
                );
              })}
              <div className="ml-auto flex items-center gap-2">
                <select value={projectId} onChange={(e) => setProjectId(e.target.value)} aria-label="Project"
                  className="h-7 max-w-40 rounded-md border border-border bg-surface-2 px-2 text-xs text-muted outline-none">
                  <option value="">No project</option>
                  {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
                <button onClick={() => setProjectOpen(true)} className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-subtle hover:text-text" aria-label="New project" title="New project"><FolderPlus className="h-3.5 w-3.5" /></button>
              </div>
            </>}
          />
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface px-4 py-2.5">
            <Toggle checked={save} onChange={setSave} label={<span className="text-[13px]">Save to history</span>} />
            <AIToggle value={useAI} onChange={setUseAI} />
          </div>
          {stale && <Alert tone="info">The code changed since the last run. Inline markers are hidden; re-run the review to refresh them.</Alert>}
          {error && <Alert tone="error" title="Cannot run review">{error}</Alert>}
        </div>

        <div className="min-w-0">
          {review ? (
            <ReviewResults review={review} onJump={jump} selectedId={selected} onSelect={setSelected}
              onApplySuggested={(c) => { setCode(c); setReview(null); notify("info", "Suggested code loaded into the editor", { persist: false }); }} />
          ) : (
            <div className="card">
              <EmptyState icon={<ScanSearch className="h-6 w-6" />} title="Inspector is idle"
                description={<>Paste code, upload a file or load a sample, then click <span className="text-text">Run Full Review</span> (<span className="kbd">{MOD_KEY}↵</span>). The health score, prioritized action items and fixes appear here.</>} />
              <div className="grid grid-cols-2 gap-2 border-t border-border p-4">
                {CATEGORIES.map((c) => {
                  const Icon = CAT_ICON[c.value];
                  return (
                    <div key={c.value} className="rounded-lg border border-border bg-surface-2 p-3">
                      <Icon className="h-4 w-4 text-accent-text" />
                      <p className="mt-2 text-[13px] font-medium">{c.label}</p>
                      <p className="mt-0.5 text-xs text-muted">{c.description}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
      <ProjectModal open={projectOpen} onClose={() => setProjectOpen(false)} onSaved={(p) => { setProjects((ps) => [p, ...ps]); setProjectId(p.id); }} />
    </>
  );
}
