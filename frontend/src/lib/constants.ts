import type { ActivityType, Category, Language, Severity } from "./types";

export const LANGUAGES: { value: Language; label: string; ext: string; monaco: string }[] = [
  { value: "python", label: "Python", ext: "py", monaco: "python" },
  { value: "javascript", label: "JavaScript", ext: "js", monaco: "javascript" },
  { value: "typescript", label: "TypeScript", ext: "ts", monaco: "typescript" },
  { value: "java", label: "Java", ext: "java", monaco: "java" },
  { value: "cpp", label: "C++", ext: "cpp", monaco: "cpp" },
  { value: "c", label: "C", ext: "c", monaco: "c" },
  { value: "go", label: "Go", ext: "go", monaco: "go" },
];

export const langLabel = (l?: string | null) => LANGUAGES.find((x) => x.value === l)?.label ?? l ?? "—";
export const langMonaco = (l: Language) => LANGUAGES.find((x) => x.value === l)?.monaco ?? "plaintext";
export const langExt = (l: Language) => LANGUAGES.find((x) => x.value === l)?.ext ?? "txt";

export const EXT_TO_LANG: Record<string, Language> = {
  py: "python", pyw: "python", js: "javascript", mjs: "javascript", cjs: "javascript", jsx: "javascript",
  ts: "typescript", tsx: "typescript", mts: "typescript", java: "java", c: "c", h: "c",
  cpp: "cpp", cc: "cpp", cxx: "cpp", hpp: "cpp", hh: "cpp", go: "go",
};

export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];

export const SEVERITY_META: Record<Severity, { label: string; color: string; badge: string; panel: string }> = {
  critical: { label: "Critical", color: "#ef4444", badge: "bg-red-500/10 text-red-400 ring-red-500/30 light:text-red-600", panel: "bg-red-500/10 text-red-400" },
  high: { label: "High", color: "#f97316", badge: "bg-orange-500/10 text-orange-400 ring-orange-500/30 light:text-orange-600", panel: "bg-orange-500/10 text-orange-400" },
  medium: { label: "Medium", color: "#f59e0b", badge: "bg-amber-500/10 text-amber-400 ring-amber-500/30 light:text-amber-700", panel: "bg-amber-500/10 text-amber-400" },
  low: { label: "Low", color: "#38bdf8", badge: "bg-sky-400/10 text-sky-400 ring-sky-400/30 light:text-sky-700", panel: "bg-sky-400/10 text-sky-400" },
  info: { label: "Info", color: "#64748b", badge: "bg-slate-500/10 text-slate-400 ring-slate-500/30 light:text-slate-600", panel: "bg-slate-500/10 text-slate-400" },
};

export const CATEGORIES: { value: Category; label: string; description: string }[] = [
  { value: "bug", label: "Bugs", description: "Syntax errors, runtime risks, logic issues" },
  { value: "quality", label: "Code quality", description: "Unused code, naming, complexity, duplication" },
  { value: "security", label: "Security", description: "Secrets, injection, dangerous functions" },
  { value: "performance", label: "Performance", description: "Inefficient loops and repeated work" },
];

export const LANG_COLORS: Record<Language, string> = {
  python: "#22c55e",
  javascript: "#f59e0b",
  typescript: "#38bdf8",
  java: "#f97316",
  cpp: "#8b5cf6",
  c: "#94a3b8",
  go: "#2dd4bf",
};

export const ACTIVITY_META: Record<ActivityType, { label: string; path: string }> = {
  review: { label: "Code review", path: "/history/review" },
  debug: { label: "Debugging", path: "/history/debug" },
  explain: { label: "Explanation", path: "/history/explain" },
  optimize: { label: "Optimization", path: "/history/optimize" },
  documentation: { label: "Documentation", path: "/history/documentation" },
};

export function scoreColor(score: number | null | undefined): string {
  if (score == null) return "#5f6883";
  if (score >= 90) return "#22c55e";
  if (score >= 80) return "#4ade80";
  if (score >= 70) return "#f59e0b";
  if (score >= 60) return "#f97316";
  return "#ef4444";
}
