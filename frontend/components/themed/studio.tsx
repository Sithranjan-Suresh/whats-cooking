"use client";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cx, elapsed, FALLBACK_LABEL } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import { bell, clap, primeAudio, whoosh } from "@/lib/sfx";
import type { Job, Script, Stage } from "@/lib/types";
import { Spinner } from "@/components/ui";
import { PhonePlayer } from "@/components/studio";

const ORDER = ["analyze", "script", "visuals", "voice", "assemble"] as const;
const blank: Stage[] = ORDER.map((n) => ({ name: n, status: "pending", started_at: null, ended_at: null, note: null }));

function useNow(active: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(t);
  }, [active]);
  return now;
}

// ================================================================ Generate button

export function GenerateButton({ onClick, disabled, loading }: { onClick: () => void; disabled?: boolean; loading?: boolean }) {
  const { theme, t, sound } = useTheme();
  const reduce = useReducedMotion();
  const [snap, setSnap] = useState(false);
  const fire = () => {
    primeAudio();
    if (sound) (theme === "studio" ? clap : whoosh)();
    setSnap(true);
    setTimeout(() => setSnap(false), 700);
    onClick();
  };

  if (theme === "studio") {
    return (
      <button
        onClick={fire}
        disabled={disabled || loading}
        className="group relative mt-4 block w-full select-none pt-14 disabled:cursor-not-allowed disabled:opacity-45"
        aria-label={t.studio.generate}
      >
        {/* clapstick */}
        <motion.div
          className="relative z-10 h-8 origin-[2%_100%] rounded-t-[6px] border-2 border-black bg-[repeating-linear-gradient(-55deg,#f6efe4_0_22px,#111_22px_44px)]"
          initial={false}
          animate={{ rotate: snap || loading ? 0 : reduce ? 0 : -5 }}
          whileHover={disabled || loading || reduce ? undefined : { rotate: -7 }}
          transition={{ type: "spring", stiffness: 900, damping: 22 }}
        />
        {/* slate */}
        <div className="relative -mt-0.5 overflow-hidden rounded-b-[8px] border-2 border-black bg-[#111] px-5 py-3 text-left shadow-[0_18px_40px_-14px_rgb(var(--gold)/.5)]">
          <div className="grid grid-cols-3 gap-2 border-b border-white/25 pb-1.5 font-mono text-[10px] uppercase tracking-[.2em] text-white/55">
            <span>Prod. What&apos;s Cooking?</span>
            <span className="text-center">Scene 1</span>
            <span className="text-right">Take 1</span>
          </div>
          <div className="flex items-center justify-between pt-1.5">
            <span className="font-display text-[44px] uppercase leading-none tracking-[.06em] text-cream group-hover:text-gold">
              {loading ? t.studio.generating : t.studio.generate}
            </span>
            {loading ? <Spinner className="h-7 w-7 text-gold" /> : <span className="font-display text-xl text-gold">★</span>}
          </div>
        </div>
        <AnimatePresence>
          {snap && !reduce && (
            <motion.span
              className="pointer-events-none absolute inset-0 rounded-[10px] bg-white"
              initial={{ opacity: 0.55 }}
              animate={{ opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35 }}
            />
          )}
        </AnimatePresence>
      </button>
    );
  }

  // kitchen: Fire!
  return (
    <button
      onClick={fire}
      disabled={disabled || loading}
      className="group relative mt-6 flex min-h-[72px] w-full items-center justify-center gap-3 overflow-hidden rounded-[6px] bg-ember font-display text-[34px] uppercase leading-none text-paper shadow-[0_5px_0_0_#7a1a10,0_18px_40px_-12px_rgb(var(--ember)/.7)] transition active:translate-y-[4px] active:shadow-[0_1px_0_0_#7a1a10] disabled:cursor-not-allowed disabled:opacity-45"
    >
      <span className="relative inline-block h-9 w-7" aria-hidden>
        <span className="absolute inset-x-0 bottom-0 h-full origin-bottom animate-flame rounded-[50%_50%_45%_45%/60%_60%_40%_40%] bg-gradient-to-t from-[#ffcf4a] via-[#ff8a3d] to-transparent" />
        <span className="absolute inset-x-1.5 bottom-0 h-1/2 origin-bottom animate-flame rounded-full bg-[#fff2b0]" style={{ animationDelay: ".12s" }} />
      </span>
      {loading ? t.studio.generating : t.studio.generate}
      <AnimatePresence>
        {snap && !reduce && (
          <motion.span
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_120%,#ffd36b,#ff7a2f_40%,transparent_70%)]"
            initial={{ opacity: 0.9, scale: 0.6 }}
            animate={{ opacity: 0, scale: 1.6 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
          />
        )}
      </AnimatePresence>
    </button>
  );
}

// ================================================================ Stage board

export function StageBoard({ job }: { job: Job | null }) {
  const { theme } = useTheme();
  return theme === "studio" ? <FilmStrip job={job} /> : <KitchenTicket job={job} />;
}

function stageBits(job: Job | null, st: Stage, now: number) {
  const t = elapsed(st.started_at, st.ended_at, now);
  const waiting = job?.status === "needs_dish" && st.name === "analyze";
  return { t, waiting };
}

function FilmStrip({ job }: { job: Job | null }) {
  const { t } = useTheme();
  const running = !!job && ["queued", "running"].includes(job.status);
  const now = useNow(running);
  const stages = job?.stages ?? blank;
  const total = job ? elapsed(job.created_at, job.finished_at, now) : null;
  return (
    <div>
      <div className="mb-3 flex items-center justify-between font-mono text-[11px] uppercase tracking-[.25em] text-muted">
        <span>Production log</span>
        {total != null && <span className="text-gold">⏱ {total.toFixed(1)}s</span>}
      </div>
      <ol className="relative overflow-hidden rounded-[6px] bg-black px-7 py-1" aria-live="polite">
        {/* sprocket holes */}
        <Sprockets side="left" />
        <Sprockets side="right" />
        {stages.map((st) => {
          const { t: secs, waiting } = stageBits(job, st, now);
          const label = t.stages[st.name];
          const live = st.status === "running" && !waiting;
          return (
            <li
              key={st.name}
              className={cx(
                "relative my-1.5 flex items-center gap-3 rounded-[3px] border px-3 py-2.5 transition duration-500",
                st.status === "done" ? "border-gold/25 bg-[#1a1210]" : live ? "border-gold/70 bg-[#241812]" : "border-white/10 bg-[#0d0a0a]",
              )}
            >
              <span className="w-6 text-center">
                {st.status === "done" ? (
                  <motion.span initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="font-display text-xl text-gold">
                    ✓
                  </motion.span>
                ) : st.status === "failed" ? (
                  <span className="font-display text-xl text-bad">✕</span>
                ) : live ? (
                  <span className="relative block h-3 w-3 rounded-full bg-bad">
                    <span className="absolute inset-0 animate-ping rounded-full bg-bad" />
                  </span>
                ) : waiting ? (
                  <span className="font-display text-xl text-gold">?</span>
                ) : (
                  <span className="block h-2 w-2 rounded-full bg-white/20" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className={cx("font-display text-[24px] uppercase leading-none tracking-[.06em]", st.status === "pending" ? "text-white/30" : "text-cream")}>{label.title}</div>
                <div className="mt-0.5 truncate font-mono text-[11.5px] text-muted">{st.note || label.sub}</div>
                {st.name === "visuals" && st.status === "done" && (job?.veo_used || job?.fallback_reason) && (
                  <div className={cx("mt-1 inline-block rounded-sm px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest", job?.veo_used ? "bg-gold text-ongold" : "bg-white/10 text-cream/80")}>
                    {job?.veo_used ? "Shot on Veo" : `Free rig · ${FALLBACK_LABEL[job!.fallback_reason!] ?? "Veo unavailable"}`}
                  </div>
                )}
              </div>
              {secs != null && st.status !== "pending" && <span className="font-mono text-xs text-gold/80">{secs.toFixed(1)}s</span>}
              {live && <span className="absolute -left-px bottom-0 top-0 w-[3px] bg-bad shadow-[0_0_12px_rgb(var(--bad))]" />}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Sprockets({ side }: { side: "left" | "right" }) {
  return (
    <div className={cx("absolute bottom-0 top-0 flex w-4 flex-col justify-around py-1", side === "left" ? "left-1.5" : "right-1.5")} aria-hidden>
      {Array.from({ length: 14 }).map((_, i) => (
        <span key={i} className="h-2.5 w-3 rounded-[2px] bg-[#2a201c]" />
      ))}
    </div>
  );
}

function KitchenTicket({ job }: { job: Job | null }) {
  const { t } = useTheme();
  const running = !!job && ["queued", "running"].includes(job.status);
  const now = useNow(running);
  const stages = job?.stages ?? blank;
  const total = job ? elapsed(job.created_at, job.finished_at, now) : null;
  const created = job ? new Date(job.created_at) : null;
  return (
    <div className="relative pt-3">
      {/* ticket rail */}
      <div className="steel absolute inset-x-[-12px] top-0 h-4 rounded-sm border-b border-black/60 shadow-[0_3px_6px_rgb(0_0_0/.5)]" aria-hidden />
      <motion.div
        initial={{ y: -16, opacity: 0, rotate: -2 }}
        animate={{ y: 0, opacity: 1, rotate: running ? [0, -0.8, 0.6, 0] : -0.6 }}
        transition={running ? { rotate: { repeat: Infinity, duration: 3 } } : { type: "spring", stiffness: 140, damping: 14 }}
        className="ticket ticket-zigzag relative mx-2 rounded-t-[2px] px-5 pt-5 font-mono text-[13px] shadow-lift"
      >
        <div className="flex justify-between text-[11px] uppercase tracking-widest text-ink/60">
          <span>Ticket #{job ? String(job.id).padStart(4, "0") : "----"}</span>
          <span>{created ? created.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "--:--"}</span>
        </div>
        <div className="mt-1 border-b-2 border-dashed border-ink/30 pb-2 text-[18px] font-semibold uppercase tracking-wide text-ink">
          1× {job?.menu_item?.name ?? "New Short"}
        </div>
        <ul className="mt-2 space-y-2" aria-live="polite">
          {stages.map((st) => {
            const { t: secs, waiting } = stageBits(job, st, now);
            const label = t.stages[st.name];
            const done = st.status === "done";
            return (
              <li key={st.name} className="relative flex items-baseline gap-2">
                <span className={cx("w-20 shrink-0 font-semibold uppercase", done ? "text-ink/45 line-through decoration-2" : "text-ink")}>{label.title}</span>
                <span className="min-w-0 flex-1 truncate border-b border-dotted border-ink/30 text-[11px] text-ink/55">{st.note || label.sub}</span>
                <span className="w-14 text-right text-[12px] text-ink/70">
                  {st.status === "running" && !waiting ? <Spinner className="ml-auto h-3.5 w-3.5 text-ember" /> : secs != null && st.status !== "pending" ? `${secs.toFixed(1)}s` : "--"}
                </span>
                {done && (
                  <motion.span
                    initial={{ scale: 2.2, opacity: 0, rotate: -20 }}
                    animate={{ scale: 1, opacity: 1, rotate: -8 }}
                    className="absolute -left-4 top-0 rounded-sm border-2 border-[#2f8a3c] px-0.5 text-[9px] font-semibold leading-tight text-[#2f8a3c]"
                  >
                    ✓
                  </motion.span>
                )}
                {st.status === "failed" && <span className="absolute -left-5 top-0 rounded-sm border-2 border-ember px-1 text-[10px] font-semibold uppercase text-ember">86</span>}
                {waiting && <span className="absolute -left-6 top-0 rounded-sm border-2 border-[#c47a17] px-1 text-[10px] font-semibold uppercase text-[#c47a17]">hold</span>}
              </li>
            );
          })}
        </ul>
        {job?.fallback_reason && job.status === "done" && <div className="mt-3 text-[11px] uppercase text-ink/60">Note: free camera · {FALLBACK_LABEL[job.fallback_reason] ?? "Veo unavailable"}</div>}
        {job?.veo_used && <div className="mt-3 text-[11px] font-semibold uppercase text-ember">Note: live motion by Veo</div>}
        <div className="mt-3 flex justify-between border-t-2 border-dashed border-ink/30 pt-2 text-[12px] uppercase text-ink/70">
          <span>Time on the line</span>
          <span>{total != null ? `${total.toFixed(1)}s` : "--"}</span>
        </div>
      </motion.div>
    </div>
  );
}

// ================================================================ Script sheet

export function ScriptSheet({ script, loading, restaurant }: { script: Script | null; loading: boolean; restaurant?: string }) {
  const { theme, t } = useTheme();
  const studio = theme === "studio";
  if (!script) {
    return (
      <div>
        <div className="mb-3 font-mono text-[11px] uppercase tracking-[.25em] text-muted">{t.studio.scriptTitle}</div>
        {loading ? (
          <div className="space-y-2.5" aria-hidden>
            {[80, 60, 92, 70, 85].map((w, i) => (
              <div key={i} className="h-3.5 animate-pulse rounded bg-panel2" style={{ width: `${w}%` }} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">
            {studio ? "The screenplay types itself here the moment the script is written. Every line comes from your menu." : "The ticket prints here as soon as the kitchen writes it. Every line comes from your menu."}
          </p>
        )}
      </div>
    );
  }
  const badge =
    script.source === "template" ? "From the menu" : script.source === "edited" ? "Edited · menu-checked" : "Grounded in your menu";
  if (studio) {
    return (
      <div>
        <div className="mb-3 flex items-center justify-between">
          <span className="font-mono text-[11px] uppercase tracking-[.25em] text-muted">{t.studio.scriptTitle}</span>
          <span className="rounded-sm bg-gold/15 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-gold">{badge}</span>
        </div>
        {/* screenplay page */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative rounded-[3px] bg-[#f6f1e7] px-6 py-6 font-mono text-[13px] leading-[1.55] text-[#1b1512] shadow-[0_20px_50px_-20px_rgb(0_0_0/.9)]"
        >
          <span className="absolute left-2.5 top-8 h-2.5 w-2.5 rounded-full bg-[#cfc6b6]" aria-hidden />
          <span className="absolute left-2.5 top-1/2 h-2.5 w-2.5 rounded-full bg-[#cfc6b6]" aria-hidden />
          <span className="absolute bottom-8 left-2.5 h-2.5 w-2.5 rounded-full bg-[#cfc6b6]" aria-hidden />
          <p className="font-bold uppercase">INT. {(restaurant ?? "THE RESTAURANT").toUpperCase()} — DINNER RUSH</p>
          <p className="mt-2">
            Close on the dish. Steam curls toward the light. <span className="uppercase">SUPER:</span>
          </p>
          <p className="mt-1 text-center text-[17px] font-bold uppercase">“{script.hook}”</p>
          {script.beats.map((b, i) => (
            <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 + i * 0.12 }} className="mt-2">
              <span className="uppercase">SUPER:</span> {b.caption.replace(/\n/g, " ")}
              <span className="ml-1 text-[11px] text-[#8a7d6e]">({b.seconds.toFixed(1)}s)</span>
              {(b.facts ?? []).length > 0 && (
                <span className="ml-1.5 whitespace-nowrap rounded-sm bg-[#1b1512] px-1 py-px align-middle text-[9.5px] uppercase tracking-wider text-[#f6f1e7]">menu: {(b.facts ?? []).join(" + ")}</span>
              )}
            </motion.div>
          ))}
          <p className="mt-4 text-center font-bold uppercase">{t.studio.voiceover}</p>
          <p className="mx-auto max-w-[85%]">{script.voiceover}</p>
          <p className="mt-4 text-right font-bold uppercase">CUT TO: END CARD.</p>
        </motion.div>
        <Details script={script} />
      </div>
    );
  }
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-[.25em] text-muted">{t.studio.scriptTitle}</span>
        <span className="rounded-[3px] border border-ok/50 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-ok">{badge}</span>
      </div>
      <motion.div
        initial={{ clipPath: "inset(0 0 100% 0)" }}
        animate={{ clipPath: "inset(0 0 0% 0)" }}
        transition={{ duration: 0.9, ease: "easeOut" }}
        className="ticket ticket-zigzag rounded-t-[2px] px-5 pt-4 font-mono text-[13px] text-ink shadow-lift"
      >
        <div className="text-center text-[11px] uppercase tracking-[.3em] text-ink/55">— expo —</div>
        <div className="mt-2 text-center text-[19px] font-semibold uppercase leading-tight">{script.hook}</div>
        <div className="my-3 border-t-2 border-dashed border-ink/30" />
        {script.beats.map((b, i) => (
          <div key={i} className="flex gap-2 py-0.5">
            <span className="w-5 text-ink/45">{i + 1}.</span>
            <span className="flex-1 font-semibold">{b.caption.replace(/\n/g, " ")}</span>
            <span className="text-ink/50">{b.seconds.toFixed(1)}s</span>
          </div>
        ))}
        <div className="my-3 border-t-2 border-dashed border-ink/30" />
        <div className="text-[11px] uppercase tracking-widest text-ink/55">{t.studio.voiceover}</div>
        <p className="mt-1 text-[12.5px] leading-relaxed">{script.voiceover}</p>
        <div className="mt-3 text-center font-hand text-2xl text-ember">every fact from your menu ✓</div>
      </motion.div>
      <Details script={script} />
    </div>
  );
}

function Details({ script }: { script: Script }) {
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-muted hover:text-cream">YouTube title, description &amp; hashtags</summary>
      <div className="mt-2 space-y-1 text-cream/90">
        <div className="font-semibold">{script.title}</div>
        <div className="text-muted">{script.description}</div>
        <div className="text-gold">{script.hashtags.join(" ")}</div>
      </div>
    </details>
  );
}

// ================================================================ Player stage (signature moment)

export function PlayerStage({
  job,
  previewImg,
  busy,
  children,
}: {
  job: Job | null;
  previewImg: string | null;
  busy: boolean;
  children?: ReactNode;
}) {
  const { theme, t, sound } = useTheme();
  const reduce = useReducedMotion();
  const done = job?.status === "done" && !!job.video;
  const [revealKey, setRevealKey] = useState<number | null>(null);
  const prev = useRef<string | undefined>(undefined);
  useEffect(() => {
    // play the reveal only when a job transitions to done while we watch
    if (job && prev.current && prev.current !== "done" && job.status === "done") {
      setRevealKey(job.id);
      if (theme === "kitchen" && sound) bell();
    }
    prev.current = job?.status;
  }, [job, theme, sound]);
  const revealing = revealKey === job?.id && !reduce;

  const player = (
    <PhonePlayer
      src={done ? job!.video!.url : null}
      poster={job?.video?.poster_url}
      placeholder={job?.photo_url ?? previewImg}
      overlay={
        busy ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 bg-black/45 p-6 text-center">
            {theme === "studio" ? <ReelSpinner /> : <Steam />}
            <div className={cx("text-cream", theme === "studio" ? "font-display text-3xl uppercase tracking-[.12em]" : "font-display text-2xl")}>{t.studio.working}…</div>
            <div className="font-mono text-[11px] text-cream/75">{job?.stages.find((s) => s.status === "running")?.note || ""}</div>
          </div>
        ) : !job && !previewImg ? (
          <div className="flex h-full items-center justify-center p-6 text-center font-mono text-xs uppercase tracking-widest text-muted">{t.studio.placeholder}</div>
        ) : null
      }
    />
  );

  if (theme === "studio") {
    return (
      <div className="relative mx-auto max-w-[340px]">
        {/* marquee frame: bulbs chase while rendering */}
        <div className="relative rounded-[40px] bg-gradient-to-b from-[#2a1712] to-[#120a08] p-5 ring-1 ring-gold/25">
          <MarqueeFrame chasing={busy} lit={done} />
          <div className="relative mx-auto max-w-[300px] overflow-hidden rounded-[32px]">
            {player}
            {/* curtains */}
            <AnimatePresence>
              {revealing && (
                <>
                  <motion.div
                    key="l"
                    className="velvet pointer-events-none absolute inset-y-0 left-0 z-20 w-1/2 rounded-l-[30px]"
                    initial={{ x: 0 }}
                    animate={{ x: "-104%" }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 1.3, ease: [0.7, 0, 0.3, 1], delay: 0.25 }}
                  />
                  <motion.div
                    key="r"
                    className="velvet pointer-events-none absolute inset-y-0 right-0 z-20 w-1/2 rounded-r-[30px]"
                    initial={{ x: 0 }}
                    animate={{ x: "104%" }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 1.3, ease: [0.7, 0, 0.3, 1], delay: 0.25 }}
                  />
                </>
              )}
            </AnimatePresence>
          </div>
        </div>
        {done && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: revealing ? 1.4 : 0 }} className="mt-4 text-center font-display text-[30px] uppercase tracking-[.14em] text-gold [text-shadow:0_0_20px_rgb(var(--gold)/.6)]">
            ★ {t.studio.ready} ★
          </motion.div>
        )}
        {children}
      </div>
    );
  }

  // kitchen: the pass under heat lamps
  return (
    <div className="relative mx-auto max-w-[340px]">
      <div className="pointer-events-none absolute -inset-x-6 -top-10 h-64 heatlamp" aria-hidden />
      <div className="relative mb-3 flex justify-center gap-16" aria-hidden>
        {[0, 1].map((i) => (
          <div key={i} className="flex flex-col items-center">
            <span className="h-4 w-0.5 bg-[#555]" />
            <span className={cx("h-5 w-14 rounded-t-full border border-black/50 bg-gradient-to-b from-[#6c7276] to-[#3a3e41]", busy && "shadow-[0_10px_30px_6px_rgb(var(--gold)/.55)]")} />
            <span className={cx("h-1.5 w-10 rounded-b-full", busy ? "bg-[#ffb070]" : "bg-[#ff9a50]/60")} />
          </div>
        ))}
      </div>
      <div className="relative">
        {player}
        <AnimatePresence>
          {revealing && (
            <motion.div
              key="stamp"
              className="pointer-events-none absolute inset-0 z-20 grid place-items-center"
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 1, 1, 0] }}
              transition={{ duration: 2.2, times: [0, 0.1, 0.75, 1] }}
            >
              <motion.span
                initial={{ scale: 3, rotate: -24 }}
                animate={{ scale: 1, rotate: -12 }}
                transition={{ type: "spring", stiffness: 500, damping: 18 }}
                className="rounded-md border-[5px] border-ember bg-paper/90 px-5 py-2 font-display text-[40px] uppercase text-ember shadow-xl"
              >
                Order up!
              </motion.span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <div className="steel mx-[-10px] mt-3 h-3 rounded-sm border-t border-white/10 shadow-[0_6px_10px_rgb(0_0_0/.6)]" aria-hidden />
      {children}
    </div>
  );
}

function MarqueeFrame({ chasing, lit }: { chasing: boolean; lit: boolean }) {
  const n = 9;
  const reduce = useReducedMotion();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!chasing || reduce) return;
    const t = setInterval(() => setTick((x) => x + 1), 140);
    return () => clearInterval(t);
  }, [chasing, reduce]);
  const on = (i: number) => (chasing ? (i + tick) % 3 === 0 : true);
  const row = (offset: number, cls: string, vertical = false) => (
    <div className={cx("absolute flex justify-between", vertical ? "flex-col" : "", cls)} aria-hidden>
      {Array.from({ length: n }).map((_, i) => (
        <span key={i} className={cx("bulb", !on(i + offset) && "off", lit && !chasing && "animate-flicker")} style={{ width: 8, height: 8, animationDelay: `${(i % 5) * 0.4}s` }} />
      ))}
    </div>
  );
  return (
    <>
      {row(0, "inset-x-7 top-1.5")}
      {row(1, "inset-x-7 bottom-1.5")}
      {row(2, "inset-y-8 left-1.5", true)}
      {row(0, "inset-y-8 right-1.5", true)}
    </>
  );
}

function ReelSpinner() {
  return (
    <svg viewBox="0 0 48 48" className="h-14 w-14 animate-spin text-gold [animation-duration:2.4s] motion-reduce:animate-none" aria-hidden>
      <circle cx="24" cy="24" r="21" fill="none" stroke="currentColor" strokeWidth="2.5" />
      {[0, 72, 144, 216, 288].map((a) => (
        <circle key={a} cx={24 + 11 * Math.cos((a * Math.PI) / 180)} cy={24 + 11 * Math.sin((a * Math.PI) / 180)} r="4.5" fill="currentColor" />
      ))}
      <circle cx="24" cy="24" r="2.5" fill="currentColor" />
    </svg>
  );
}

function Steam() {
  return (
    <div className="flex h-14 items-end gap-2" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <span key={i} className="block h-10 w-3 animate-steam rounded-full bg-white/60 blur-[3px]" style={{ animationDelay: `${i * 0.45}s` }} />
      ))}
    </div>
  );
}
