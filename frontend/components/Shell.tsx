"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { cx } from "@/lib/format";
import { useHealth, useRestaurant } from "@/hooks/data";

const NAV = [
  { href: "/insights", label: "Insights", icon: IconChart },
  { href: "/studio", label: "Studio", icon: IconSpark },
  { href: "/library", label: "Library", icon: IconGrid },
  { href: "/settings", label: "Brand & Budget", short: "Brand", icon: IconSliders },
];

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { data: health } = useHealth();
  const { data: r } = useRestaurant();
  const demo = health?.demo && health.actor !== "owner";
  return (
    <div className="min-h-screen md:flex">
      {/* Sidebar (desktop) */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-panel/60 px-4 py-6 md:flex">
        <Link href="/insights" className="mb-8 px-2">
          <Wordmark />
        </Link>
        <nav className="flex flex-col gap-1" aria-label="Main">
          {NAV.map((n) => {
            const active = path?.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "flex min-h-[44px] items-center gap-3 rounded-xl px-3 text-sm font-semibold transition",
                  active ? "bg-gold/15 text-gold" : "text-muted hover:bg-panel2 hover:text-cream",
                )}
              >
                <n.icon className="h-5 w-5" />
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto rounded-xl border border-line bg-bg/50 p-3">
          <div className="flex items-center gap-3">
            {r?.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={r.logo_url} alt="" className="h-9 w-9 rounded-full object-contain" />
            ) : (
              <div className="h-9 w-9 rounded-full bg-gold/20" />
            )}
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-cream">{r?.name ?? "…"}</div>
              <div className="text-xs text-muted">{health?.actor === "owner" ? "Owner" : "Demo viewer"}</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        {/* Top bar (mobile) */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-bg/90 px-4 py-3 backdrop-blur md:hidden">
          <Wordmark small />
          <span className="truncate pl-3 text-xs text-muted">{r?.name}</span>
        </header>
        {demo && (
          <div className="border-b border-gold/30 bg-gold/10 px-4 py-2 text-center text-xs text-gold sm:text-sm">
            <b>Demo mode</b> · You&apos;re viewing Kumar&apos;s. Videos render in free mode, and publishing is owner-only.
          </div>
        )}
        {health && health.mock && (
          <div className="border-b border-line bg-panel px-4 py-1.5 text-center text-[11px] uppercase tracking-wider text-muted">
            Mock pipeline
          </div>
        )}
        <main className="mx-auto w-full max-w-6xl px-4 pb-28 pt-6 sm:px-6 md:pb-12 md:pt-10">{children}</main>
      </div>

      {/* Bottom tabs (mobile) */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-line bg-panel/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        {NAV.map((n) => {
          const active = path?.startsWith(n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active ? "page" : undefined}
              className={cx("flex min-h-[58px] flex-col items-center justify-center gap-1 text-[11px] font-semibold", active ? "text-gold" : "text-muted")}
            >
              <n.icon className="h-5 w-5" />
              {n.short ?? n.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

export function Wordmark({ small }: { small?: boolean }) {
  return (
    <span className={cx("font-display uppercase leading-none tracking-wide text-cream", small ? "text-xl" : "text-2xl")}>
      What&apos;s <span className="text-gold">Cooking?</span>
    </span>
  );
}

type IconProps = { className?: string };
function IconChart({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M4 19V5M4 19h16M8 15l4-4 3 3 5-6" />
    </svg>
  );
}
function IconSpark({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <rect x="6" y="3" width="12" height="18" rx="2.5" />
      <path d="M11 9.5v5l4-2.5z" fill="currentColor" />
    </svg>
  );
}
function IconGrid({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <rect x="4" y="4" width="7" height="9" rx="1.5" />
      <rect x="13" y="4" width="7" height="6" rx="1.5" />
      <rect x="4" y="15" width="7" height="5" rx="1.5" />
      <rect x="13" y="12" width="7" height="8" rx="1.5" />
    </svg>
  );
}
function IconSliders({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="10" cy="17" r="2" />
    </svg>
  );
}
