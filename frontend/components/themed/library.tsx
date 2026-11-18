"use client";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { cx, money, timeAgo } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import type { Video } from "@/lib/types";

export function VideoTileThemed({ v, onOpen, index, restaurant }: { v: Video; onOpen: () => void; index: number; restaurant?: string }) {
  const { theme } = useTheme();
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 30, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: Math.min(index, 8) * 0.06, type: "spring", stiffness: 140, damping: 18 }}
    >
      {theme === "studio" ? <Poster v={v} onOpen={onOpen} restaurant={restaurant} /> : <Plate v={v} onOpen={onOpen} />}
    </motion.div>
  );
}

function Poster({ v, onOpen, restaurant }: { v: Video; onOpen: () => void; restaurant?: string }) {
  const showing = v.publish_status === "published";
  return (
    <article className="group">
      <button
        onClick={onOpen}
        aria-label={`Play ${v.dish ?? "video"}`}
        className="relative block aspect-[2/3] w-full overflow-hidden rounded-[4px] bg-black text-left shadow-lift ring-1 ring-white/10 transition duration-500 group-hover:-translate-y-1 group-hover:shadow-[0_30px_60px_-20px_rgb(var(--gold)/.35)]"
      >
        {v.poster_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={v.poster_url} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover transition duration-700 group-hover:scale-105" />
        )}
        <div className="absolute inset-0 bg-gradient-to-b from-black/70 via-transparent to-black/95" />
        <div className="absolute inset-x-0 top-2.5 text-center font-mono text-[8.5px] uppercase tracking-[.3em] text-cream/75">
          {restaurant ?? "The kitchen"} presents
        </div>
        <div className="absolute inset-x-2 bottom-2">
          <div className="font-display text-[clamp(22px,4.2vw,34px)] uppercase leading-[.85] tracking-[.02em] text-cream [text-shadow:0_2px_12px_rgb(0_0_0/.8)]">{v.dish ?? "Untitled"}</div>
          <div className="mt-1.5 border-t border-white/25 pt-1 font-mono text-[7.5px] uppercase leading-snug tracking-[.12em] text-cream/60">
            Starring {v.dish ?? "the dish"} · {v.mode === "veo" ? "shot on Veo" : "free camera rig"} · {Math.round(v.duration_s)}s · {timeAgo(v.created_at)}
          </div>
        </div>
        {showing && (
          <div className="absolute right-2 top-7 rotate-6 rounded-sm bg-gold px-1.5 py-0.5 font-display text-[13px] uppercase tracking-[.12em] text-ongold shadow-glow">Now showing</div>
        )}
        {v.publish_status === "publishing" && <div className="absolute right-2 top-7 rounded-sm bg-ember px-1.5 py-0.5 font-display text-[13px] uppercase tracking-[.12em] text-cream">Premiering {v.publish_progress}%</div>}
        {v.publish_status === "failed" && <div className="absolute right-2 top-7 rounded-sm bg-bad px-1.5 py-0.5 font-display text-[13px] uppercase text-ongold">Premiere failed</div>}
        <span className="absolute inset-0 grid place-items-center opacity-0 transition group-hover:opacity-100">
          <span className="grid h-14 w-14 place-items-center rounded-full border border-gold/70 bg-black/60 text-xl text-gold backdrop-blur">▶</span>
        </span>
      </button>
      <div className="mt-2 flex items-center justify-between px-0.5 font-mono text-[11px] text-muted">
        <span>{v.mode === "veo" ? "★ Veo" : "Free rig"}</span>
        <span className="text-gold/90">Budget {money(v.cost_cents)}</span>
      </div>
    </article>
  );
}

function Plate({ v, onOpen }: { v: Video; onOpen: () => void }) {
  const served = v.publish_status === "published";
  return (
    <article className="group relative">
      <div className="pointer-events-none absolute -inset-x-2 -top-6 h-24 opacity-0 transition duration-500 heatlamp group-hover:opacity-100" aria-hidden />
      <button onClick={onOpen} aria-label={`Play ${v.dish ?? "video"}`} className="relative block aspect-[9/16] w-full overflow-hidden rounded-[6px] bg-black shadow-lift ring-1 ring-black/60">
        {v.poster_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={v.poster_url} alt="" loading="lazy" className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.04]" />
        )}
        <span className="absolute inset-0 grid place-items-center opacity-0 transition group-hover:opacity-100">
          <span className="grid h-14 w-14 place-items-center rounded-full bg-ember text-xl text-paper shadow-lg">▶</span>
        </span>
        {served && (
          <span className="absolute left-1/2 top-1/3 -translate-x-1/2 -rotate-12 rounded-md border-4 border-ok bg-paper/85 px-3 py-0.5 font-display text-2xl uppercase text-[#2f8a3c] shadow">Served</span>
        )}
      </button>
      {/* ticket clipped under the plate */}
      <div className="ticket ticket-zigzag relative -mt-2 mx-2 rounded-t-[2px] px-3 pt-3 font-mono text-[11.5px] shadow-lift transition group-hover:rotate-[-1deg]">
        <span className="absolute -top-1.5 left-1/2 h-3 w-10 -translate-x-1/2 rounded-sm bg-[#8e969d] shadow" aria-hidden />
        <div className="truncate text-[13px] font-semibold uppercase">{v.dish ?? "Plate"}</div>
        <div className="mt-1 flex justify-between text-ink/60">
          <span>{timeAgo(v.created_at)}</span>
          <span>{v.mode === "veo" ? "VEO" : "FREE"}</span>
        </div>
        <div className="mt-1 flex justify-between border-t border-dashed border-ink/30 pt-1">
          <span className="text-ink/60">{v.publish_status === "publishing" ? `running ${v.publish_progress}%` : v.publish_status === "failed" ? "86'd: retry" : served ? "served ✓" : "on the pass"}</span>
          <span className="font-semibold">{money(v.cost_cents)}</span>
        </div>
      </div>
    </article>
  );
}

// ================================================================ publish celebration

export function Celebration({ show, onDone }: { show: boolean; onDone: () => void }) {
  const { theme, t } = useTheme();
  const reduce = useReducedMotion();
  return (
    <AnimatePresence onExitComplete={() => {}}>
      {show && !reduce && (
        <motion.div
          key="celebrate"
          className="pointer-events-none fixed inset-0 z-[80] grid place-items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onAnimationComplete={() => setTimeout(onDone, 2200)}
        >
          {theme === "studio" ? (
            <>
              <div className="absolute inset-0 bg-black/60" />
              {/* red carpet rolling out */}
              <motion.div
                className="absolute bottom-0 left-1/2 w-[46vw] max-w-[520px] -translate-x-1/2 origin-bottom bg-[linear-gradient(90deg,#5b0710,#b0182a_20%,#c41e33_50%,#b0182a_80%,#5b0710)] [clip-path:polygon(38%_0,62%_0,100%_100%,0_100%)]"
                initial={{ height: 0 }}
                animate={{ height: "78vh" }}
                transition={{ duration: 1.1, ease: [0.2, 0.8, 0.2, 1] }}
              />
              {/* camera flashes */}
              {[...Array(7)].map((_, i) => (
                <motion.span
                  key={i}
                  className="absolute h-24 w-24 rounded-full bg-white blur-2xl"
                  style={{ left: `${10 + ((i * 37) % 80)}%`, top: `${15 + ((i * 23) % 50)}%` }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0, 0.9, 0] }}
                  transition={{ delay: 0.7 + i * 0.18, duration: 0.35 }}
                />
              ))}
              <motion.div
                className="relative text-center"
                initial={{ scale: 0.7, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.9, type: "spring", stiffness: 160, damping: 14 }}
              >
                <div className="font-mono text-sm uppercase tracking-[.4em] text-gold2">World premiere</div>
                <div className="font-display text-[clamp(56px,10vw,120px)] uppercase leading-none text-gold [text-shadow:0_0_40px_rgb(var(--gold)/.8)]">{t.library.live}</div>
              </motion.div>
            </>
          ) : (
            <>
              <div className="absolute inset-0 bg-black/50" />
              <motion.div
                className="relative rounded-xl border-[6px] border-[#2f8a3c] bg-paper px-10 py-5 text-center shadow-2xl"
                initial={{ scale: 3, rotate: -30, opacity: 0 }}
                animate={{ scale: 1, rotate: -8, opacity: 1 }}
                transition={{ type: "spring", stiffness: 420, damping: 16 }}
              >
                <div className="font-display text-[clamp(48px,9vw,96px)] uppercase leading-none text-[#2f8a3c]">Served!</div>
                <div className="mt-1 font-mono text-sm uppercase tracking-[.3em] text-ink/70">on YouTube · table 1</div>
              </motion.div>
            </>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function TileCls(theme: string) {
  return cx(theme === "studio" ? "grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 lg:grid-cols-4" : "grid grid-cols-2 gap-x-5 gap-y-10 pt-4 sm:grid-cols-3 lg:grid-cols-4");
}
