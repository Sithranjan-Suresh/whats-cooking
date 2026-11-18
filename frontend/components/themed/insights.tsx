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
  return <Headshots cards={cards} />;
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
