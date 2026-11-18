"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { cx } from "@/lib/format";
import { useHealth, useRestaurant } from "@/hooks/data";
import { THEMES, useTheme } from "@/lib/theme";

const ROUTES = [
  { href: "/insights", key: "insights" as const, icon: IconStar, kicon: IconBoard },
  { href: "/studio", key: "studio" as const, icon: IconClap, kicon: IconFlame },
  { href: "/library", key: "library" as const, icon: IconReel, kicon: IconBell },
  { href: "/settings", key: "settings" as const, icon: IconTicket, kicon: IconReceipt },
];

export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { data: health } = useHealth();
  const { data: r } = useRestaurant();
  const { theme, t } = useTheme();
  const demo = health?.demo && health.actor !== "owner";
  const studio = theme === "studio";

  return (
    <div className="min-h-screen md:flex">
      {studio && <div className="grain-layer" aria-hidden />}

      {/* Sidebar (desktop) */}
      <aside
        className={cx(
          "sticky top-0 hidden h-screen w-64 shrink-0 flex-col md:flex",
          studio ? "border-r border-line/70 bg-black/40 backdrop-blur-sm" : "steel border-r-4 border-black/60",
        )}
      >
        {studio ? <StudioMarquee /> : <KitchenHeader />}
        <nav className="mt-2 flex flex-col gap-1.5 px-4" aria-label="Main">
          {ROUTES.map((n) => {
            const active = path?.startsWith(n.href);
            const Icon = studio ? n.icon : n.kicon;
            const label = t.nav[n.key];
            return studio ? (
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
            ) : (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={cx(
                  "relative flex min-h-[48px] items-center gap-3 rounded-[4px] px-3 font-mono text-[13px] font-semibold uppercase tracking-[.12em] transition",
                  active ? "ticket -rotate-[0.6deg] shadow-lift" : "text-muted hover:bg-white/5 hover:text-cream",
                )}
              >
                <Icon className="h-5 w-5" />
                {label}
                {active && <span className="absolute -top-1.5 left-1/2 h-3 w-8 -translate-x-1/2 rounded-sm bg-[#8e969d] shadow" aria-hidden />}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto space-y-3 p-4">
          <ThemeSwitch />
          <div className={cx("flex items-center gap-3 p-3", studio ? "rounded-xl border border-line/70 bg-black/40" : "ticket rounded-[4px]")}>
            {r?.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={r.logo_url} alt="" className="h-9 w-9 rounded-full object-contain" />
            ) : (
              <div className="h-9 w-9 rounded-full bg-gold/20" />
            )}
            <div className="min-w-0">
              <div className={cx("truncate text-sm font-semibold", studio ? "text-cream" : "text-ink")}>{r?.name ?? "…"}</div>
              <div className={cx("text-xs", studio ? "text-muted" : "text-ink/60")}>
                {health?.actor === "owner" ? (studio ? "Director" : "Head chef") : studio ? "Audience" : "Guest"}
              </div>
            </div>
          </div>
        </div>
      </aside>

      <div className="relative min-w-0 flex-1">
        {/* Top bar (mobile) */}
        <header className={cx("sticky top-0 z-30 flex items-center justify-between px-4 py-3 md:hidden", studio ? "border-b border-line/70 bg-bg/85 backdrop-blur" : "steel border-b-2 border-black/50")}>
          <Wordmark small />
          <ThemeSwitch compact />
        </header>
        {demo && (
          <div
            className={cx(
              "px-4 py-2 text-center text-xs sm:text-sm",
              studio ? "border-b border-gold/25 bg-gradient-to-r from-transparent via-ember/30 to-transparent text-gold2" : "border-b border-black/40 bg-ember/90 font-mono uppercase tracking-wider text-paper",
            )}
          >
            {studio ? (
              <>
                <b className="font-display text-base tracking-[.12em]">Preview screening</b> · You&apos;re watching Kumar&apos;s. Shoots run on the free camera rig, and premieres are for the director.
              </>
            ) : (
              <>Guest at the pass · Kumar&apos;s kitchen · free mode only · publishing is for the head chef</>
            )}
          </div>
        )}
        {health && health.mock && <div className="border-b border-line bg-panel px-4 py-1.5 text-center text-[11px] uppercase tracking-wider text-muted">Mock pipeline</div>}
        <main className="mx-auto w-full max-w-6xl px-4 pb-28 pt-6 sm:px-6 md:pb-14 md:pt-10">{children}</main>
      </div>

      {/* Bottom tabs (mobile) */}
      <nav
        aria-label="Main"
        className={cx(
          "fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 pb-[env(safe-area-inset-bottom)] md:hidden",
          studio ? "border-t border-line/70 bg-black/90 backdrop-blur" : "steel border-t-2 border-black/60",
        )}
      >
        {ROUTES.map((n) => {
          const active = path?.startsWith(n.href);
          const Icon = studio ? n.icon : n.kicon;
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active ? "page" : undefined}
              className={cx(
                "relative flex min-h-[60px] flex-col items-center justify-center gap-1 text-[11px] font-semibold",
                active ? "text-gold" : "text-muted",
                studio ? "font-display text-[14px] tracking-[.1em]" : "font-mono uppercase tracking-wider",
              )}
            >
              {active && <motion.span layoutId="tabspot" className="absolute inset-x-4 top-0 h-[3px] rounded-full bg-gold shadow-glow" />}
              <Icon className="h-5 w-5" />
              {n.key === "settings" ? t.nav.settingsShort : t.nav[n.key].replace("Screening Room", "Screening").replace("Today's ", "")}
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

function KitchenHeader() {
  return (
    <Link href="/insights" className="mx-4 mb-6 mt-6 block">
      <div className="ticket rounded-[4px] px-4 pb-3 pt-4 shadow-lift">
        <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[.2em] text-ink/55">
          <span>Ticket #0001</span>
          <span>Table 1</span>
        </div>
        <div className="mt-1 font-display text-[26px] leading-[1] text-ink">
          What&apos;s <span className="text-ember">Cooking?</span>
        </div>
        <div className="mt-2 border-t border-dashed border-ink/30 pt-1.5 font-hand text-xl text-ink/70">order up!</div>
      </div>
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

export function ThemeSwitch({ compact }: { compact?: boolean }) {
  const { theme, setTheme, sound, setSound } = useTheme();
  return (
    <div className={cx("flex items-center gap-1.5", compact ? "" : "justify-between")}>
      <div role="radiogroup" aria-label="Theme" className="flex rounded-full border border-line bg-black/40 p-0.5">
        {THEMES.map((th) => (
          <button
            key={th}
            role="radio"
            aria-checked={theme === th}
            onClick={() => setTheme(th)}
            className={cx(
              "rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider transition",
              theme === th ? "bg-gold text-ongold" : "text-muted hover:text-cream",
            )}
          >
            {th === "studio" ? (compact ? "🎬" : "🎬 Studio") : compact ? "🔔" : "🔔 Kitchen"}
          </button>
        ))}
      </div>
      <button
        onClick={() => setSound(!sound)}
        aria-label={sound ? "Mute sound effects" : "Unmute sound effects"}
        className="grid h-7 w-7 place-items-center rounded-full border border-line bg-black/40 text-xs text-muted hover:text-cream"
      >
        {sound ? "🔊" : "🔇"}
      </button>
    </div>
  );
}

export function Wordmark({ small }: { small?: boolean }) {
  const { theme } = useTheme();
  if (theme === "kitchen")
    return (
      <span className={cx("font-display leading-none text-cream", small ? "text-lg" : "text-2xl")}>
        What&apos;s <span className="text-gold">Cooking?</span>
      </span>
    );
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
function IconBoard({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" {...sv} aria-hidden>
      <path d="M5 21l3-6M19 21l-3-6" />
      <rect x="3" y="3" width="18" height="12" rx="1" />
      <path d="M7 8h6M7 11h9" />
    </svg>
  );
}
function IconFlame({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" {...sv} aria-hidden>
      <path d="M12 21c-4 0-6.5-2.6-6.5-6 0-3.5 3-5.5 3.5-9 2.5 1.5 3.5 4 3.5 5.5 1-1 1.5-2.2 1.5-3.5 2.5 2 4.5 4.5 4.5 7 0 3.4-2.5 6-6.5 6z" />
    </svg>
  );
}
function IconBell({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" {...sv} aria-hidden>
      <path d="M4 17h16M5 17a7 7 0 0 1 14 0M12 8V6M10 6h4" />
      <path d="M3 20h18" />
    </svg>
  );
}
function IconReceipt({ className }: IconProps) {
  return (
    <svg className={className} viewBox="0 0 24 24" {...sv} aria-hidden>
      <path d="M6 3h12v18l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5L6 21z" />
      <path d="M9 8h6M9 11h6M9 14h4" />
    </svg>
  );
}
