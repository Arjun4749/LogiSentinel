// Thin API client. The token is kept in localStorage so a page refresh keeps you signed in.
const BASE = (import.meta as any).env?.VITE_API_BASE_URL || "";

export type User = { username: string; role: "admin" | "planner" | "viewer"; name: string; title: string };

let token: string | null = null;
try { token = localStorage.getItem("ls_token"); } catch { token = null; }

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

export function setToken(t: string | null) {
  token = t;
  try { t ? localStorage.setItem("ls_token", t) : localStorage.removeItem("ls_token"); } catch { /* ignore */ }
}
export function getToken() { return token; }

export class ApiError extends Error { status: number; constructor(status: number, msg: string) { super(msg); this.status = status; } }

export async function api<T = any>(path: string, opts: { method?: string; body?: any; text?: boolean } = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      method: opts.method || "GET",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the LogiSentinel server. Is it running? (start it with START_WINDOWS.bat or start_mac_linux.sh)");
  }
  if (res.status === 401 && path !== "/api/auth/login") { onUnauthorized(); }
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try { const j = await res.json(); if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }
  return (opts.text ? res.text() : res.json()) as Promise<T>;
}

export async function download(path: string, filename: string) {
  const res = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, "Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
