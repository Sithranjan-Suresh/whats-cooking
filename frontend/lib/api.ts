// Typed fetch wrapper: adds X-Owner-Token, parses the contract error shape.
import type { ApiErrorBody } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

const TOKEN_KEY = "wc_owner_token";
const listeners = new Set<() => void>();

export function getOwnerToken(): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setOwnerToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage blocked: owner mode lasts for this page only */
  }
  listeners.forEach((l) => l());
}

export function onOwnerTokenChange(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

// Encrypted YouTube connection kept in the browser so it survives the free server wiping its disk.
const YT_KEY = "wc_yt";
export function getYtBlob(): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(YT_KEY);
  } catch {
    return null;
  }
}
export function setYtBlob(blob: string | null) {
  try {
    if (blob) window.localStorage.setItem(YT_KEY, blob);
    else window.localStorage.removeItem(YT_KEY);
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  code: string;
  retryable: boolean;
  status: number;
  constructor(code: string, message: string, retryable: boolean, status: number) {
    super(message);
    this.code = code;
    this.retryable = retryable;
    this.status = status;
  }
}

type Opts = { method?: string; json?: unknown; form?: FormData; signal?: AbortSignal };

export async function api<T>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getOwnerToken();
  if (token) headers["X-Owner-Token"] = token;
  const yt = getYtBlob();
  if (yt) headers["X-YouTube-Auth"] = yt;
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: opts.method || (body ? "POST" : "GET"),
      headers,
      body,
      signal: opts.signal,
      cache: "no-store",
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("network_error", "Can't reach the server. Check your connection and retry.", true, 0);
  }
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const err = (data as ApiErrorBody | null)?.error;
    if (err?.code === "youtube_reconnect_required") setYtBlob(null);
    throw new ApiError(
      err?.code || "http_error",
      err?.message || `Request failed (${res.status})`,
      err?.retryable ?? res.status >= 500,
      res.status,
    );
  }
  return data as T;
}

export const fetcher = <T,>(path: string) => api<T>(path);

// The studio is shared, so "Your videos" only lists jobs started from this browser.
const MY_JOBS_KEY = "wc_jobs";

export function getMyJobs(): Set<number> {
  try {
    const raw = typeof window === "undefined" ? null : window.localStorage.getItem(MY_JOBS_KEY);
    return new Set(raw ? (JSON.parse(raw) as number[]) : []);
  } catch {
    return new Set();
  }
}

export function addMyJob(id: number) {
  try {
    const ids = getMyJobs();
    ids.add(id);
    window.localStorage.setItem(MY_JOBS_KEY, JSON.stringify(Array.from(ids).slice(-200)));
  } catch {
    /* ignore */
  }
}
