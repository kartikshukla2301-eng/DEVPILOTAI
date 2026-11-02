import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { LANG_COLORS, SEVERITIES, SEVERITY_META, langLabel } from "../lib/constants";
import type { Language, Severity } from "../lib/types";

const tooltipStyle = {
  contentStyle: {
    background: "var(--overlay-bg)", backdropFilter: "blur(12px)", border: "1px solid var(--border-strong)", borderRadius: 10,
    fontSize: 12, color: "var(--text)", boxShadow: "var(--overlay-shadow)",
  },
  labelStyle: { color: "var(--muted)", marginBottom: 4, fontFamily: "JetBrains Mono, monospace", fontSize: 11 },
  itemStyle: { color: "var(--text)", padding: 0 },
  cursor: { fill: "var(--surface-3)", opacity: 0.5 },
};
const axis = { stroke: "var(--subtle)", fontSize: 10.5, tickLine: false, axisLine: false, fontFamily: "JetBrains Mono, monospace" } as const;

export function SeverityBarChart({ data, height = 220 }: { data: { severity: Severity; count: number }[]; height?: number }) {
  const rows = data.map((d) => ({ ...d, name: SEVERITY_META[d.severity].label }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
        <XAxis dataKey="name" {...axis} />
        <YAxis allowDecimals={false} {...axis} />
        <Tooltip {...tooltipStyle} formatter={(v) => [v, "Issues"]} />
        <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={40}>
          {rows.map((r) => <Cell key={r.severity} fill={SEVERITY_META[r.severity].color} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Horizontal segmented distribution bar with a percentage legend (design: "Issue Severity"). */
export function SeverityDistribution({ data }: { data: { severity: Severity; count: number }[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  const ordered = SEVERITIES.map((s) => ({ severity: s, count: data.find((d) => d.severity === s)?.count ?? 0 }));
  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-surface-3">
        {total > 0 && ordered.filter((d) => d.count).map((d) => (
          <div key={d.severity} style={{ width: `${(d.count / total) * 100}%`, background: SEVERITY_META[d.severity].color }} title={`${SEVERITY_META[d.severity].label}: ${d.count}`} />
        ))}
      </div>
      <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3">
        {ordered.map((d) => (
          <div key={d.severity} className="flex items-center justify-between text-[13px]">
            <span className="flex items-center gap-2 text-muted"><span className="h-2.5 w-2.5 rounded-full" style={{ background: SEVERITY_META[d.severity].color }} />{SEVERITY_META[d.severity].label}</span>
            <span className="font-mono text-xs tabular-nums text-text">{total ? Math.round((d.count / total) * 100) : 0}% <span className="text-subtle">· {d.count}</span></span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SeverityDonut({ data, height = 180 }: { data: { severity: Severity; count: number }[]; height?: number }) {
  const rows = data.filter((d) => d.count > 0).map((d) => ({ ...d, name: SEVERITY_META[d.severity].label }));
  if (!rows.length) return <div className="flex items-center justify-center text-[13px] text-muted" style={{ height }}>No issues found</div>;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={rows} dataKey="count" nameKey="name" innerRadius="60%" outerRadius="88%" paddingAngle={2} stroke="none">
          {rows.map((r) => <Cell key={r.severity} fill={SEVERITY_META[r.severity].color} />)}
        </Pie>
        <Tooltip {...tooltipStyle} />
      </PieChart>
    </ResponsiveContainer>
  );
}

/** Language chips with share percentages (design: "Active Languages"). */
export function LanguageChips({ data }: { data: { language: Language; count: number }[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  if (!total) return <p className="text-[13px] text-muted">No reviews yet.</p>;
  return (
    <div className="flex flex-wrap gap-2">
      {data.map((d) => (
        <span key={d.language} className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-2 px-2.5 py-1 text-xs">
          <span className="h-2 w-2 rounded-full" style={{ background: LANG_COLORS[d.language] ?? "#64748b" }} />
          {langLabel(d.language)}
          <span className="font-mono text-[10.5px] text-subtle">{Math.round((d.count / total) * 100)}%</span>
        </span>
      ))}
    </div>
  );
}

export function LanguagePie({ data, height = 220 }: { data: { language: Language; count: number }[]; height?: number }) {
  const rows = data.map((d) => ({ ...d, name: langLabel(d.language) }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={rows} dataKey="count" nameKey="name" innerRadius="58%" outerRadius="86%" paddingAngle={2} stroke="none">
          {rows.map((r) => <Cell key={r.language} fill={LANG_COLORS[r.language] ?? "#64748b"} />)}
        </Pie>
        <Tooltip {...tooltipStyle} />
      </PieChart>
    </ResponsiveContainer>
  );
}

/** Smooth area chart: analyses run vs. issues flagged per day (design: "Weekly Review Activity"). */
export function WeeklyActivityChart({ data, height = 260 }: { data: { label: string; date: string; total: number; findings: number }[]; height?: number }) {
  const today = data[data.length - 1]?.date;
  const rows = data.map((d) => ({ ...d, tick: d.date === today ? "TODAY" : d.label.toUpperCase() }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 10, right: 12, left: -22, bottom: 0 }}>
        <defs>
          <linearGradient id="gScans" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.45} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="gIssues" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fb7185" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#fb7185" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 4" />
        <XAxis dataKey="tick" {...axis} interval={0} />
        <YAxis allowDecimals={false} {...axis} />
        <Tooltip {...tooltipStyle}
          labelFormatter={(_, p) => (p?.[0]?.payload?.date ? new Date(p[0].payload.date + "T00:00").toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" }) : "")} />
        <Area type="monotone" dataKey="total" name="Analyses run" stroke="#a78bfa" strokeWidth={2.2} fill="url(#gScans)" dot={{ r: 3, fill: "#a78bfa", strokeWidth: 0 }} activeDot={{ r: 5 }} />
        <Area type="monotone" dataKey="findings" name="Issues flagged" stroke="#fb7185" strokeWidth={2} fill="url(#gIssues)" dot={false} activeDot={{ r: 4 }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ScoreTrendChart({ data, height = 200 }: { data: { date: string; score: number; title: string }[]; height?: number }) {
  const rows = data.map((d, i) => ({ ...d, idx: i + 1 }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}>
        <defs>
          <linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 4" />
        <XAxis dataKey="idx" {...axis} />
        <YAxis domain={[0, 100]} {...axis} />
        <Tooltip {...tooltipStyle} labelFormatter={(_, p) => p?.[0]?.payload?.title ?? ""} formatter={(v) => [v, "Score"]} />
        <Area type="monotone" dataKey="score" stroke="#38bdf8" strokeWidth={2} fill="url(#scoreFill)" dot={{ r: 3, fill: "#38bdf8", strokeWidth: 0 }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
