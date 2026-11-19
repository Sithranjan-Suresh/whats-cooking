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

// Each browser has its own studio (restaurant name, logo, dishes, videos), copied from the demo on first use.
// The id is random and lives only in this browser; the server keys the studio by it (X-Workspace).
const WS_KEY = "wc_ws";
let memoryWorkspace: string | null = null;

export function getWorkspace(): string {
  try {
    let id = window.localStorage.getItem(WS_KEY);
    if (!id || !/^[0-9a-f]{32}$/.test(id)) {
      id = newWorkspaceId();
      window.localStorage.setItem(WS_KEY, id);
    }
    return id;
  } catch {
    // storage blocked (private mode): one studio for this page load
    return (memoryWorkspace ??= newWorkspaceId());
  }
}

function newWorkspaceId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function api<T>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Workspace": getWorkspace() };
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


// YouTube connect: the browser makes a one-time nonce, the server signs it into the OAuth state and hands it
// back with the connection (#yt=…&n=…). A connection is kept only if its nonce matches, so a link someone
// else started (with their channel) can't be planted in this browser.
const YT_NONCE_KEY = "wc_yt_nonce";

export async function startYouTubeConnect(): Promise<void> {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  const nonce = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  try {
    window.localStorage.setItem(YT_NONCE_KEY, nonce);
  } catch {
    /* ignore */
  }
  const { url } = await api<{ url: string }>(`/youtube/auth/url?nonce=${nonce}`);
  window.location.href = url;
}

/** Accept a connection from the URL fragment only if this browser started it. */
export function acceptYouTubeConnection(hash: string): boolean {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const blob = params.get("yt");
  const nonce = params.get("n");
  let expected: string | null = null;
  try {
    expected = window.localStorage.getItem(YT_NONCE_KEY);
    window.localStorage.removeItem(YT_NONCE_KEY);
  } catch {
    /* ignore */
  }
  if (!blob || !nonce || !expected || nonce !== expected) return false;
  setYtBlob(blob);
  return true;
}
