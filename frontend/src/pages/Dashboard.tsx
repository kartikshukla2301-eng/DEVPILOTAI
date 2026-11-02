import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight, BookOpenText, Bug, FileCode2, FileText, FolderKanban, FolderPlus, Gauge, MessageSquareCode, RefreshCw,
  ScanSearch, ShieldAlert, ShieldCheck, Sparkles, Zap,
} from "lucide-react";
import { LanguageChips, ScoreTrendChart, SeverityDistribution, WeeklyActivityChart } from "../components/charts";
import { ProjectModal } from "../components/ProjectModal";
import { Alert, Badge, Button, Card, EmptyState, SeverityBadge, Skeleton, StatCard, StatusChip } from "../components/ui";
import { MOD_KEY } from "../components/layout/AppLayout";
import { useAuth } from "../context/AuthContext";
import { api, errorMessage } from "../lib/api";
import { ACTIVITY_META, LANG_COLORS, SEVERITY_META, langLabel, scoreColor } from "../lib/constants";
import type { ActivityType, DashboardSummary } from "../lib/types";
import { cn, timeAgo } from "../lib/utils";

const ACTIVITY_ICON: Record<ActivityType, typeof ScanSearch> = { review: MessageSquareCode, debug: Bug, explain: BookOpenText, optimize: Zap, documentation: FileText };

const MODULES = [
  { to: "/debug", title: "Debugging Assistant", desc: "Paste a stack trace to get the root cause, a step-by-step fix and corrected code.", icon: Bug, tone: "from-rose-500/20" },
  { to: "/explain", title: "Code Explainer", desc: "Line-by-line walkthroughs with algorithm detection and Big-O estimates.", icon: BookOpenText, tone: "from-sky-500/20" },
  { to: "/optimize", title: "Code Optimizer", desc: "Safe rewrites with a before/after diff. Your original code is never overwritten.", icon: Gauge, tone: "from-emerald-500/20" },
  { to: "/docs", title: "Doc Generator", desc: "Markdown docs with parameters, return values, examples and dependencies.", icon: FileText, tone: "from-violet-500/25" },
];

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function Dashboard() {
  const { user, aiActive } = useAuth();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [projectOpen, setProjectOpen] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await api.get<DashboardSummary>("/dashboard/summary", { params: { tz_offset_minutes: -new Date().getTimezoneOffset() } });
      setData(r.data);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (error) return <Alert tone="error" title="Could not load the dashboard">{error}</Alert>;
  if (!data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-44" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-40" />)}</div>
        <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-80 lg:col-span-2" /><Skeleton className="h-80" /></div>
      </div>
    );
  }

  const t = data.totals;
  const weekFindings = data.weekly_activity.reduce((s, d) => s + d.findings, 0);
  const totalFindings = data.severity_distribution.reduce((s, d) => s + d.count, 0);
  const critHigh = data.severity_distribution.filter((d) => d.severity === "critical" || d.severity === "high").reduce((s, d) => s + d.count, 0);

  const hero = (
    <section className="hero-gradient relative overflow-hidden rounded-2xl border border-border p-6 shadow-card sm:p-8">
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-60 [mask-image:radial-gradient(ellipse_at_top_left,black,transparent_70%)]" />
      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-2.5">
            <StatusChip tone={aiActive ? "accent" : "blue"} pulse>{aiActive ? "AI hybrid engine active" : "Static analysis engine active"}</StatusChip>
            <span className="font-mono text-[11px] text-subtle">ws: {user?.email.split("@")[0]}</span>
          </div>
          <h1 className="font-display text-[30px] font-semibold leading-tight tracking-[-0.02em] sm:text-[36px]">{greeting()}, {user?.name.split(" ")[0]}</h1>
          <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-muted">
            {data.is_empty ? (
              <>Your code intelligence workspace is ready. Run your first analysis to start tracking code health.</>
            ) : (
              <>Your workspace is ready. <span className="font-medium text-emerald-400">{data.week_total} analys{data.week_total === 1 ? "is" : "es"}</span> ran in the last 7 days, flagging {weekFindings.toLocaleString()} issue{weekFindings === 1 ? "" : "s"}.</>
            )}
          </p>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row lg:flex-col lg:items-end">
          <div className="flex gap-2">
            <Button variant="secondary" icon={<ShieldCheck className="h-4 w-4 text-rose-400" />} onClick={() => navigate("/review?focus=security")}>Run Security Audit</Button>
            <Button variant="secondary" icon={<FolderPlus className="h-4 w-4 text-sky-400" />} onClick={() => setProjectOpen(true)}>New Project</Button>
          </div>
          <Button size="lg" className="glow-accent" icon={<ScanSearch className="h-4 w-4" />} kbd={`${MOD_KEY}K`} onClick={() => navigate("/review")}>New Code Review</Button>
        </div>
      </div>
    </section>
  );

  if (data.is_empty) {
    return (
      <div className="space-y-6">
        {hero}
        <Card padded={false}>
          <EmptyState icon={<Sparkles className="h-6 w-6" />} title="No analyses yet"
            description={<>Statistics on this dashboard come only from your saved analyses. {aiActive ? "AI assistance is enabled." : "Local analysis mode: the static analyzers work without an AI key."}</>}
            action={<Button icon={<ScanSearch className="h-4 w-4" />} onClick={() => navigate("/review")}>Review your first file</Button>} />
        </Card>
        <ModuleCards />
        <ProjectModal open={projectOpen} onClose={() => setProjectOpen(false)} onSaved={load} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {hero}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Total reviews" value={t.reviews.toLocaleString()} icon={<FileCode2 className="h-4 w-4" />}
          hint={<span className="text-accent-text">{t.ai_reviews} AI-assisted · {t.reviews - t.ai_reviews} static</span>} progress={t.reviews ? 100 : 0} />
        <StatCard label="Critical & high issues" value={critHigh.toLocaleString()} valueColor={critHigh ? "#fb7185" : undefined} icon={<ShieldAlert className="h-4 w-4" />} accent="red"
          hint={critHigh ? "Need attention before merge" : "None detected"} progress={totalFindings ? (critHigh / totalFindings) * 100 : 0} />
        <StatCard label="Security vulnerabilities" value={t.security_issues.toLocaleString()} icon={<ShieldCheck className="h-4 w-4" />} accent="blue"
          hint={<span className="text-sky-400">Secrets, injection, unsafe APIs</span>} progress={totalFindings ? (t.security_issues / totalFindings) * 100 : 0} />
        <StatCard label="Avg quality score" value={t.avg_score ?? "—"} suffix="/ 100" valueColor={scoreColor(t.avg_score)} icon={<Sparkles className="h-4 w-4" />} accent="green"
          hint={t.avg_score == null ? "No reviews yet" : t.avg_score >= 80 ? "Healthy codebase" : t.avg_score >= 60 ? "Needs attention" : "At risk"} progress={t.avg_score ?? 0} />
        <StatCard label="Bugs detected" value={t.bugs.toLocaleString()} icon={<Bug className="h-4 w-4" />} accent="yellow"
          hint={`${t.lines_analyzed.toLocaleString()} lines analyzed`} progress={totalFindings ? (t.bugs / totalFindings) * 100 : 0} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2" title="Weekly Review Activity" subtitle="Analyses run vs. issues flagged, last 7 days"
          action={<div className="hidden items-center gap-4 font-mono text-[11px] text-muted sm:flex">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-violet-400" /> Analyses run</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-rose-400" /> Issues flagged</span>
          </div>}>
          <WeeklyActivityChart data={data.weekly_activity} />
        </Card>
        <Card title="Issue Severity" subtitle="Distribution across saved reviews" action={<span className="font-mono text-[11px] text-subtle">{totalFindings} total</span>}>
          <SeverityDistribution data={data.severity_distribution} />
          <div className="mt-7 border-t border-border pt-5">
            <div className="mb-3 flex items-center justify-between">
              <span className="eyebrow">Active languages</span>
              <span className="font-mono text-[11px] text-accent-text">{data.language_distribution.length} engine{data.language_distribution.length === 1 ? "" : "s"}</span>
            </div>
            <LanguageChips data={data.language_distribution} />
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2" padded={false} title="Recent Code Reviews" subtitle="Latest saved reports from your workspace"
          action={<Button size="sm" variant="ghost" icon={<RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />} onClick={load}>Refresh</Button>}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-[13px]">
              <thead><tr className="border-b border-border bg-bg/40">
                <th className="eyebrow px-5 py-3 font-medium">File / Review</th><th className="eyebrow px-3 py-3 font-medium">Lang</th>
                <th className="eyebrow px-3 py-3 font-medium">Score</th><th className="eyebrow px-3 py-3 font-medium">Issues</th><th className="eyebrow px-5 py-3 text-right font-medium">When</th>
              </tr></thead>
              <tbody>
                {data.recent_reviews.map((r) => (
                  <tr key={r.id} onClick={() => navigate(`/history/review/${r.id}`)} className="cursor-pointer border-b border-border last:border-0 hover:bg-surface-3/60">
                    <td className="max-w-72 px-5 py-3.5">
                      <p className="truncate font-mono text-[12.5px] text-accent-text">{r.filename}</p>
                      <p className="mt-0.5 truncate text-xs text-muted">{r.title}</p>
                    </td>
                    <td className="px-3 py-3.5"><span className="text-xs font-medium" style={{ color: LANG_COLORS[r.language] }}>{langLabel(r.language)}</span></td>
                    <td className="px-3 py-3.5">
                      <span className="inline-flex items-center rounded-md px-2 py-1 font-mono text-[11px] font-semibold ring-1 ring-inset"
                        style={{ color: scoreColor(r.score), background: `${scoreColor(r.score)}14`, boxShadow: `inset 0 0 0 1px ${scoreColor(r.score)}40` }}>
                        {r.score} / {r.grade}
                      </span>
                    </td>
                    <td className="px-3 py-3.5">
                      {r.summary.critical + r.summary.high > 0
                        ? <span className="rounded-md bg-red-500/12 px-2 py-1 font-mono text-[11px] text-red-400 ring-1 ring-inset ring-red-500/30">{r.summary.critical + r.summary.high} crit/high</span>
                        : <span className="font-mono text-[11px] text-subtle">{r.total_findings} minor</span>}
                    </td>
                    <td className="whitespace-nowrap px-5 py-3.5 text-right font-mono text-[11px] text-subtle">{timeAgo(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between border-t border-border px-5 py-3 text-xs text-muted">
            <span>Showing {data.recent_reviews.length} of {t.reviews} reviews</span>
            <Link to="/history" className="flex items-center gap-1 font-medium text-accent-text hover:underline">View all reviews <ArrowRight className="h-3.5 w-3.5" /></Link>
          </div>
        </Card>

        <Card title="Priority Findings" subtitle="Latest critical and high issues to fix first" icon={<ShieldAlert className="h-[18px] w-[18px]" />}
          action={data.top_findings.length ? <Badge tone="red" mono>{data.top_findings.length} open</Badge> : undefined}>
          {data.top_findings.length === 0 ? (
            <EmptyState className="py-6" icon={<ShieldCheck className="h-5 w-5" />} title="Nothing critical" description="No critical or high-severity findings in your saved reviews." />
          ) : (
            <div className="space-y-3">
              {data.top_findings.map((f, i) => (
                <div key={i} className="rounded-lg border border-border border-l-2 bg-surface-2 p-3" style={{ borderLeftColor: SEVERITY_META[f.severity].color }}>
                  <div className="flex items-center justify-between gap-2">
                    <SeverityBadge severity={f.severity} />
                    <span className="truncate font-mono text-[10.5px] text-subtle">{f.filename}{f.line ? `:${f.line}` : ""}</span>
                  </div>
                  <p className="mt-2 text-[13px] font-medium leading-snug">{f.title}</p>
                  <p className="mt-1 line-clamp-2 text-xs text-muted">{f.recommendation}</p>
                  <div className="mt-2.5 flex items-center justify-between">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">{f.source === "ai" ? "AI suggestion" : "Static analysis"} · {timeAgo(f.created_at)}</span>
                    <Button size="sm" variant="outline" className="h-7 px-2.5 text-xs" onClick={() => navigate(`/history/review/${f.review_id}`)}>Open report</Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Quality Score Trend" subtitle="Last 12 reviews">
          {data.score_trend.length > 1 ? <ScoreTrendChart data={data.score_trend} height={200} /> : <p className="py-14 text-center text-[13px] text-muted">Run at least two reviews to see a trend.</p>}
        </Card>
        <Card title="Recent Activity" padded={false} action={<Link to="/history?tab=activity" className="text-xs font-medium text-accent-text hover:underline">All activity</Link>}>
          <ul>
            {data.recent_activity.slice(0, 6).map((a) => {
              const Icon = ACTIVITY_ICON[a.type];
              return (
                <li key={`${a.type}-${a.id}`}>
                  <Link to={`${ACTIVITY_META[a.type].path}/${a.id}`} className="flex items-center gap-3 border-b border-border px-5 py-2.5 last:border-0 hover:bg-surface-3/60">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-3 text-muted"><Icon className="h-4 w-4" /></div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px]">{a.title}</p>
                      <p className="font-mono text-[10.5px] text-subtle">{ACTIVITY_META[a.type].label}{a.language ? ` · ${langLabel(a.language)}` : ""}</p>
                    </div>
                    <span className="whitespace-nowrap font-mono text-[10.5px] text-subtle">{timeAgo(a.created_at)}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Card>
        <Card title="Usage & Projects" action={<Button size="sm" variant="ghost" icon={<FolderPlus className="h-3.5 w-3.5" />} onClick={() => setProjectOpen(true)}>New</Button>}>
          <div className="grid grid-cols-3 gap-2">
            {[
              ["Reviews", data.usage.reviews], ["Debug", data.usage.debug_sessions], ["Explain", data.usage.explanations],
              ["Optimize", data.usage.optimizations], ["Docs", data.usage.documentation], ["Projects", data.usage.projects],
            ].map(([k, v]) => (
              <div key={String(k)} className="rounded-lg border border-border bg-surface-2 px-3 py-2.5">
                <p className="font-display text-xl font-semibold tabular-nums">{v}</p>
                <p className="eyebrow mt-0.5 text-[9.5px]">{k}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 space-y-1.5">
            {data.recent_projects.slice(0, 3).map((p) => (
              <Link key={p.id} to={`/history?project=${p.id}`} className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-surface-3">
                <FolderKanban className="h-4 w-4 text-sky-400" />
                <span className="flex-1 truncate text-[13px]">{p.name}</span>
                <span className="font-mono text-[11px] text-subtle">{p.review_count} rev</span>
                {p.avg_score != null && <span className="font-mono text-[11px] font-semibold" style={{ color: scoreColor(p.avg_score) }}>{p.avg_score}</span>}
              </Link>
            ))}
            {data.recent_projects.length === 0 && <p className="px-2 text-xs text-subtle">No projects yet. Group related reviews into projects.</p>}
          </div>
        </Card>
      </div>

      <ModuleCards />
      <ProjectModal open={projectOpen} onClose={() => setProjectOpen(false)} onSaved={load} />
    </div>
  );
}

function ModuleCards() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {MODULES.map(({ to, title, desc, icon: Icon, tone }) => (
        <Link key={to} to={to} className="card group overflow-hidden transition-all hover:-translate-y-0.5 hover:border-accent/40">
          <div className={cn("relative h-24 overflow-hidden border-b border-border bg-gradient-to-br to-transparent", tone)}>
            <div className="absolute inset-0 bg-grid opacity-70" />
            <Icon className="absolute bottom-4 left-5 h-8 w-8 text-text/80 transition-transform group-hover:scale-110" strokeWidth={1.5} />
            <ArrowRight className="absolute right-4 top-4 h-4 w-4 text-subtle transition-transform group-hover:translate-x-0.5 group-hover:text-accent-text" />
          </div>
          <div className="p-4">
            <p className="font-display text-[16px] font-semibold">{title}</p>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">{desc}</p>
          </div>
        </Link>
      ))}
    </div>
  );
}
