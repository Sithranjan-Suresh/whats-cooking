"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cx } from "@/lib/format";
import type { ApiError } from "@/lib/api";

// ---------------------------------------------------------------- Button
type BtnVariant = "primary" | "ghost" | "danger" | "subtle";
export function Button({
  variant = "primary",
  loading,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; loading?: boolean }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl px-4 min-h-[44px] text-sm font-semibold transition " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-bg " +
    "disabled:opacity-45 disabled:cursor-not-allowed active:scale-[.98]";
  const v = {
    primary:
      "bg-gold text-ongold hover:bg-gold2 studio:shadow-[0_0_0_1px_rgb(var(--gold2)/.6),0_8px_30px_-8px_rgb(var(--gold)/.6)] kitchen:font-mono kitchen:uppercase kitchen:tracking-wider kitchen:shadow-[0_3px_0_0_rgb(0_0_0/.55)] kitchen:active:translate-y-[2px] kitchen:active:shadow-none",
    ghost: "border border-line text-cream hover:border-gold/60 hover:bg-panel2 kitchen:font-mono kitchen:uppercase kitchen:tracking-wider kitchen:text-[12px]",
    danger: "border border-bad/50 text-bad hover:bg-bad/10",
    subtle: "text-muted hover:text-cream",
  }[variant];
  return (
    <button className={cx(base, v, className)} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cx("animate-spin motion-reduce:animate-none", className)} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity=".25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

// ---------------------------------------------------------------- Card
export function Card({ className, children, as: As = "div" }: { className?: string; children: ReactNode; as?: "div" | "section" | "article" }) {
  return <As className={cx("card rounded-xl border border-line bg-panel", className)}>{children}</As>;
}

export function SectionTitle({ title, sub, right, eyebrow }: { title: string; sub?: ReactNode; right?: ReactNode; eyebrow?: string }) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && (
          <div className="mb-2 flex items-center gap-2 font-mono text-[12px] uppercase tracking-[.28em] text-gold studio:before:content-['★'] kitchen:inline-flex kitchen:-rotate-1 kitchen:rounded-[3px] kitchen:border-2 kitchen:border-ember kitchen:px-2 kitchen:py-0.5 kitchen:text-ember kitchen:tracking-[.18em]">
            {eyebrow}
          </div>
        )}
        <h1 className="font-display uppercase leading-[.85] text-cream studio:text-[64px] studio:tracking-[.02em] studio:[text-shadow:0_2px_30px_rgb(var(--ember)/.6)] sm:studio:text-[88px] kitchen:text-[40px] kitchen:normal-case kitchen:leading-[1] sm:kitchen:text-[54px]">
          {title}
        </h1>
        {sub && <p className="mt-3 max-w-xl text-[15px] text-muted">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

// ---------------------------------------------------------------- Badge
type Tone = "neutral" | "gold" | "ok" | "bad" | "info";
export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  const t = {
    neutral: "border-line text-muted",
    gold: "border-gold/50 text-gold bg-gold/10",
    ok: "border-ok/40 text-ok bg-ok/10",
    bad: "border-bad/50 text-bad bg-bad/10",
    info: "border-cream/20 text-cream bg-cream/5",
  }[tone];
  return (
    <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider", t, className)}>
      {children}
    </span>
  );
}

// ---------------------------------------------------------------- Toggle
export function Toggle({
  checked,
  onChange,
  disabled,
  label,
  id,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label: string;
  id?: string;
}) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        "relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold",
        checked ? "border-gold bg-gold" : "border-line bg-bg",
        disabled && "cursor-not-allowed opacity-45",
      )}
    >
      <span className={cx("inline-block h-5 w-5 rounded-full shadow transition", checked ? "translate-x-6 bg-bg" : "translate-x-1 bg-muted")} />
    </button>
  );
}

// ---------------------------------------------------------------- Meter
export function Meter({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 100;
  const over = value >= max;
  return (
    <div role="meter" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-bg">
        <div className={cx("h-full rounded-full transition-all duration-700", over ? "bg-bad" : pct > 75 ? "bg-gold2" : "bg-gold")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function StatTile({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "bad" | "ok" }) {
  return (
    <div className="rounded-xl border border-line bg-bg/40 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">{label}</div>
      <div className={cx("mt-1 font-mono text-2xl", tone === "bad" ? "text-bad" : tone === "ok" ? "text-ok" : "text-cream")}>{value}</div>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- Skeleton
export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cx("relative overflow-hidden rounded-xl bg-panel2", className)} aria-hidden>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-cream/5 to-transparent motion-reduce:hidden" />
    </div>
  );
}

// ---------------------------------------------------------------- ErrorCallout
export function ErrorCallout({ error, onRetry, title }: { error: ApiError | Error | string | null | undefined; onRetry?: () => void; title?: string }) {
  if (!error) return null;
  const msg = typeof error === "string" ? error : error.message;
  const retryable = typeof error === "string" ? true : "retryable" in error ? (error as ApiError).retryable : true;
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm">
      <div>
        {title && <div className="font-semibold text-cream">{title}</div>}
        <div className="text-cream/90">{msg}</div>
      </div>
      {onRetry && retryable && (
        <Button variant="ghost" onClick={onRetry} className="min-h-[36px]">
          Retry
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ icon, title, body, action }: { icon?: ReactNode; title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-line px-6 py-12 text-center">
      {icon && <div className="mb-3 text-gold">{icon}</div>}
      <div className="font-display text-xl uppercase tracking-wide text-cream">{title}</div>
      {body && <div className="mt-2 max-w-md text-sm text-muted">{body}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- Modal
export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    setTimeout(() => ref.current?.querySelector<HTMLElement>("input,select,textarea,button")?.focus(), 30);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      prev?.focus?.();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-6" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cx("max-h-[92vh] w-full animate-fadeup overflow-y-auto rounded-t-xl border border-line bg-panel p-5 sm:rounded-xl", wide ? "sm:max-w-3xl" : "sm:max-w-lg")}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="font-display text-2xl uppercase tracking-wide text-cream">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="-mr-2 -mt-1 grid h-10 w-10 place-items-center rounded-full text-muted hover:bg-panel2 hover:text-cream">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Toasts
type Toast = { id: number; text: string; tone: "ok" | "bad" | "info" };
const ToastCtx = createContext<(text: string, tone?: Toast["tone"]) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function Toaster({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-2), { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-20 z-[60] flex flex-col items-center gap-2 px-4 md:bottom-6 md:items-end md:pr-6">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cx(
              "pointer-events-auto max-w-sm animate-fadeup rounded-xl border px-4 py-3 text-sm shadow-lg backdrop-blur",
              t.tone === "ok" && "border-ok/40 bg-panel/95 text-cream",
              t.tone === "bad" && "border-bad/50 bg-panel/95 text-cream",
              t.tone === "info" && "border-line bg-panel/95 text-cream",
            )}
          >
            <span className={cx("mr-2", t.tone === "ok" ? "text-ok" : t.tone === "bad" ? "text-bad" : "text-gold")}>●</span>
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

// ---------------------------------------------------------------- Field
export function Field({ label, hint, children, htmlFor }: { label: string; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-muted">
        {label}
      </label>
      {children}
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export const inputCls =
  "w-full rounded-xl border border-line bg-bg px-3 py-2.5 text-sm text-cream placeholder:text-muted/60 focus:border-gold focus:outline-none focus:ring-1 focus:ring-gold";
