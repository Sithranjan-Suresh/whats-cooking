"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { cx } from "@/lib/format";
import { useHealth, useRestaurant } from "@/hooks/data";
import { useTheme } from "@/lib/theme";

const ROUTES = [
  { href: "/insights", key: "insights" as const, icon: IconStar },
  { href: "/studio", key: "studio" as const, icon: IconClap },
  { href: "/library", key: "library" as const, icon: IconReel },
  { href: "/settings", key: "settings" as const, icon: IconTicket },
];

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { data: health } = useHealth();
  const { data: r } = useRestaurant();
  const { t } = useTheme();
  const demo = health?.demo && health.actor !== "owner";

  return (
    <div className="min-h-screen md:flex">
      <div className="grain-layer" aria-hidden />

      {/* Sidebar (desktop) */}
      <aside
        className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-line/70 bg-black/40 backdrop-blur-sm md:flex"
      >
        <StudioMarquee />
        <nav className="mt-2 flex flex-col gap-1.5 px-4" aria-label="Main">
          {ROUTES.map((n) => {
            const active = path?.startsWith(n.href);
            const Icon = n.icon;
            const label = t.nav[n.key];
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "group relative flex min-h-[48px] items-center gap-3 px-3 font-display text-[22px] uppercase tracking-[.08em] transition",
                  active ? "text-gold" : "text-muted hover:text-cream",
                )}
              >
                {active && <motion.span layoutId="navspot" className="absolute inset-0 rounded-xl bg-[radial-gradient(ellipse_at_left,rgb(var(--gold)/.22),transparent_70%)]" />}
                <Icon className="relative h-5 w-5" />
                <span className="relative">{label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto space-y-3 p-4">
          <SoundToggle />
          <div className="flex items-center gap-3 rounded-xl border border-line/70 bg-black/40 p-3">
            {r?.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={r.logo_url} alt="" className="h-9 w-9 rounded-full object-contain" />
            ) : (
              <div className="h-9 w-9 rounded-full bg-gold/20" />
            )}
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-cream">{r?.name ?? "…"}</div>
              <div className="text-xs text-muted">{health?.actor === "owner" ? "Director" : "Audience"}</div>
            </div>
          </div>
        </div>
      </aside>

      <div className="relative min-w-0 flex-1">
        {/* Top bar (mobile) */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line/70 bg-bg/85 px-4 py-3 backdrop-blur md:hidden">
          <Wordmark small />
          <SoundToggle />
        </header>
        {demo && (
          <div className="border-b border-gold/25 bg-gradient-to-r from-transparent via-ember/30 to-transparent px-4 py-2 text-center text-xs text-gold2 sm:text-sm">
            <b className="font-display text-base tracking-[.12em]">Preview screening</b> · You&apos;re watching Kumar&apos;s. Shoots run on the free camera rig, and premieres are for the director.
          </div>
        )}
        {health && health.mock && <div className="border-b border-line bg-panel px-4 py-1.5 text-center text-[11px] uppercase tracking-wider text-muted">Mock pipeline</div>}
        <main className="mx-auto w-full max-w-6xl px-4 pb-28 pt-6 sm:px-6 md:pb-14 md:pt-10">{children}</main>
      </div>

      {/* Bottom tabs (mobile) */}
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-line/70 bg-black/90 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        {ROUTES.map((n) => {
          const active = path?.startsWith(n.href);
          const Icon = n.icon;
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active ? "page" : undefined}
              className={cx(
                "relative flex min-h-[60px] flex-col items-center justify-center gap-1 font-display text-[14px] tracking-[.1em]",
                active ? "text-gold" : "text-muted",
              )}
            >
              {active && <motion.span layoutId="tabspot" className="absolute inset-x-4 top-0 h-[3px] rounded-full bg-gold shadow-glow" />}
              <Icon className="h-5 w-5" />
              {n.key === "settings" ? t.nav.settingsShort : t.nav[n.key].replace("Screening Room", "Screening")}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

function StudioMarquee() {
  const { t } = useTheme();
  return (
    <Link href="/insights" className="relative mx-4 mb-6 mt-6 block rounded-xl bg-black/60 px-4 py-5 text-center ring-1 ring-gold/30">
      <BulbRow className="absolute inset-x-3 top-1.5" n={11} />
      <BulbRow className="absolute inset-x-3 bottom-1.5" n={11} offset />
      <div className="font-display text-[34px] uppercase leading-[.9] tracking-[.04em] text-cream">
        What&apos;s <span className="animate-flicker text-gold [text-shadow:0_0_18px_rgb(var(--gold)/.55)]">Cooking?</span>
      </div>
      <div className="mt-1.5 font-mono text-[11px] uppercase tracking-[.25em] text-muted">{t.brandTag}</div>
    </Link>
  );
}

export function BulbRow({ n, className, offset }: { n: number; className?: string; offset?: boolean }) {
  return (
    <div className={cx("flex justify-between", className)} aria-hidden>
      {Array.from({ length: n }).map((_, i) => (
        <span key={i} className="bulb animate-flicker" style={{ animationDelay: `${((i + (offset ? 1 : 0)) % 4) * 0.37}s`, width: 6, height: 6 }} />
      ))}
    </div>
  );
}

export function SoundToggle() {
  const { sound, setSound } = useTheme();
  return (
    <button
      onClick={() => setSound(!sound)}
      aria-label={sound ? "Mute sound effects" : "Unmute sound effects"}
      className="flex h-8 items-center gap-2 self-start rounded-full border border-line bg-black/40 px-3 text-[11px] font-semibold uppercase tracking-wider text-muted hover:text-cream"
    >
      <span aria-hidden>{sound ? "🔊" : "🔇"}</span>
      <span className="hidden md:inline">{sound ? "Sound on" : "Sound off"}</span>
    </button>
  );
}

export function Wordmark({ small }: { small?: boolean }) {
  return (
    <span className={cx("font-display uppercase leading-none tracking-[.05em] text-cream", small ? "text-2xl" : "text-3xl")}>
      What&apos;s <span className="text-gold [text-shadow:0_0_14px_rgb(var(--gold)/.5)]">Cooking?</span>
    </span>
  );
}

type IconProps = { className?: string };
const sv = { fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
function IconStar({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" {...sv} aria-hidden>
      <path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z" />
    </svg>
  );
}
function IconClap({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" {...sv} aria-hidden>
      <rect x="3" y="10" width="18" height="11" rx="1.5" />
      <path d="M3 10l2-5.5 16 0L19 10M8 4.5L6.5 10M13 4.5L11.5 10M18 4.5L16.5 10" />
    </svg>
  );
}
function IconReel({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" {...sv} aria-hidden>
      <circle cx="11" cy="12" r="8" />
      <circle cx="11" cy="12" r="1.6" />
      <circle cx="11" cy="7.5" r="1.6" />
      <circle cx="11" cy="16.5" r="1.6" />
      <circle cx="6.5" cy="12" r="1.6" />
      <circle cx="15.5" cy="12" r="1.6" />
      <path d="M19 20h3" />
    </svg>
  );
}
function IconTicket({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" {...sv} aria-hidden>
      <path d="M3 8a2 2 0 0 0 0 4v0a2 2 0 0 0 0 4v2h18v-2a2 2 0 0 1 0-4 2 2 0 0 1 0-4V6H3z" />
      <path d="M14 6v12" strokeDasharray="2 2" />
    </svg>
  );
}
