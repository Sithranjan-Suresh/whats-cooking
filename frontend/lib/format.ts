import type { Angle } from "./types";

export const money = (cents: number | null | undefined) =>
  cents == null ? "—" : `$${(cents / 100).toFixed(2)}`;

export const ANGLE_LABEL: Record<Angle, string> = {
  rising: "Rising",
  top_seller: "Top seller",
  slow_mover: "Slow mover",
};

export const ANGLE_HINT: Record<Angle, string> = {
  rising: "Back by demand",
  top_seller: "Everyone's ordering it",
  slow_mover: "Underrated favorite",
};

export const FALLBACK_LABEL: Record<string, string> = {
  free_mode: "Free mode is on",
  daily_limit: "Daily Veo limit reached",
  monthly_cap: "Monthly cap reached",
  demo_mode: "Demo mode",
  veo_timeout: "Veo timed out",
  veo_blocked: "Veo declined this photo",
  veo_error: "Veo unavailable",
  veo_rate_limit: "Veo busy",
  veo_unavailable: "Veo not configured",
};

export function timeAgo(iso: string) {
  const t = new Date(iso).getTime();
  const s = Math.max(1, Math.round((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return d < 30 ? `${d}d ago` : new Date(iso).toLocaleDateString();
}

export function shortDate(iso: string) {
  return new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function elapsed(start: string | null, end: string | null, now = Date.now()) {
  if (!start) return null;
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : now;
  return Math.max(0, (e - s) / 1000);
}

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
