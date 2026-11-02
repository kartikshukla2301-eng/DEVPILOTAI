import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bell, BookOpen, BookOpenText, Bug, ChevronsLeft, ChevronsRight, CircleHelp, Cpu, FileText, FolderKanban, Gauge, History,
  LayoutDashboard, LogOut, Menu, MessageSquareCode, MoreVertical, PlusCircle, Search, Settings, Sparkles, User as UserIcon, X,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { NOTICE_ICON, NOTICE_TONE, useNotify } from "../../context/NotificationContext";
import { api } from "../../lib/api";
import { cn, timeAgo } from "../../lib/utils";

type NavItem = { to: string; label: string; icon: typeof LayoutDashboard; short?: string };
const SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Workspace",
    items: [
      { to: "/dashboard", label: "Overview / Dashboard", icon: LayoutDashboard, short: "Home" },
      { to: "/review", label: "Code Review", icon: MessageSquareCode, short: "Review" },
      { to: "/debug", label: "Debugging Assistant", icon: Bug, short: "Debug" },
      { to: "/explain", label: "Code Explainer", icon: BookOpenText, short: "Explain" },
      { to: "/optimize", label: "Code Optimizer", icon: Gauge },
      { to: "/docs", label: "Doc Generator", icon: FileText },
    ],
  },
  { title: "Management", items: [{ to: "/history", label: "Review History", icon: History, short: "History" }, { to: "/settings#projects", label: "Projects", icon: FolderKanban }] },
  { title: "Preferences", items: [{ to: "/settings", label: "Settings", icon: Settings }] },
];
const ALL_NAV = SECTIONS.flatMap((s) => s.items);
const MOBILE_NAV = ALL_NAV.filter((n) => n.short);

export function Logo({ compact = false, version = true }: { compact?: boolean; version?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0" aria-hidden>
        <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#8b5cf6" /><stop offset="1" stopColor="#38bdf8" /></linearGradient></defs>
        <rect width="32" height="32" rx="8" fill="url(#lg)" />
        <path d="M11 10l-5 6 5 6M21 10l5 6-5 6M18 8l-4 16" stroke="#fff" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {!compact && (
        <div className="leading-none">
          <div className="font-display text-[17px] font-semibold tracking-tight">DevPilot <span className="text-accent-text">AI</span></div>
          {version && <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-subtle">v1.0 · workspace</div>}
        </div>
      )}
    </div>
  );
}

function useClickOutside(ref: React.RefObject<HTMLElement | null>, onOutside: () => void, active: boolean) {
  useEffect(() => {
    if (!active) return;
    const fn = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && onOutside();
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, [ref, onOutside, active]);
}

/** Polls /api/health so the sidebar status reflects the real backend + database state. */
function useSystemStatus() {
  const [status, setStatus] = useState<"ok" | "degraded" | "down" | "checking">("checking");
  useEffect(() => {
    let alive = true;
    const check = () => api.get<{ status: string }>("/health", { timeout: 8000 })
      .then((r) => alive && setStatus(r.data.status === "ok" ? "ok" : "degraded"))
      .catch(() => alive && setStatus("down"));
    check();
    const t = setInterval(check, 60_000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  return status;
}

function Notifications() {
  const { notices, unread, markAllRead, clearAll } = useNotify();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  useClickOutside(ref, () => setOpen(false), open);
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => { setOpen((o) => !o); if (!open && unread) setTimeout(markAllRead, 1200); }}
        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-surface-3 hover:text-text"
        aria-label={`Notifications${unread ? ` (${unread} unread)` : ""}`}
      >
        <Bell className="h-[18px] w-[18px]" />
        {unread > 0 && <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-orange-400 ring-2 ring-rail" />}
      </button>
      {open && (
        <div className="glass absolute right-0 top-11 z-50 w-[min(360px,calc(100vw-1.5rem))] animate-fade-in overflow-hidden rounded-xl">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <span className="text-sm font-semibold">Notifications</span>
            {notices.length > 0 && <button onClick={clearAll} className="text-xs text-muted hover:text-text">Clear all</button>}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {notices.length === 0 ? (
              <p className="px-4 py-10 text-center text-[13px] text-muted">You're all caught up. Completed analyses appear here.</p>
            ) : notices.map((n) => {
              const Icon = NOTICE_ICON[n.kind];
              return (
                <button key={n.id} onClick={() => { if (n.link) { navigate(n.link); setOpen(false); } }}
                  className={cn("flex w-full gap-3 border-b border-border px-4 py-3 text-left last:border-0 hover:bg-surface-3", !n.read && "bg-accent-soft")}>
                  <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", NOTICE_TONE[n.kind])} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium">{n.title}</p>
                    {n.message && <p className="mt-0.5 line-clamp-2 text-xs text-muted">{n.message}</p>}
                    <p className="mt-1 font-mono text-[10px] text-subtle">{timeAgo(n.created_at)}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function Avatar({ name, size = "h-9 w-9" }: { name: string; size?: string }) {
  const initials = name.split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return <span className={cn("flex shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-sky-500 text-xs font-semibold text-white ring-2 ring-border", size)}>{initials}</span>;
}

function UserMenu({ placement = "top" }: { placement?: "top" | "sidebar" }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  useClickOutside(ref, () => setOpen(false), open);
  const menu = open && (
    <div className={cn("glass absolute z-50 w-56 animate-fade-in rounded-xl p-1.5", placement === "top" ? "right-0 top-12" : "bottom-14 left-0")}>
      <div className="border-b border-border px-2.5 pb-2 pt-1">
        <p className="truncate text-sm font-medium">{user?.name}</p>
        <p className="truncate text-xs text-muted">{user?.email}</p>
      </div>
      <Link to="/settings" onClick={() => setOpen(false)} className="mt-1 flex items-center gap-2 rounded-md px-2.5 py-2 text-[13px] hover:bg-surface-3"><UserIcon className="h-4 w-4 text-muted" /> Profile & settings</Link>
      <Link to="/history" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-md px-2.5 py-2 text-[13px] hover:bg-surface-3"><History className="h-4 w-4 text-muted" /> Review history</Link>
      <button onClick={async () => { await logout(); navigate("/login"); }} className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-[13px] text-red-400 hover:bg-red-500/10"><LogOut className="h-4 w-4" /> Log out</button>
    </div>
  );
  if (placement === "sidebar") {
    return (
      <div className="relative" ref={ref}>
        <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left hover:bg-surface-3" aria-label="Account menu">
          <Avatar name={user?.name ?? "?"} size="h-8 w-8" />
          <span className="min-w-0 flex-1 leading-tight">
            <span className="block truncate text-[13px] font-medium">{user?.name}</span>
            <span className="block truncate font-mono text-[10px] text-subtle">{user?.email}</span>
          </span>
          <MoreVertical className="h-4 w-4 text-subtle" />
        </button>
        {menu}
      </div>
    );
  }
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} className="rounded-full" aria-label="User menu"><Avatar name={user?.name ?? "?"} /></button>
      {menu}
    </div>
  );
}

function ModePill() {
  const { aiStatus, aiActive } = useAuth();
  if (!aiStatus) return null;
  const title = aiActive ? `AI-assisted analysis using ${aiStatus.model}` : aiStatus.ai_configured ? "AI is configured but disabled in your settings" : "No AI API key on the server; rule-based analysis";
  return (
    <Link to="/settings#ai" title={title} className="hidden items-center gap-2.5 rounded-full border border-border bg-surface px-3 py-1.5 transition-colors hover:border-border-strong md:flex">
      {aiActive ? <Sparkles className="h-4 w-4 text-accent-text" /> : <Cpu className="h-4 w-4 text-sky-400" />}
      <span className="leading-tight">
        <span className="block max-w-40 truncate font-mono text-[11px] text-text">{aiActive ? aiStatus.model : "Static engine"}</span>
        <span className="block font-mono text-[10px] text-subtle">{aiActive ? "AI + static hybrid" : aiStatus.ai_configured ? "AI off · local" : "Local analysis mode"}</span>
      </span>
    </Link>
  );
}

/* ---------------------------------------------------------------- Command palette (⌘K) */
function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setIdx(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  const items = useMemo(() => {
    const nav = ALL_NAV.filter((n) => n.label.toLowerCase().includes(q.toLowerCase())).map((n) => ({ key: n.to, label: n.label, icon: n.icon, hint: "Go to", run: () => navigate(n.to) }));
    const search = q.trim() ? [{ key: "search", label: `Search review history for “${q.trim()}”`, icon: Search, hint: "Search", run: () => navigate(`/history?q=${encodeURIComponent(q.trim())}`) }] : [];
    return [...nav, ...search];
  }, [q, navigate]);

  useEffect(() => setIdx(0), [q]);
  if (!open) return null;

  const run = (i: number) => {
    items[i]?.run();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[95] flex items-start justify-center px-4 pt-[14vh]" role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="absolute inset-0 bg-black/55" onClick={onClose} />
      <div className="glass relative w-full max-w-[640px] animate-fade-in overflow-hidden rounded-2xl">
        <div className="flex items-center gap-3 border-b border-border px-4">
          <span className="font-mono text-accent-text">›</span>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              else if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(items.length - 1, i + 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(0, i - 1)); }
              else if (e.key === "Enter") run(idx);
            }}
            placeholder="Jump to a module or search your reviews…"
            className="h-14 flex-1 bg-transparent text-base outline-none placeholder:text-subtle"
          />
          <span className="kbd">Esc</span>
        </div>
        <ul className="max-h-80 overflow-y-auto p-2">
          {items.length === 0 && <li className="px-3 py-6 text-center text-[13px] text-muted">No matching commands</li>}
          {items.map((it, i) => (
            <li key={it.key}>
              <button onMouseEnter={() => setIdx(i)} onClick={() => run(i)}
                className={cn("flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[13px]", i === idx ? "bg-surface-3 text-text" : "text-muted")}>
                <it.icon className={cn("h-4 w-4", i === idx ? "text-accent-text" : "text-subtle")} />
                <span className="flex-1 truncate">{it.label}</span>
                <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">{it.hint}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-4 border-t border-border px-4 py-2 font-mono text-[10px] text-subtle">
          <span><span className="kbd">↑↓</span> navigate</span><span><span className="kbd">↵</span> open</span>
        </div>
      </div>
    </div>
  );
}

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
export const MOD_KEY = isMac ? "⌘" : "Ctrl";

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("devpilot.sidebar") === "collapsed");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const status = useSystemStatus();
  const current = ALL_NAV.find((n) => location.pathname.startsWith(n.to.split("#")[0]) && n.to !== "/settings#projects")
    ?? (location.pathname.startsWith("/history") ? ALL_NAV.find((n) => n.to === "/history") : null);

  useEffect(() => setMobileOpen(false), [location.pathname]);
  useEffect(() => localStorage.setItem("devpilot.sidebar", collapsed ? "collapsed" : "expanded"), [collapsed]);

  const onKey = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === "k") {
      e.preventDefault();
      e.stopPropagation(); // Monaco uses Ctrl+K as a chord prefix; take it first
      setPaletteOpen((o) => !o);
    }
  }, []);
  useEffect(() => {
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onKey]);

  const statusMeta = {
    ok: { dot: "bg-emerald-400", text: "text-emerald-400", label: "All systems normal" },
    degraded: { dot: "bg-amber-400", text: "text-amber-400", label: "Database unavailable" },
    down: { dot: "bg-red-400", text: "text-red-400", label: "API unreachable" },
    checking: { dot: "bg-subtle", text: "text-subtle", label: "Checking status…" },
  }[status];

  const isActive = (to: string) => {
    const [path, hash] = to.split("#");
    if (hash) return location.pathname === path && location.hash === `#${hash}`;
    if (path === "/settings") return location.pathname === "/settings" && location.hash !== "#projects";
    return location.pathname.startsWith(path);
  };

  const sidebar = (mobile: boolean) => {
    const mini = collapsed && !mobile;
    return (
      <nav className="flex h-full flex-col">
        <div className={cn("flex h-16 shrink-0 items-center border-b border-border px-4", mini ? "justify-center" : "justify-between")}>
          <Link to="/dashboard"><Logo compact={mini} /></Link>
          {mobile && <button onClick={() => setMobileOpen(false)} className="rounded p-1 text-muted hover:bg-surface-3" aria-label="Close menu"><X className="h-5 w-5" /></button>}
        </div>
        <div className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
          {SECTIONS.map((sec) => (
            <div key={sec.title}>
              {!mini && <p className="eyebrow mb-1.5 px-2.5">{sec.title}</p>}
              <div className="space-y-0.5">
                {sec.items.map(({ to, label, icon: Icon }) => {
                  const active = isActive(to);
                  return (
                    <NavLink key={to} to={to} title={mini ? label : undefined}
                      className={cn(
                        "group flex items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] transition-colors",
                        active ? "bg-accent text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18),0_0_18px_-6px_rgba(139,92,246,0.7)]" : "text-muted hover:bg-surface-3 hover:text-text",
                        mini && "justify-center px-0",
                      )}>
                      <Icon className={cn("h-[18px] w-[18px] shrink-0", active ? "text-white" : "text-subtle group-hover:text-muted")} />
                      {!mini && <span className="truncate font-medium">{label}</span>}
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <div className="shrink-0 space-y-1 border-t border-border bg-bg/40 p-3">
          {!mini && (
            <>
              <Link to="/home#faq" className="flex items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] text-muted hover:bg-surface-3 hover:text-text"><BookOpen className="h-[18px] w-[18px] text-subtle" /> Help & Docs</Link>
              <div className={cn("flex items-center gap-2 px-2.5 py-1 font-mono text-[10.5px]", statusMeta.text)} title="Backend /api/health">
                <span className="relative flex h-2 w-2">
                  {status === "ok" && <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", statusMeta.dot)} />}
                  <span className={cn("relative inline-flex h-2 w-2 rounded-full", statusMeta.dot)} />
                </span>
                {statusMeta.label}
              </div>
              <UserMenu placement="sidebar" />
            </>
          )}
          {!mobile && (
            <button onClick={() => setCollapsed((c) => !c)} className={cn("flex w-full items-center gap-3 rounded-lg px-2.5 py-1.5 text-xs text-subtle hover:bg-surface-3 hover:text-text", mini && "justify-center px-0")}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
              {collapsed ? <ChevronsRight className="h-4 w-4" /> : <><ChevronsLeft className="h-4 w-4" /> Collapse</>}
            </button>
          )}
        </div>
      </nav>
    );
  };

  return (
    <div className="flex h-full">
      <aside className={cn("hidden shrink-0 border-r border-border bg-rail transition-[width] duration-200 lg:block", collapsed ? "w-[68px]" : "w-64")}>
        {sidebar(false)}
      </aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-[80] lg:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 animate-fade-in border-r border-border bg-rail">{sidebar(true)}</aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-16 shrink-0 items-center gap-3 border-b border-border bg-rail/90 px-4 backdrop-blur-md sm:px-6">
          <button onClick={() => setMobileOpen(true)} className="rounded-lg p-2 text-muted hover:bg-surface-3 lg:hidden" aria-label="Open menu"><Menu className="h-5 w-5" /></button>
          <nav className="hidden min-w-0 items-center gap-2 font-mono text-[12px] sm:flex" aria-label="Breadcrumb">
            <Link to="/dashboard" className="text-muted hover:text-text">DevPilot AI</Link>
            <span className="text-subtle">/</span>
            <span className="truncate text-text">{current?.label.replace("Overview / ", "") ?? "Workspace"}</span>
          </nav>
          <button onClick={() => setPaletteOpen(true)}
            className="ml-auto flex h-9 min-w-0 items-center gap-2.5 rounded-lg border border-border bg-surface px-3 text-[13px] text-subtle transition-colors hover:border-border-strong sm:w-64 lg:ml-6 xl:w-80"
            aria-label="Open command palette">
            <Search className="h-4 w-4 shrink-0" />
            <span className="hidden flex-1 truncate text-left sm:block">Search modules, reviews…</span>
            <span className="kbd hidden sm:inline-flex">{MOD_KEY} K</span>
          </button>
          <div className="flex items-center gap-2 lg:ml-auto">
            <ModePill />
            <button onClick={() => navigate("/review")}
              className="hidden h-9 items-center gap-2 rounded-lg bg-accent px-3.5 text-[13px] font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2)] transition-all hover:bg-accent-hover hover:shadow-[0_0_16px_rgba(139,92,246,0.4)] sm:flex">
              <PlusCircle className="h-4 w-4" /> New Review
            </button>
            <Notifications />
            <Link to="/home#faq" className="hidden h-9 w-9 items-center justify-center rounded-lg text-muted hover:bg-surface-3 hover:text-text xl:flex" aria-label="Help"><CircleHelp className="h-[18px] w-[18px]" /></Link>
            <UserMenu />
          </div>
        </header>
        <main className="flex-1 overflow-y-auto pb-16 lg:pb-0">
          <div className="mx-auto w-full max-w-[1520px] animate-fade-in p-4 sm:p-6 lg:p-8" key={location.pathname}>
            <Outlet />
          </div>
        </main>
        {/* Mobile bottom navigation */}
        <nav className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border bg-rail/95 backdrop-blur-md lg:hidden" aria-label="Primary">
          {MOBILE_NAV.map(({ to, short, icon: Icon }) => {
            const active = isActive(to);
            return (
              <NavLink key={to} to={to} className={cn("flex flex-1 flex-col items-center gap-1 py-2 text-[10px] font-medium", active ? "text-accent-text" : "text-subtle")}>
                <Icon className="h-5 w-5" />{short}
              </NavLink>
            );
          })}
        </nav>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
