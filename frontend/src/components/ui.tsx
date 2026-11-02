import { forwardRef, useEffect, useState, type ButtonHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { Check, ChevronDown, ChevronLeft, ChevronRight, Copy, Cpu, Loader2, X } from "lucide-react";
import { SEVERITY_META, scoreColor } from "../lib/constants";
import type { Severity } from "../lib/types";
import { cn, copyToClipboard } from "../lib/utils";

/* ------------------------------------------------------------------ Button */
type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline" | "success";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2)] hover:bg-accent-hover hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_0_16px_rgba(139,92,246,0.4)]",
  secondary: "bg-surface-3 text-text border border-border hover:border-border-strong",
  outline: "border border-border text-muted hover:bg-surface-3 hover:border-border-strong hover:text-text",
  ghost: "text-muted hover:bg-surface-3 hover:text-text",
  danger: "bg-red-500/90 text-white hover:bg-red-500",
  success: "bg-emerald-600 text-white hover:bg-emerald-500 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md" | "lg" | "icon";
  loading?: boolean;
  icon?: ReactNode;
  /** Keyboard hint rendered as a mono chip, e.g. "⌘↵". */
  kbd?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon, kbd, className, children, disabled, ...rest }, ref,
) {
  const sizes = { sm: "h-8 px-3 text-[13px] gap-1.5", md: "h-9 px-3.5 text-sm gap-2", lg: "h-11 px-5 text-[15px] gap-2", icon: "h-9 w-9 justify-center" };
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex select-none items-center justify-center rounded-lg font-medium transition-all duration-150 active:scale-[.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none disabled:active:scale-100",
        VARIANTS[variant], sizes[size], className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
      {kbd && <span className="kbd ml-1">{kbd}</span>}
    </button>
  );
});

/* ------------------------------------------------------------------ Card */
export function Card({ className, children, title, action, subtitle, padded = true, icon }: {
  className?: string; children: ReactNode; title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; padded?: boolean; icon?: ReactNode;
}) {
  return (
    <section className={cn("card", className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-3.5">
          <div className="flex min-w-0 items-start gap-2.5">
            {icon && <span className="mt-0.5 text-accent-text">{icon}</span>}
            <div className="min-w-0">
              {title && <h3 className="text-[15px] font-semibold">{title}</h3>}
              {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
            </div>
          </div>
          {action}
        </header>
      )}
      <div className={cn(padded && "p-5")}>{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ Badges */
export type Tone = "neutral" | "accent" | "blue" | "green" | "red" | "yellow";
const TONES: Record<Tone, string> = {
  neutral: "bg-surface-3 text-muted ring-border",
  accent: "bg-accent/12 text-accent-text ring-accent/35",
  blue: "bg-sky-400/10 text-sky-400 ring-sky-400/30 light:text-sky-700",
  green: "bg-emerald-500/10 text-emerald-400 ring-emerald-500/30 light:text-emerald-700",
  red: "bg-red-500/10 text-red-400 ring-red-500/30 light:text-red-600",
  yellow: "bg-amber-500/10 text-amber-400 ring-amber-500/30 light:text-amber-700",
};

export function Badge({ children, className, tone = "neutral", mono }: { children: ReactNode; className?: string; tone?: Tone; mono?: boolean }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
      mono && "font-mono text-[10px] uppercase tracking-[0.05em]", TONES[tone], className,
    )}>{children}</span>
  );
}

/** Uppercase mono "eyebrow" chip, e.g. "HEURISTIC ENGINE ACTIVE". */
export function StatusChip({ children, tone = "accent", pulse }: { children: ReactNode; tone?: Tone; pulse?: boolean }) {
  return (
    <Badge tone={tone} mono>
      <span className="relative flex h-1.5 w-1.5">
        {pulse && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />}
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-current" />
      </span>
      {children}
    </Badge>
  );
}

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const m = SEVERITY_META[severity];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.06em] ring-1 ring-inset", m.badge, className)}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: m.color }} />
      {m.label}
    </span>
  );
}

export function SourceBadge({ source }: { source: "static" | "ai" }) {
  return source === "ai" ? (
    <StatusChip tone="accent" pulse>AI suggestion</StatusChip>
  ) : (
    <Badge tone="blue" mono><Cpu className="h-3 w-3" /> Static</Badge>
  );
}

/** Shows whether a result came from AI or local analysis. */
export function ModeBadge({ ai, error }: { ai: boolean; error?: string | null }) {
  if (ai) return <StatusChip tone="accent" pulse>AI-assisted</StatusChip>;
  return (
    <span title={error ? `AI unavailable: ${error}` : "Local rule-based analysis"}>
      <Badge tone={error ? "yellow" : "blue"} mono><Cpu className="h-3 w-3" /> {error ? "Local · AI failed" : "Local engine"}</Badge>
    </span>
  );
}

/* ------------------------------------------------------------------ Form controls */
export function Field({ label, error, hint, children, htmlFor }: { label: string; error?: string; hint?: string; children: ReactNode; htmlFor?: string }) {
  return (
    <div>
      <label className="label" htmlFor={htmlFor}>{label}</label>
      {children}
      {error ? <p className="mt-1 text-xs text-red-400">{error}</p> : hint ? <p className="mt-1 text-xs text-subtle">{hint}</p> : null}
    </div>
  );
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={cn("relative", className)}>
      <select {...rest} className="input appearance-none pr-8">{children}</select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
    </div>
  );
}

export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-[13px] text-muted hover:text-text">
      <button type="button" role="checkbox" aria-checked={checked} onClick={() => onChange(!checked)}
        className={cn("flex h-4 w-4 items-center justify-center rounded border transition-colors", checked ? "border-accent bg-accent" : "border-border-strong bg-bg")}>
        {checked && <Check className="h-3 w-3 text-white" strokeWidth={3} />}
      </button>
      {label}
    </label>
  );
}

export function Toggle({ checked, onChange, label, disabled, description }: { checked: boolean; onChange: (v: boolean) => void; label?: ReactNode; disabled?: boolean; description?: ReactNode }) {
  return (
    <label className={cn("flex cursor-pointer items-center gap-2.5", disabled && "cursor-not-allowed opacity-50")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn("relative h-5 w-9 shrink-0 rounded-full transition-colors duration-75", checked ? "bg-accent" : "bg-border")}
      >
        <span className={cn("absolute left-0 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-75", checked ? "translate-x-4" : "translate-x-0.5")} />
      </button>
      {(label || description) && (
        <span className="min-w-0">
          {label && <span className="block text-sm">{label}</span>}
          {description && <span className="block text-xs text-muted">{description}</span>}
        </span>
      )}
    </label>
  );
}

export function Segmented<T extends string>({ value, onChange, options, size = "md", className }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[]; size?: "sm" | "md"; className?: string }) {
  return (
    <div className={cn("inline-flex rounded-lg border border-border bg-bg p-0.5", className)} role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md font-medium transition-colors",
            size === "sm" ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-[13px]",
            value === o.value ? "bg-surface-3 text-text shadow-sm ring-1 ring-border-strong" : "text-subtle hover:text-text",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** IDE-style tabs: active tab gets a 2px violet stroke. */
export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: { value: T; label: ReactNode; count?: number }[] }) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-border" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.value}
          role="tab"
          aria-selected={value === t.value}
          onClick={() => onChange(t.value)}
          className={cn(
            "-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] font-medium transition-colors",
            value === t.value ? "border-accent text-text" : "border-transparent text-subtle hover:text-text",
          )}
        >
          {t.label}
          {t.count != null && <span className="rounded-full bg-surface-3 px-1.5 font-mono text-[10px] text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ Feedback */
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin text-accent", className)} />;
}

export function PageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-64 flex-col items-center justify-center gap-3 text-sm text-muted">
      <Spinner className="h-6 w-6" />
      {label}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-surface-3", className)} />;
}

export function EmptyState({ icon, title, description, action, className }: { icon: ReactNode; title: string; description?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-12 text-center", className)}>
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-accent/25 bg-accent-soft text-accent-text">{icon}</div>
      <h3 className="text-[15px] font-semibold">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-[13px] text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Alert({ tone = "info", title, children, icon }: { tone?: "info" | "warning" | "error" | "success"; title?: ReactNode; children?: ReactNode; icon?: ReactNode }) {
  const tones = {
    info: "border-sky-400/25 bg-sky-400/[0.07]",
    warning: "border-amber-500/30 bg-amber-500/[0.08]",
    error: "border-red-500/30 bg-red-500/[0.08]",
    success: "border-emerald-500/30 bg-emerald-500/[0.08]",
  };
  return (
    <div className={cn("flex gap-3 rounded-lg border px-3.5 py-3 text-[13px]", tones[tone])}>
      {icon && <div className="mt-0.5 shrink-0">{icon}</div>}
      <div className="min-w-0">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn("text-muted", title ? "mt-0.5" : "")}>{children}</div>}
      </div>
    </div>
  );
}

/** Page hero: status chip eyebrow, large Geist title, description, optional right-side actions/metrics. */
export function PageHeader({ title, description, actions, eyebrow, meta }: { title: string; description?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode; meta?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        {(eyebrow || meta) && (
          <div className="mb-2.5 flex flex-wrap items-center gap-2.5">
            {eyebrow}
            {meta && <span className="font-mono text-[11px] uppercase tracking-[0.06em] text-subtle">{meta}</span>}
          </div>
        )}
        <h1 className="font-display text-[28px] font-semibold leading-tight tracking-[-0.02em] sm:text-[32px]">{title}</h1>
        {description && <p className="mt-2 max-w-3xl text-[15px] leading-relaxed text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 lg:justify-end">{actions}</div>}
    </div>
  );
}

export function CopyButton({ text, label = "Copy", size = "sm", variant = "outline" }: { text: string; label?: string; size?: "sm" | "md"; variant?: Variant }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      size={size}
      variant={variant}
      icon={done ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
      onClick={async () => {
        if (await copyToClipboard(text)) {
          setDone(true);
          setTimeout(() => setDone(false), 1600);
        }
      }}
    >
      {done ? "Copied" : label}
    </Button>
  );
}

/* ------------------------------------------------------------------ Modal */
export function Modal({ open, onClose, title, children, footer, width = "max-w-md" }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; width?: string }) {
  useEffect(() => {
    if (!open) return;
    const fn = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[90] flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className={cn("glass relative w-full animate-fade-in rounded-2xl", width)}>
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <button onClick={onClose} className="rounded p-1 text-subtle hover:bg-surface-3 hover:text-text" aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-border px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, onClose, onConfirm, title, message, confirmLabel = "Delete", loading }: {
  open: boolean; onClose: () => void; onConfirm: () => void; title: string; message: ReactNode; confirmLabel?: string; loading?: boolean;
}) {
  return (
    <Modal open={open} onClose={onClose} title={title}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="danger" loading={loading} onClick={onConfirm}>{confirmLabel}</Button></>}>
      <p className="text-sm text-muted">{message}</p>
    </Modal>
  );
}

/* ------------------------------------------------------------------ Score ring */
export function ScoreRing({ score, size = 112, label, grade, color }: { score: number | null; size?: number; label?: string; grade?: string; color?: string }) {
  const stroke = Math.max(5, size / 13);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100;
  const col = color ?? scoreColor(score);
  return (
    <div className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--surface-3)" strokeWidth={stroke} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={col} strokeWidth={stroke} fill="none" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - pct)} style={{ transition: "stroke-dashoffset .8s ease", filter: `drop-shadow(0 0 6px ${col}55)` }} />
      </svg>
      <div className="absolute text-center">
        <div className="font-display font-semibold tabular-nums leading-none" style={{ fontSize: size / 4 }}>{score ?? "—"}</div>
        {(label || grade) && <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-subtle">{grade ? `Grade ${grade}` : label}</div>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Pagination */
export function Pagination({ page, pages, total, onPage, label = "results" }: { page: number; pages: number; total: number; onPage: (p: number) => void; label?: string }) {
  if (total === 0) return null;
  const nums: (number | "…")[] = [];
  for (let p = 1; p <= pages; p++) {
    if (p === 1 || p === pages || Math.abs(p - page) <= 1) nums.push(p);
    else if (nums[nums.length - 1] !== "…") nums.push("…");
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3 text-[13px] text-muted">
      <span>Showing page <span className="text-text">{page}</span> of {pages} · {total.toLocaleString()} {label}</span>
      <div className="flex items-center gap-1">
        <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => onPage(page - 1)} icon={<ChevronLeft className="h-4 w-4" />}>Prev</Button>
        {nums.map((n, i) => n === "…" ? <span key={i} className="px-1 text-subtle">…</span> : (
          <button key={i} onClick={() => onPage(n)} className={cn("h-8 min-w-8 rounded-lg px-2 font-mono text-xs", n === page ? "bg-accent/15 text-accent-text ring-1 ring-accent/40" : "text-muted hover:bg-surface-3")}>{n}</button>
        ))}
        <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next <ChevronRight className="h-4 w-4" /></Button>
      </div>
    </div>
  );
}

/** Telemetry metric card: mono eyebrow, large tabular figure, hint line and optional progress bar. */
export function StatCard({ label, value, icon, hint, accent = "accent", progress, valueColor, suffix }: {
  label: string; value: ReactNode; icon: ReactNode; hint?: ReactNode; accent?: "accent" | "blue" | "red" | "yellow" | "green";
  progress?: number | null; valueColor?: string; suffix?: ReactNode;
}) {
  const tones = {
    accent: { box: "bg-accent/12 text-accent-text", bar: "#8b5cf6" },
    blue: { box: "bg-sky-400/10 text-sky-400", bar: "#38bdf8" },
    red: { box: "bg-red-500/12 text-red-400", bar: "#f87171" },
    yellow: { box: "bg-amber-500/12 text-amber-400", bar: "#f59e0b" },
    green: { box: "bg-emerald-500/12 text-emerald-400", bar: "#22c55e" },
  };
  return (
    <div className="card flex flex-col p-4 transition-colors hover:border-border-strong">
      <div className="flex items-start justify-between gap-2">
        <p className="eyebrow leading-snug">{label}</p>
        <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", tones[accent].box)}>{icon}</div>
      </div>
      <p className="mt-3 font-display text-[32px] font-semibold leading-none tracking-[-0.02em] tabular-nums" style={valueColor ? { color: valueColor } : undefined}>
        {value}{suffix && <span className="ml-1 text-sm font-normal text-subtle">{suffix}</span>}
      </p>
      {hint && <p className="mt-2 text-xs text-muted">{hint}</p>}
      {progress != null && (
        <div className="mt-auto pt-4">
          <div className="h-1 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${Math.max(2, Math.min(100, progress))}%`, background: tones[accent].bar }} />
          </div>
        </div>
      )}
    </div>
  );
}
