"use client";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { cx } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import { clap, primeAudio } from "@/lib/sfx";
import type { Job, Stage } from "@/lib/types";
import { Spinner } from "@/components/ui";
import { PhonePlayer } from "@/components/player";

export function GenerateButton({ onClick, disabled, loading }: { onClick: () => void; disabled?: boolean; loading?: boolean }) {
  const { t, sound } = useTheme();
  const reduce = useReducedMotion();
  const [snap, setSnap] = useState(false);
  const fire = () => {
    primeAudio();
    if (sound) clap();
    setSnap(true);
    setTimeout(() => setSnap(false), 700);
    onClick();
  };

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
            <span>Prod.<span className="hidden sm:inline"> What&apos;s Cooking?</span></span>
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

// ================================================================ Stage board

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
  const { t } = useTheme();
  const reduce = useReducedMotion();
  const done = job?.status === "done" && !!job.video;
  const [revealKey, setRevealKey] = useState<number | null>(null);
  const prev = useRef<string | undefined>(undefined);
  useEffect(() => {
    // play the reveal only when a job transitions to done while we watch
    if (job && prev.current && prev.current !== "done" && job.status === "done") {
      setRevealKey(job.id);
    }
    prev.current = job?.status;
  }, [job]);
  const revealing = revealKey === job?.id && !reduce;

  const player = (
    <PhonePlayer
      src={done ? job!.video!.url : null}
      poster={job?.video?.poster_url}
      placeholder={job?.photo_url ?? previewImg}
      overlay={
        busy ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 bg-black/45 p-6 text-center">
            <ReelSpinner />
            <div className="font-display text-3xl uppercase tracking-[.12em] text-cream">{t.studio.working}…</div>
            <div className="font-mono text-[11px] text-cream/75">{job?.stages.find((s) => s.status === "running")?.note || ""}</div>
          </div>
        ) : !job && !previewImg ? (
          <div className="flex h-full items-center justify-center p-6 text-center font-mono text-xs uppercase tracking-widest text-muted">{t.studio.placeholder}</div>
        ) : null
      }
    />
  );

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
