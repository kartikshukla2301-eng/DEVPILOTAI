import axios, { AxiosError } from "axios";

const TOKEN_KEY = "devpilot.token";

/** Token storage. "Remember this device" keeps it in localStorage; otherwise it lives only for the browser session. */
export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(TOKEN_KEY),
  set: (t: string, remember?: boolean) => {
    const persist = remember ?? localStorage.getItem(TOKEN_KEY) != null;
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_KEY);
    (persist ? localStorage : sessionStorage).setItem(TOKEN_KEY, t);
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  },
};

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  timeout: 120_000,
});

api.interceptors.request.use((config) => {
  const t = tokenStore.get();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;
export const setUnauthorizedHandler = (fn: UnauthorizedHandler | null) => {
  onUnauthorized = fn;
};

api.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    const url = error.config?.url ?? "";
    if (error.response?.status === 401 && !url.startsWith("/auth/login") && !url.startsWith("/auth/register")) {
      tokenStore.clear();
      onUnauthorized?.();
    }
    return Promise.reject(error);
  },
);

/** Human-readable message from any API error (FastAPI detail strings or validation arrays). */
export function errorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return err.code === "ECONNABORTED" ? "The request timed out." : "Cannot reach the server. Is the backend running?";
    const detail = (err.response.data as { detail?: unknown })?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length) {
      return detail
        .map((d: { loc?: (string | number)[]; msg?: string }) => {
          const field = d.loc?.filter((x) => x !== "body").join(".");
          return `${field ? field + ": " : ""}${(d.msg ?? "").replace(/^Value error, /, "")}`;
        })
        .join("; ");
    }
    return `Request failed (HTTP ${err.response.status}).`;
  }
  return err instanceof Error ? err.message : fallback;
}

/** Download a protected file (with the auth header) and save it. */
export async function downloadFromApi(url: string, fallbackName: string): Promise<void> {
  const res = await api.get(url, { responseType: "blob" });
  const cd = (res.headers["content-disposition"] as string | undefined) ?? "";
  const m = /filename="?([^"]+)"?/.exec(cd);
  saveBlob(res.data as Blob, m?.[1] ?? fallbackName);
}

export function saveBlob(blob: Blob, filename: string) {
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

export function saveText(text: string, filename: string, type = "text/plain") {
  saveBlob(new Blob([text], { type: `${type};charset=utf-8` }), filename);
}
