import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "../lib/api";
import type { AIStatus, Theme, TokenResponse, User, UserSettings } from "../lib/types";

const DEFAULT_SETTINGS: UserSettings = { theme: "dark", default_language: "python", explanation_level: "intermediate", use_ai: true };

interface AuthState {
  user: User | null;
  settings: UserSettings;
  aiStatus: AIStatus | null;
  loading: boolean;
  /** True when AI is configured on the server AND enabled in the user's preferences. */
  aiActive: boolean;
  login: (email: string, password: string, remember?: boolean) => Promise<void>;
  register: (name: string, email: string, password: string, remember?: boolean) => Promise<void>;
  logout: (opts?: { silent?: boolean }) => Promise<void>;
  setUser: (u: User) => void;
  acceptToken: (t: TokenResponse) => void;
  updateSettings: (patch: Partial<UserSettings>) => Promise<UserSettings>;
}

const AuthContext = createContext<AuthState | null>(null);

export function applyTheme(theme: Theme) {
  localStorage.setItem("devpilot.theme", theme);
  const resolved = theme === "system" ? (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark") : theme;
  document.documentElement.classList.toggle("light", resolved === "light");
  document.documentElement.classList.toggle("dark", resolved !== "light");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS);
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const reset = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setSettings(DEFAULT_SETTINGS);
    setAiStatus(null);
  }, []);

  const loadSession = useCallback(async () => {
    const [me, s, ai] = await Promise.all([
      api.get<User>("/auth/me"),
      api.get<UserSettings>("/settings"),
      api.get<AIStatus>("/settings/ai-status"),
    ]);
    setUser(me.data);
    setSettings(s.data);
    setAiStatus(ai.data);
    applyTheme(s.data.theme);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => reset());
    (async () => {
      if (tokenStore.get()) {
        try {
          await loadSession();
        } catch {
          reset();
        }
      }
      setLoading(false);
    })();
    return () => setUnauthorizedHandler(null);
  }, [loadSession, reset]);

  // keep "system" theme in sync with the OS
  useEffect(() => {
    if (settings.theme !== "system") return;
    const mq = matchMedia("(prefers-color-scheme: light)");
    const fn = () => applyTheme("system");
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, [settings.theme]);

  const acceptToken = useCallback((t: TokenResponse) => {
    tokenStore.set(t.access_token);
    setUser(t.user);
  }, []);

  const login = useCallback(async (email: string, password: string, remember = true) => {
    const r = await api.post<TokenResponse>("/auth/login", { email, password });
    tokenStore.set(r.data.access_token, remember);
    await loadSession();
  }, [loadSession]);

  const register = useCallback(async (name: string, email: string, password: string, remember = true) => {
    const r = await api.post<TokenResponse>("/auth/register", { name, email, password });
    tokenStore.set(r.data.access_token, remember);
    await loadSession();
  }, [loadSession]);

  const logout = useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) {
      try {
        await api.post("/auth/logout");
      } catch {
        /* token may already be invalid; clear locally regardless */
      }
    }
    reset();
  }, [reset]);

  const updateSettings = useCallback(async (patch: Partial<UserSettings>) => {
    const r = await api.patch<UserSettings>("/settings", patch);
    setSettings(r.data);
    applyTheme(r.data.theme);
    return r.data;
  }, []);

  const value = useMemo<AuthState>(() => ({
    user, settings, aiStatus, loading,
    aiActive: Boolean(aiStatus?.ai_configured && settings.use_ai),
    login, register, logout, setUser, acceptToken, updateSettings,
  }), [user, settings, aiStatus, loading, login, register, logout, acceptToken, updateSettings]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
