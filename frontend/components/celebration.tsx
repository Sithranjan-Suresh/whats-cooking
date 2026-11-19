"use client";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useTheme } from "@/lib/theme";

export function Celebration({ show, onDone }: { show: boolean; onDone: () => void }) {
  const { t } = useTheme();
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
        </motion.div>
      )}
    </AnimatePresence>
  );
}
