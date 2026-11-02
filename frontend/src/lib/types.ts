export type Language = "python" | "javascript" | "typescript" | "java" | "cpp" | "c" | "go";
export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type Category = "bug" | "quality" | "security" | "performance";
export type Level = "beginner" | "intermediate" | "advanced";
export type Theme = "dark" | "light" | "system";

export interface User {
  id: string;
  name: string;
  email: string;
  bio: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface UserSettings {
  theme: Theme;
  default_language: Language;
  explanation_level: Level;
  use_ai: boolean;
  updated_at?: string | null;
}

export interface AIStatus {
  ai_configured: boolean;
  mode: "ai" | "local";
  model: string | null;
  provider_host: string | null;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  language: Language | null;
  review_count: number;
  avg_score?: number | null;
  created_at: string;
  updated_at: string;
}

export interface Finding {
  id: string;
  category: Category;
  severity: Severity;
  title: string;
  description: string;
  recommendation: string;
  line: number | null;
  end_line?: number | null;
  column?: number | null;
  snippet?: string | null;
  rule?: string | null;
  source: "static" | "ai";
  tool: string;
}

export interface ReviewMetrics {
  lines_total: number;
  lines_code: number;
  lines_comment: number;
  functions: number;
  classes: number;
  max_complexity: number | null;
  avg_complexity: number | null;
  max_nesting: number;
}

export type SeverityCounts = Record<Severity, number>;

export interface Review {
  id: string | null;
  title: string;
  filename: string;
  language: Language;
  categories: Category[];
  score: number;
  grade: string;
  summary: SeverityCounts;
  category_summary: Record<Category, number>;
  findings: Finding[];
  metrics: ReviewMetrics;
  tools_used: string[];
  ai_used: boolean;
  ai_summary?: string | null;
  ai_error?: string | null;
  suggested_code?: string | null;
  suggested_code_source?: "static" | "ai" | null;
  code: string;
  project_id?: string | null;
  saved: boolean;
  created_at: string;
  disclaimer: string;
}

export interface ReviewListItem {
  id: string;
  title: string;
  filename: string;
  language: Language;
  score: number;
  grade: string;
  summary: SeverityCounts;
  total_findings: number;
  max_severity: Severity | null;
  ai_used: boolean;
  project_id: string | null;
  created_at: string;
  top_finding?: { title: string; severity: Severity; category: Category; line: number | null; source: "static" | "ai" } | null;
}

export interface HistoryStats {
  total: number;
  avg_score: number | null;
  findings: number;
  clean: number;
  grade_a: number;
  ai: number;
  with_severity: Record<Severity, number>;
  severity_totals: { critical: number; high: number; medium: number };
  languages: { language: Language; count: number }[];
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface DebugResult {
  id: string | null;
  language: Language;
  error_type: string;
  explanation: string;
  root_cause: string;
  location: { line: number; code: string; context: string } | null;
  steps: string[];
  suggested_code: string | null;
  prevention_tips: string[];
  confidence: "high" | "medium" | "low";
  ai_used: boolean;
  ai_error?: string | null;
  created_at: string;
  code?: string;
  error_message?: string;
  context?: string;
}

export interface LineExplanation {
  line: number;
  code: string;
  explanation: string;
}

export interface SymbolExplanation {
  name: string;
  kind: string;
  line: number | null;
  explanation: string;
}

export interface ExplainResult {
  id: string | null;
  language: Language;
  level: Level;
  purpose: string;
  lines: LineExplanation[];
  functions: SymbolExplanation[];
  variables: SymbolExplanation[];
  algorithm: string;
  time_complexity: string;
  space_complexity: string;
  complexity_note: string;
  ai_used: boolean;
  ai_error?: string | null;
  created_at: string;
  code?: string;
}

export interface Suggestion {
  kind: "performance" | "readability" | "pattern";
  title: string;
  description: string;
  line: number | null;
  before: string | null;
  after: string | null;
  impact: "high" | "medium" | "low";
}

export interface OptimizeResult {
  id: string | null;
  language: Language;
  original_code: string;
  optimized_code: string;
  changed: boolean;
  suggestions: Suggestion[];
  summary: string;
  ai_used: boolean;
  ai_error?: string | null;
  created_at: string;
}

export interface DocsResult {
  id: string | null;
  language: Language;
  markdown: string;
  symbols: Record<string, number>;
  ai_used: boolean;
  ai_error?: string | null;
  created_at: string;
  code?: string;
  title?: string;
}

export type ActivityType = "review" | "debug" | "explain" | "optimize" | "documentation";

export interface ActivityItem {
  id: string;
  type: ActivityType;
  title: string;
  language?: Language;
  created_at: string;
  score?: number;
  grade?: string;
  error_type?: string;
  ai_used?: boolean;
  level?: Level;
}

export interface DashboardSummary {
  is_empty: boolean;
  totals: {
    reviews: number;
    bugs: number;
    security_issues: number;
    quality_issues: number;
    performance_issues: number;
    avg_score: number | null;
    lines_analyzed: number;
    ai_reviews: number;
  };
  usage: {
    reviews: number;
    debug_sessions: number;
    explanations: number;
    optimizations: number;
    documentation: number;
    projects: number;
  };
  severity_distribution: { severity: Severity; count: number }[];
  language_distribution: { language: Language; count: number }[];
  weekly_activity: { date: string; label: string; reviews: number; debug: number; explain: number; other: number; total: number; findings: number }[];
  week_total: number;
  top_findings: {
    review_id: string; filename: string; language: Language; created_at: string; title: string; severity: Severity;
    category: Category; line: number | null; recommendation: string; snippet?: string | null; source: "static" | "ai";
  }[];
  score_trend: { date: string; score: number; title: string }[];
  recent_reviews: ReviewListItem[];
  recent_projects: Project[];
  recent_activity: ActivityItem[];
  ai_mode: "ai" | "local";
}
