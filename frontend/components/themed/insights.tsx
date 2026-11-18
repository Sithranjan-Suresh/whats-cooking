"use client";
import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { cx } from "@/lib/format";
import type { InsightCard } from "@/lib/types";
import { useTheme } from "@/lib/theme";

function bigMetric(c: InsightCard) {
  if (c.angle === "rising") return { big: `+${c.metric.wow_pct ?? 0}%`, unit: "vs last week" };
  if (c.angle === "top_seller") return { big: `${c.metric.qty_7d ?? 0}`, unit: "sold this week" };
  return { big: `${c.metric.qty_14d ?? 0}`, unit: "sold in 14 days" };
}

export function InsightBoard({ cards }: { cards: InsightCard[] }) {
  const { theme } = useTheme();
  return theme === "studio" ? <Headshots cards={cards} /> : <SpecialsBoard cards={cards} />;
}

// ================================================================ STUDIO: casting headshots

function Headshots({ cards }: { cards: InsightCard[] }) {
  const reduce = useReducedMotion();
  return (
    <div className="grid gap-6 md:grid-cols-3">
      {cards.map((c, i) => (
        <motion.div
          key={c.id}
          initial={reduce ? false : { opacity: 0, y: 40, rotate: i === 1 ? 0 : i === 0 ? -3 : 3 }}
          animate={{ opacity: 1, y: 0, rotate: 0 }}
          transition={{ delay: 0.12 + i * 0.12, type: "spring", stiffness: 120, damping: 16 }}
        >
          <Headshot card={c} lead={i === 0 && c.angle === "rising"} />
        </motion.div>
      ))}
    </div>
  );
}

function Headshot({ card, lead }: { card: InsightCard; lead: boolean }) {
  const { t } = useTheme();
  const a = t.angle[card.angle];
  const { big, unit } = bigMetric(card);
  return (
    <article className="group relative">
      {/* 8x10 glossy with a white border, like a real headshot */}
      <div
        className={cx(
          "relative overflow-hidden rounded-[6px] bg-[#f4efe6] p-2.5 pb-14 shadow-lift transition duration-500 group-hover:-translate-y-1.5 group-hover:rotate-[-.6deg]",
          lead && "ring-2 ring-gold/80 shadow-[0_0_70px_-10px_rgb(var(--gold)/.55)]",
        )}
      >
        <div className="relative aspect-[4/5] overflow-hidden rounded-[2px] bg-black">
          {card.menu_item.photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={card.menu_item.photo_url}
              alt={card.menu_item.name}
              loading="lazy"
              className="h-full w-full object-cover grayscale-[.35] contrast-[1.1] transition duration-700 group-hover:scale-105 group-hover:grayscale-0"
            />
          ) : (
            <div className="grid h-full place-items-center text-sm text-muted">No headshot yet</div>
          )}
          {/* spotlight sweep on the lead */}
          {lead && <div className="spotlight pointer-events-none absolute inset-0" aria-hidden />}
          <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/80 to-transparent" />
          <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between">
            <span className="font-display text-[44px] leading-none text-gold [text-shadow:0_0_24px_rgb(var(--gold)/.7)]">{big}</span>
            <span className="mb-1 font-mono text-[11px] uppercase tracking-widest text-cream/80">{unit}</span>
          </div>
          <div className="absolute left-0 top-4 bg-ember px-3 py-1 font-display text-[15px] uppercase tracking-[.18em] text-cream shadow-lg">{a.label}</div>
        </div>
        {/* signature line on the white border */}
        <div className="absolute inset-x-3 bottom-2.5 flex items-end justify-between text-[#1a0d0b]">
          <span className="font-display text-[30px] uppercase leading-none tracking-[.02em]">{card.menu_item.name}</span>
          {card.menu_item.price && <span className="mb-0.5 font-mono text-[13px]">{card.menu_item.price}</span>}
        </div>
      </div>
      <p className="mt-4 min-h-[60px] px-1 font-mono text-[13.5px] leading-relaxed text-cream/85">“{card.reason}”</p>
      <div className="mt-1 px-1 text-[10.5px] uppercase tracking-[.2em] text-muted">
        {card.reason_source === "gemini" ? "Notes by Gemini · numbers from your sales" : "Notes from your sales numbers"}
      </div>
      <Link
        href={`/studio?insight=${card.id}`}
        className="mt-4 flex min-h-[50px] items-center justify-center gap-2 rounded-xl bg-gold font-display text-[22px] uppercase tracking-[.1em] text-ongold shadow-[0_10px_30px_-10px_rgb(var(--gold)/.8)] transition hover:bg-gold2 hover:tracking-[.14em]"
      >
        ★ {a.cta}
      </Link>
    </article>
  );
}

// ================================================================ KITCHEN: chalk specials board

function SpecialsBoard({ cards }: { cards: InsightCard[] }) {
  const reduce = useReducedMotion();
  return (
    <div className="chalkboard relative rounded-[10px] px-5 pb-8 pt-6 sm:px-9 sm:pt-8">
      <div className="mb-6 flex items-baseline justify-between gap-4 border-b border-dashed border-white/20 pb-4">
        <h2 className="chalk-text font-hand text-[44px] leading-none sm:text-[56px]">Today&apos;s Specials</h2>
        <span className="chalk-text hidden font-hand text-2xl opacity-70 sm:block">picked by your sales ✓</span>
      </div>
      <ul className="grid gap-8 md:grid-cols-3 md:gap-6">
        {cards.map((c, i) => (
          <motion.li
            key={c.id}
            initial={reduce ? false : { opacity: 0, clipPath: "inset(0 100% 0 0)" }}
            animate={{ opacity: 1, clipPath: "inset(0 0% 0 0)" }}
            transition={{ delay: 0.15 + i * 0.25, duration: 0.9, ease: "easeOut" }}
          >
            <Special card={c} hot={i === 0 && c.angle === "rising"} index={i} />
          </motion.li>
        ))}
      </ul>
      {/* chalk tray */}
      <div className="absolute -bottom-3 left-6 right-6 h-3 rounded-b-md bg-[#3a2819] shadow-[0_4px_8px_rgb(0_0_0/.5)]" aria-hidden>
        <span className="absolute -top-1 left-10 h-2 w-8 rounded-full bg-white/90" />
        <span className="absolute -top-1 left-24 h-2 w-5 rounded-full bg-[#f5c46b]" />
      </div>
    </div>
  );
}

function Special({ card, hot, index }: { card: InsightCard; hot: boolean; index: number }) {
  const { t } = useTheme();
  const a = t.angle[card.angle];
  const { big, unit } = bigMetric(card);
  const tilt = ["-rotate-2", "rotate-1", "-rotate-1"][index % 3];
  return (
    <div className="group flex h-full flex-col">
      {/* polaroid taped to the board */}
      <div className={cx("relative mx-auto w-[82%] bg-[#fbf8f1] p-2 pb-8 shadow-[0_10px_20px_rgb(0_0_0/.45)] transition duration-300 group-hover:rotate-0 group-hover:scale-[1.03]", tilt)}>
        <span className="absolute -top-3 left-1/2 h-6 w-20 -translate-x-1/2 rotate-[-3deg] bg-[#f3e6a9]/80 shadow-sm" aria-hidden />
        <div className="relative aspect-[4/3] overflow-hidden bg-black">
          {card.menu_item.photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={card.menu_item.photo_url} alt={card.menu_item.name} loading="lazy" className="h-full w-full object-cover" />
          ) : (
            <div className="grid h-full place-items-center text-sm text-muted">no photo yet</div>
          )}
          {hot && (
            <div className="absolute inset-x-0 bottom-0 flex justify-center gap-3" aria-hidden>
              {[0, 1, 2].map((s) => (
                <span key={s} className="block h-8 w-3 animate-steam rounded-full bg-white/40 blur-[3px]" style={{ animationDelay: `${s * 0.6}s` }} />
              ))}
            </div>
          )}
        </div>
        <span className="absolute bottom-1.5 left-0 right-0 text-center font-hand text-[22px] leading-none text-ink">{card.menu_item.name}</span>
      </div>
      <div className="mt-5 flex items-center justify-between gap-2">
        <span className="chalk-text font-hand text-[30px] leading-none">{a.label}</span>
        <span className={cx("rounded-full border-2 px-2.5 py-0.5 font-hand text-xl leading-none", hot ? "border-[#ff9a6b] text-[#ffb08a]" : "border-white/50 chalk-text")}>{a.badge}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className={cx("font-hand text-[54px] font-bold leading-none", hot ? "text-[#ffb08a]" : "chalk-text")}>{big}</span>
        <span className="chalk-text font-hand text-2xl opacity-80">{unit}</span>
      </div>
      <svg viewBox="0 0 200 8" className="mt-1 h-2 w-40 text-white/60" aria-hidden>
        <path d="M2 5 C 50 1, 120 8, 198 3" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      </svg>
      <p className="chalk-text mt-3 flex-1 font-hand text-[23px] leading-[1.15] opacity-90">{card.reason}</p>
      <Link
        href={`/studio?insight=${card.id}`}
        className="mt-5 inline-flex min-h-[48px] items-center justify-center gap-2 rounded-[4px] bg-ember font-mono text-sm font-semibold uppercase tracking-[.2em] text-paper shadow-[0_3px_0_0_rgb(0_0_0/.6)] transition hover:brightness-110 active:translate-y-[2px] active:shadow-none"
      >
        🔥 {a.cta}
      </Link>
    </div>
  );
}
