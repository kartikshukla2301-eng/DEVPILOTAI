import { Fragment, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  BookOpenText, Bug, ChevronDown, Download, ExternalLink, FileCode2, FileJson, FileText, Gauge, MessageSquareCode, ScanSearch,
  Search, ShieldAlert, ShieldCheck, Sparkles, Trash2, X,
} from "lucide-react";
import { Alert, Badge, Button, ConfirmDialog, EmptyState, PageHeader, Pagination, Select, Skeleton, Spinner, StatCard, StatusChip, Tabs } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { api, downloadFromApi, errorMessage } from "../lib/api";
import { ACTIVITY_META, LANGUAGES, LANG_COLORS, SEVERITIES, SEVERITY_META, langLabel, scoreColor } from "../lib/constants";
import type { ActivityItem, ActivityType, HistoryStats, Paginated, Project, Review, ReviewListItem } from "../lib/types";
import { cn, formatDate, timeAgo } from "../lib/utils";

const TYPE_ICON: Record<ActivityType, typeof ScanSearch> = { review: MessageSquareCode, debug: Bug, explain: BookOpenText, optimize: Gauge, documentation: FileText };

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function statusOf(r: ReviewListItem): { label: string; tone: "green" | "blue" | "yellow" | "red" } {
  if (r.summary.critical > 0) return { label: "Changes requested", tone: "red" };
  if (r.summary.high > 0) return { label: "Needs attention", tone: "yellow" };
  if (r.score >= 90) return { label: "Verified clean", tone: "green" };
  return { label: "Passed", tone: "blue" };
}

function ExpandedReview({ id }: { id: string }) {
  const [data, setData] = useState<Review | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.get<Review>(`/history/reviews/${id}`).then((r) => setData(r.data)).catch((e) => setErr(errorMessage(e))); }, [id]);
  if (err) return <div className="p-4"><Alert tone="error">{err}</Alert></div>;
  if (!data) return <div className="flex justify-center p-6"><Spinner /></div>;
  const top = data.findings.slice(0, 4);
  return (
    <div className="m-3 rounded-xl border border-border bg-surface-2 p-4 animate-fade-in">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 font-display text-[15px] font-semibold"><ShieldCheck className="h-4 w-4 text-emerald-400" /> Review summary</p>
          <p className="mt-1 font-mono text-[10.5px] text-subtle">id {data.id} · {data.tools_used.join(" · ")} · {data.metrics.lines_code} LOC</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" icon={<FileJson className="h-3.5 w-3.5" />} onClick={() => downloadFromApi(`/history/reviews/${id}/export?format=json`, "review.json")}>JSON</Button>
          <Link to={`/history/review/${id}`}><Button size="sm" icon={<ExternalLink className="h-3.5 w-3.5" />}>Open full report</Button></Link>
        </div>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {[["Category breakdown", Object.entries(data.category_summary).filter(([, v]) => v).map(([k, v]) => `${k} ${v}`).join(" · ") || "no findings"],
          ["Complexity", `max ${data.metrics.max_complexity ?? "n/a"} · nesting ${data.metrics.max_nesting}`],
          ["Suggested fix", data.suggested_code ? (data.suggested_code_source === "ai" ? "AI corrected version" : "Automatic safe fixes") : "Manual changes required"]].map(([k, v]) => (
          <div key={k} className="rounded-lg border border-border bg-surface px-3 py-2">
            <p className="eyebrow text-[9.5px]">{k}</p><p className="mt-0.5 truncate text-[12.5px]">{v}</p>
          </div>
        ))}
      </div>
      {top.length > 0 && (
        <div className="mt-3 overflow-hidden rounded-lg border border-border bg-bg font-mono text-[12px]">
          {top.map((f) => (
            <div key={f.id} className="flex items-center gap-3 border-b border-border px-3 py-2 last:border-0">
              <span className="w-10 shrink-0 text-right text-subtle">{f.line ?? "—"}</span>
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: SEVERITY_META[f.severity].color }} />
              <span className="min-w-0 flex-1 truncate font-sans text-[12.5px]">{f.title}</span>
              <span className="shrink-0 text-[10px] uppercase" style={{ color: SEVERITY_META[f.severity].color }}>{f.severity}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ReviewsTab({ onChanged }: { onChanged: () => void }) {
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [language, setLanguage] = useState(params.get("language") ?? "");
  const [severity, setSeverity] = useState(params.get("severity") ?? "");
  const [project, setProject] = useState(params.get("project") ?? "");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [data, setData] = useState<Paginated<ReviewListItem> | null>(null);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<ReviewListItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const q = useDebounced(search);
  const navigate = useNavigate();
  const { notify } = useNotify();

  const loadStats = useCallback(() => api.get<HistoryStats>("/history/stats").then((r) => setStats(r.data)).catch(() => undefined), []);
  useEffect(() => { api.get<Project[]>("/projects").then((r) => setProjects(r.data)).catch(() => undefined); loadStats(); }, [loadStats]);
  useEffect(() => setPage(1), [q, language, severity, project, sort, pageSize]);
  useEffect(() => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries({ q, language, severity, project })) { if (v) next.set(k, v); else next.delete(k); }
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, language, severity, project]);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await api.get<Paginated<ReviewListItem>>("/history/reviews", {
        params: { search: q || undefined, language: language || undefined, severity: severity || undefined, project_id: project || undefined, sort, page, page_size: pageSize },
      });
      setData(r.data);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [q, language, severity, project, sort, page, pageSize]);
  useEffect(() => { load(); }, [load]);

  const remove = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.delete(`/history/reviews/${toDelete.id}`);
      notify("success", "Review deleted", { persist: false });
      setToDelete(null);
      load(); loadStats(); onChanged();
    } catch (e) {
      notify("error", "Could not delete", { message: errorMessage(e) });
    } finally {
      setDeleting(false);
    }
  };

  const filtersActive = Boolean(search || language || severity || project);

  return (
    <>
      {stats && (
        <div className="grid gap-4 border-b border-border p-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total audited reviews" value={stats.total.toLocaleString()} icon={<FileCode2 className="h-4 w-4" />}
            hint={`${stats.findings.toLocaleString()} findings · ${stats.ai} AI-assisted`} />
          <StatCard label="Clean (no critical/high)" value={stats.clean.toLocaleString()} icon={<Sparkles className="h-4 w-4" />} accent="green"
            hint={<span className="text-emerald-400">{stats.total ? Math.round((stats.clean / stats.total) * 100) : 0}% of reviews · {stats.grade_a} grade A</span>}
            progress={stats.total ? (stats.clean / stats.total) * 100 : 0} />
          <div className="card p-4">
            <div className="flex items-start justify-between"><p className="eyebrow">Critical / high / medium</p><div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/12 text-red-400"><ShieldAlert className="h-4 w-4" /></div></div>
            <p className="mt-3 flex items-baseline gap-2 font-display text-[28px] font-semibold leading-none tabular-nums">
              <span className="text-rose-400">{stats.severity_totals.critical}</span><span className="text-subtle">/</span>
              <span className="text-orange-400">{stats.severity_totals.high}</span><span className="text-subtle">/</span>
              <span className="text-amber-400">{stats.severity_totals.medium}</span>
            </p>
            <div className="mt-4 flex h-1 gap-1">
              {(["critical", "high", "medium"] as const).map((s) => <div key={s} className="h-full rounded-full" style={{ flex: Math.max(1, stats.severity_totals[s]), background: SEVERITY_META[s].color }} />)}
            </div>
          </div>
          <StatCard label="Average health score" value={stats.avg_score ?? "—"} suffix="/ 100" valueColor={scoreColor(stats.avg_score)} icon={<ShieldCheck className="h-4 w-4" />} accent="blue"
            hint={stats.languages.map((l) => langLabel(l.language)).join(" · ") || "No languages yet"} progress={stats.avg_score ?? 0} />
        </div>
      )}

      <div className="space-y-3 border-b border-border p-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-56 flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
            <input className="input pl-8" placeholder="Filter by title or file name" value={search} onChange={(e) => setSearch(e.target.value)} maxLength={100} aria-label="Search reviews" />
          </div>
          <Select value={project} onChange={(e) => setProject(e.target.value)} className="w-44" aria-label="Project">
            <option value="">All projects ({projects.length})</option>
            {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
          <Select value={sort} onChange={(e) => setSort(e.target.value)} className="w-40" aria-label="Sort">
            <option value="newest">Newest first</option><option value="oldest">Oldest first</option>
            <option value="score_asc">Lowest score</option><option value="score_desc">Highest score</option>
          </Select>
          {filtersActive && <Button variant="ghost" size="sm" icon={<X className="h-3.5 w-3.5" />} onClick={() => { setSearch(""); setLanguage(""); setSeverity(""); setProject(""); }}>Clear</Button>}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="eyebrow mr-1">Severity</span>
            <button onClick={() => setSeverity("")} className={cn("rounded-full px-2.5 py-1 font-mono text-[11px] ring-1 ring-inset transition-colors", !severity ? "bg-surface-3 text-text ring-border-strong" : "text-subtle ring-border hover:text-text")}>
              All ({stats?.total ?? "…"})
            </button>
            {SEVERITIES.map((s) => (
              <button key={s} onClick={() => setSeverity(severity === s ? "" : s)}
                className={cn("flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] ring-1 ring-inset transition-colors", severity === s ? "bg-surface-3 text-text ring-border-strong" : "text-subtle ring-border hover:text-text")}>
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: SEVERITY_META[s].color }} />{SEVERITY_META[s].label} ({stats?.with_severity[s] ?? "…"})
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="eyebrow mr-1">Stack</span>
            {LANGUAGES.filter((l) => !stats || stats.languages.some((x) => x.language === l.value) || language === l.value).map((l) => (
              <button key={l.value} onClick={() => setLanguage(language === l.value ? "" : l.value)}
                className={cn("rounded-md px-2 py-1 text-[12px] transition-colors", language === l.value ? "bg-surface-3 text-text ring-1 ring-border-strong" : "text-muted hover:text-text")}>
                {l.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <div className="p-4"><Alert tone="error">{error}</Alert></div>}
      {!data ? (
        <div className="space-y-2 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : data.items.length === 0 ? (
        <EmptyState icon={<ScanSearch className="h-5 w-5" />} title={filtersActive ? "No reviews match your filters" : "No saved reviews yet"}
          description={filtersActive ? "Try a different search or clear the filters." : "Reviews you run with “Save to history” enabled appear here."}
          action={!filtersActive && <Link to="/review"><Button icon={<ScanSearch className="h-4 w-4" />}>Run a review</Button></Link>} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-left text-[13px]">
            <thead><tr className="border-b border-border bg-bg/40">
              <th className="eyebrow px-4 py-3 font-medium">Review ID & file</th><th className="eyebrow px-3 py-3 font-medium">Project & stack</th>
              <th className="eyebrow px-3 py-3 font-medium">Top finding</th><th className="eyebrow px-3 py-3 text-center font-medium">Health</th>
              <th className="eyebrow px-3 py-3 font-medium">Timestamp</th><th className="eyebrow px-4 py-3 text-right font-medium">Status & actions</th>
            </tr></thead>
            <tbody>
              {data.items.map((r) => {
                const st = statusOf(r);
                const proj = projects.find((p) => p.id === r.project_id);
                const isOpen = expanded === r.id;
                const tf = r.top_finding;
                return (
                  <Fragment key={r.id}>
                    <tr className={cn("border-b border-border hover:bg-surface-3/40", isOpen && "bg-surface-3/40", r.summary.critical > 0 && "bg-red-500/[0.03]")}>
                      <td className="px-4 py-3.5">
                        <p className="font-mono text-[12px] font-semibold">#REV-{r.id.slice(-6).toUpperCase()}</p>
                        <button onClick={() => navigate(`/history/review/${r.id}`)} className="mt-0.5 block max-w-56 truncate font-mono text-[11.5px] text-accent-text hover:underline">{r.filename}</button>
                      </td>
                      <td className="px-3 py-3.5">
                        <p className="max-w-48 truncate text-[13px]">{proj?.name ?? <span className="text-subtle">No project</span>}</p>
                        <p className="mt-0.5 flex items-center gap-1.5 text-[11.5px]"><span className="h-1.5 w-1.5 rounded-full" style={{ background: LANG_COLORS[r.language] }} /><span className="text-muted">{langLabel(r.language)}</span>{r.ai_used && <Badge tone="accent" mono>AI</Badge>}</p>
                      </td>
                      <td className="max-w-72 px-3 py-3.5">
                        {tf ? (
                          <>
                            <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase" style={{ color: SEVERITY_META[tf.severity].color, background: `${SEVERITY_META[tf.severity].color}18` }}>
                              {tf.severity} · {tf.category}
                            </span>
                            <p className="mt-1 line-clamp-2 text-[12.5px] text-muted">{tf.title}</p>
                          </>
                        ) : <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-emerald-400">Clean pass</span>}
                      </td>
                      <td className="px-3 py-3.5 text-center">
                        <span className="inline-flex h-11 w-11 flex-col items-center justify-center rounded-full font-mono text-[11px] font-semibold leading-tight ring-1 ring-inset"
                          style={{ color: scoreColor(r.score), background: `${scoreColor(r.score)}12`, boxShadow: `inset 0 0 0 1px ${scoreColor(r.score)}45` }}>
                          {r.score}<span className="text-[9px] opacity-80">{r.grade}</span>
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3.5">
                        <p className="text-[12.5px] text-muted">{timeAgo(r.created_at)}</p>
                        <p className="font-mono text-[10.5px] text-subtle">{formatDate(r.created_at)}</p>
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex items-center justify-end gap-1">
                          <Badge tone={st.tone} className="mr-1">{st.label}</Badge>
                          <Button size="icon" variant="ghost" title="Export Markdown" aria-label="Export Markdown" onClick={() => downloadFromApi(`/history/reviews/${r.id}/export?format=md`, "review.md")}><Download className="h-4 w-4" /></Button>
                          <Button size="icon" variant="ghost" title="Delete" aria-label="Delete" className="hover:text-red-400" onClick={() => setToDelete(r)}><Trash2 className="h-4 w-4" /></Button>
                          <Button size="icon" variant="ghost" title={isOpen ? "Collapse" : "Expand"} aria-label={isOpen ? "Collapse" : "Expand"} aria-expanded={isOpen} onClick={() => setExpanded(isOpen ? null : r.id)}>
                            <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                    {isOpen && <tr className="border-b border-border"><td colSpan={6}><ExpandedReview id={r.id} /></td></tr>}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {data && data.total > 0 && (
        <div className="flex flex-wrap items-center justify-between border-t border-border">
          <div className="flex-1"><Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} label="reviews" /></div>
          <label className="flex items-center gap-2 px-4 py-3 text-xs text-muted">Rows
            <select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))} className="rounded-md border border-border bg-surface-2 px-2 py-1 outline-none">
              {[10, 15, 25, 50].map((n) => <option key={n} value={n}>{n} per page</option>)}
            </select>
          </label>
        </div>
      )}
      <ConfirmDialog open={!!toDelete} onClose={() => setToDelete(null)} onConfirm={remove} loading={deleting} title="Delete review?"
        message={<>“{toDelete?.title}” will be permanently deleted. This cannot be undone.</>} />
    </>
  );
}

function ActivityTab() {
  const [type, setType] = useState<"all" | ActivityType>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<ActivityItem> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<ActivityItem | null>(null);
  const [deleting, setDeleting] = useState(false);
  const q = useDebounced(search);
  const navigate = useNavigate();
  const { notify } = useNotify();

  useEffect(() => setPage(1), [type, q]);
  const load = useCallback(async () => {
    try {
      const r = await api.get<Paginated<ActivityItem>>("/history/activity", { params: { type, search: q || undefined, page, page_size: 15 } });
      setData(r.data);
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [type, q, page]);
  useEffect(() => { load(); }, [load]);

  const remove = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.delete(`/history/activity/${toDelete.type}/${toDelete.id}`);
      notify("success", "Record deleted", { persist: false });
      setToDelete(null);
      load();
    } catch (e) {
      notify("error", "Could not delete", { message: errorMessage(e) });
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 border-b border-border p-4">
        <div className="relative min-w-56 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
          <input className="input pl-8" placeholder="Search by title" value={search} onChange={(e) => setSearch(e.target.value)} maxLength={100} aria-label="Search activity" />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {(["all", ...Object.keys(ACTIVITY_META)] as ("all" | ActivityType)[]).map((t) => (
            <button key={t} onClick={() => setType(t)} className={cn("rounded-full px-3 py-1.5 text-xs ring-1 ring-inset transition-colors", type === t ? "bg-surface-3 text-text ring-border-strong" : "text-subtle ring-border hover:text-text")}>
              {t === "all" ? "All modules" : ACTIVITY_META[t].label}
            </button>
          ))}
        </div>
      </div>
      {error && <div className="p-4"><Alert tone="error">{error}</Alert></div>}
      {!data ? (
        <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}</div>
      ) : data.items.length === 0 ? (
        <EmptyState icon={<FileText className="h-5 w-5" />} title="No activity found" description="Debugging sessions, explanations, optimizations and generated docs are stored here." />
      ) : (
        <ul>
          {data.items.map((a) => {
            const Icon = TYPE_ICON[a.type];
            return (
              <li key={`${a.type}-${a.id}`} className="flex items-center gap-3 border-b border-border px-4 py-3 last:border-0 hover:bg-surface-3/40">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-2 text-muted"><Icon className="h-4 w-4" /></div>
                <button className="min-w-0 flex-1 text-left" onClick={() => navigate(`${ACTIVITY_META[a.type].path}/${a.id}`)}>
                  <p className="truncate text-[13px] font-medium hover:text-accent-text">{a.title}</p>
                  <p className="font-mono text-[10.5px] text-subtle">{ACTIVITY_META[a.type].label}{a.language ? ` · ${langLabel(a.language)}` : ""}{a.level ? ` · ${a.level}` : ""}</p>
                </button>
                {a.score != null && <span className="font-mono text-[12px] font-semibold" style={{ color: scoreColor(a.score) }}>{a.score}</span>}
                {a.ai_used && <Badge tone="accent" mono>AI</Badge>}
                <span className="hidden whitespace-nowrap font-mono text-[10.5px] text-subtle sm:block" title={formatDate(a.created_at)}>{timeAgo(a.created_at)}</span>
                <Button size="icon" variant="ghost" aria-label="Delete" className="hover:text-red-400" onClick={() => setToDelete(a)}><Trash2 className="h-4 w-4" /></Button>
              </li>
            );
          })}
        </ul>
      )}
      {data && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} label="records" />}
      <ConfirmDialog open={!!toDelete} onClose={() => setToDelete(null)} onConfirm={remove} loading={deleting} title="Delete record?"
        message={<>This {toDelete ? ACTIVITY_META[toDelete.type].label.toLowerCase() : ""} record will be permanently deleted.</>} />
    </>
  );
}

export default function History() {
  const [params, setParams] = useSearchParams();
  const [, setTick] = useState(0);
  const navigate = useNavigate();
  const tab = params.get("tab") === "activity" ? "activity" : "reviews";
  return (
    <>
      <PageHeader
        eyebrow={<StatusChip tone="accent">Review ledger</StatusChip>}
        meta="stored in mongodb · per-user"
        title="Review History & Audit Trail"
        description="Every saved analysis, searchable and filterable. Open full reports, export them as Markdown or JSON, or delete records you no longer need."
        actions={<Button icon={<ScanSearch className="h-4 w-4" />} onClick={() => navigate("/review")}>Run new review</Button>}
      />
      <section className="card overflow-hidden">
        <div className="px-3">
          <Tabs value={tab} onChange={(t) => setParams(t === "activity" ? { tab: "activity" } : {}, { replace: true })}
            tabs={[{ value: "reviews", label: "Code reviews" }, { value: "activity", label: "All activity" }]} />
        </div>
        {tab === "reviews" ? <ReviewsTab onChanged={() => setTick((n) => n + 1)} /> : <ActivityTab />}
      </section>
    </>
  );
}
