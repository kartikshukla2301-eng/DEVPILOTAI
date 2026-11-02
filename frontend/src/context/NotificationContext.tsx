import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "../lib/utils";

export type NoticeKind = "success" | "error" | "info" | "warning";

export interface Notice {
  id: string;
  kind: NoticeKind;
  title: string;
  message?: string;
  link?: string;
  created_at: string;
  read: boolean;
}

interface NotifyOptions {
  message?: string;
  link?: string;
  /** Also record in the notification center (default: true for success/warning, false for errors). */
  persist?: boolean;
}

interface NotificationState {
  notices: Notice[];
  unread: number;
  notify: (kind: NoticeKind, title: string, opts?: NotifyOptions) => void;
  markAllRead: () => void;
  clearAll: () => void;
}

const Ctx = createContext<NotificationState | null>(null);
const STORE_KEY = "devpilot.notifications";
const MAX = 30;

const ICON = { success: CheckCircle2, error: XCircle, info: Info, warning: AlertTriangle };
const TONE = {
  success: "text-emerald-400",
  error: "text-red-400",
  info: "text-blue",
  warning: "text-yellow-400",
};

export function NotificationProvider({ children, userId }: { children: ReactNode; userId: string | null }) {
  const key = userId ? `${STORE_KEY}.${userId}` : null;
  const [notices, setNotices] = useState<Notice[]>([]);
  const [toasts, setToasts] = useState<Notice[]>([]);
  const timers = useRef(new Map<string, number>());

  useEffect(() => {
    if (!key) {
      setNotices([]);
      return;
    }
    try {
      setNotices(JSON.parse(localStorage.getItem(key) || "[]"));
    } catch {
      setNotices([]);
    }
  }, [key]);

  useEffect(() => {
    if (key) localStorage.setItem(key, JSON.stringify(notices.slice(0, MAX)));
  }, [key, notices]);

  const dismiss = useCallback((id: string) => {
    setToasts((t) => t.filter((x) => x.id !== id));
    const tm = timers.current.get(id);
    if (tm) window.clearTimeout(tm);
    timers.current.delete(id);
  }, []);

  const notify = useCallback((kind: NoticeKind, title: string, opts: NotifyOptions = {}) => {
    const n: Notice = { id: crypto.randomUUID(), kind, title, message: opts.message, link: opts.link, created_at: new Date().toISOString(), read: false };
    setToasts((t) => [...t.slice(-3), n]);
    timers.current.set(n.id, window.setTimeout(() => dismiss(n.id), kind === "error" ? 6500 : 4000));
    const persist = opts.persist ?? (kind === "success" || kind === "warning");
    if (persist) setNotices((all) => [n, ...all].slice(0, MAX));
  }, [dismiss]);

  const markAllRead = useCallback(() => setNotices((all) => all.map((n) => ({ ...n, read: true }))), []);
  const clearAll = useCallback(() => setNotices([]), []);

  const value = useMemo(() => ({ notices, unread: notices.filter((n) => !n.read).length, notify, markAllRead, clearAll }),
    [notices, notify, markAllRead, clearAll]);

  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
        {toasts.map((t) => {
          const Icon = ICON[t.kind];
          return (
            <div key={t.id} role="status" className="card pointer-events-auto flex items-start gap-3 p-3.5 animate-fade-in">
              <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", TONE[t.kind])} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{t.title}</p>
                {t.message && <p className="mt-0.5 text-[13px] text-muted">{t.message}</p>}
              </div>
              <button onClick={() => dismiss(t.id)} className="rounded p-0.5 text-subtle hover:bg-surface-3 hover:text-text" aria-label="Dismiss">
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}

export function useNotify() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useNotify must be used inside NotificationProvider");
  return ctx;
}

export const NOTICE_ICON = ICON;
export const NOTICE_TONE = TONE;
