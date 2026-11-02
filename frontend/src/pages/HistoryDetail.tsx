import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Trash2 } from "lucide-react";
import { CodeEditor, EditorFrame, type CodeEditorHandle } from "../components/CodeEditor";
import { DebugResults } from "../components/results/DebugResults";
import { DocsResults } from "../components/results/DocsResults";
import { ExplainResults } from "../components/results/ExplainResults";
import { OptimizeResults } from "../components/results/OptimizeResults";
import { ReviewResults } from "../components/results/ReviewResults";
import { Alert, Button, Card, ConfirmDialog, PageLoader } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { api, errorMessage } from "../lib/api";
import { ACTIVITY_META, langLabel } from "../lib/constants";
import type { ActivityType, DebugResult, DocsResult, ExplainResult, OptimizeResult, Review } from "../lib/types";
import { formatDate } from "../lib/utils";

const ENDPOINT: Record<ActivityType, (id: string) => string> = {
  review: (id) => `/history/reviews/${id}`,
  debug: (id) => `/debug/sessions/${id}`,
  explain: (id) => `/explain/history/${id}`,
  optimize: (id) => `/optimize/history/${id}`,
  documentation: (id) => `/documentation/history/${id}`,
};

type AnyRecord = Record<string, unknown> & { id: string; title?: string; language: string; created_at: string; code?: string };

export default function HistoryDetail() {
  const { type, id } = useParams<{ type: ActivityType; id: string }>();
  const [data, setData] = useState<AnyRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [line, setLine] = useState<number | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const editor = useRef<CodeEditorHandle>(null);
  const navigate = useNavigate();
  const { notify } = useNotify();
  const valid = type && type in ENDPOINT && id;

  useEffect(() => {
    if (!valid) return;
    setData(null);
    api.get<AnyRecord>(ENDPOINT[type!](id!)).then((r) => setData(r.data)).catch((e) => setError(errorMessage(e)));
  }, [type, id, valid]);

  if (!valid) return <Alert tone="error" title="Unknown record type" />;
  if (error) return <div className="space-y-4"><BackLink /><Alert tone="error" title="Could not open this record">{error}</Alert></div>;
  if (!data) return <PageLoader />;

  const remove = async () => {
    setDeleting(true);
    try {
      await api.delete(`/history/activity/${type}/${id}`);
      notify("success", "Record deleted", { persist: false });
      navigate(type === "review" ? "/history" : "/history?tab=activity");
    } catch (e) {
      notify("error", "Could not delete", { message: errorMessage(e) });
      setDeleting(false);
    }
  };

  const jump = (l: number) => {
    setLine(l);
    editor.current?.revealLine(l);
  };

  const code = (data.code as string | undefined) ?? (data.original_code as string | undefined) ?? "";
  const lang = data.language as Review["language"];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <BackLink />
          <h1 className="mt-2 truncate text-xl font-semibold tracking-tight">{data.title ?? ACTIVITY_META[type!].label}</h1>
          <p className="mt-1 text-sm text-muted">{ACTIVITY_META[type!].label} · {langLabel(data.language)} · {formatDate(data.created_at)}</p>
        </div>
        <Button variant="outline" size="sm" icon={<Trash2 className="h-3.5 w-3.5" />} className="hover:text-red-400" onClick={() => setConfirm(true)}>Delete</Button>
      </div>

      {type === "review" && (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(380px,5fr)]">
          <div className="min-w-0 xl:sticky xl:top-20 xl:self-start">
            <EditorFrame filename={(data as unknown as Review).filename} language={langLabel(lang)}
              footer={<><span>read-only · saved snapshot</span><span>{(data as unknown as Review).findings.length} findings</span></>}>
              <CodeEditor ref={editor} bare value={code} language={lang} readOnly height="min(66vh, 680px)" findings={(data as unknown as Review).findings}
                inlineFindings onFindingClick={(f) => { setSelected(f.id); if (f.line) setLine(f.line); }} highlightLine={line} />
            </EditorFrame>
          </div>
          <div className="min-w-0"><ReviewResults review={{ ...(data as unknown as Review), saved: true }} onJump={jump} selectedId={selected} onSelect={setSelected} /></div>
        </div>
      )}
      {type === "debug" && (
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="space-y-4">
            <Card title="Submitted code"><CodeEditor value={code} language={lang} readOnly height={340} highlightLine={(data as unknown as DebugResult).location?.line} /></Card>
            <Card title="Error message"><pre className="overflow-x-auto whitespace-pre-wrap font-mono text-xs text-muted">{data.error_message as string}</pre>
              {data.context ? <p className="mt-3 text-[13px] text-muted"><span className="font-medium text-text">Context: </span>{data.context as string}</p> : null}</Card>
          </div>
          <DebugResults result={data as unknown as DebugResult} code={code} filename={(data.filename as string | undefined) ?? undefined} />
        </div>
      )}
      {type === "explain" && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card title="Code" className="xl:sticky xl:top-20 xl:self-start"><CodeEditor ref={editor} value={code} language={lang} readOnly height={520} highlightLine={line} /></Card>
          <ExplainResults result={data as unknown as ExplainResult} onLine={jump} activeLine={line} />
        </div>
      )}
      {type === "optimize" && <OptimizeResults result={data as unknown as OptimizeResult} />}
      {type === "documentation" && <DocsResults result={data as unknown as DocsResult} name={data.title} />}

      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} onConfirm={remove} loading={deleting} title="Delete record?" message="This will be permanently deleted." />
    </div>
  );
}

function BackLink() {
  return <Link to="/history" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-text"><ArrowLeft className="h-3.5 w-3.5" /> Back to history</Link>;
}
