"use client";
import { motion } from "framer-motion";
import { cx, money } from "@/lib/format";
import { useTheme } from "@/lib/theme";
import type { Usage } from "@/lib/types";

export function BudgetSummary({ u }: { u: Usage; restaurant?: string }) {
  const { t } = useTheme();
  const clipPct = u.today.limit > 0 ? Math.min(100, (u.today.clips / u.today.limit) * 100) : 100;
  const spendPct = u.month.cap_cents > 0 ? Math.min(100, (u.month.est_cents / u.month.cap_cents) * 100) : 100;
  const perClip = u.cost_per_sec_cents * 8;

  return (
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { k: "Shoot days · Veo takes today", v: `${u.today.clips}`, of: `/ ${u.today.limit}`, pct: clipPct, over: u.today.clips >= u.today.limit },
          { k: "Spent this month", v: money(u.month.est_cents), of: `of ${money(u.month.cap_cents)}`, pct: spendPct, over: u.month.est_cents >= u.month.cap_cents },
        ].map((s) => (
          <div key={s.k} className="relative overflow-hidden rounded-[10px] border border-gold/25 bg-black/50 p-4">
            <div className="font-mono text-[10.5px] uppercase tracking-[.22em] text-muted">{s.k}</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className={cx("font-display text-[56px] leading-none", s.over ? "text-bad" : "text-gold [text-shadow:0_0_20px_rgb(var(--gold)/.45)]")}>{s.v}</span>
              <span className="font-mono text-sm text-muted">{s.of}</span>
            </div>
            {/* film-strip meter */}
            <div className="mt-3 flex gap-[3px]" role="meter" aria-label={s.k} aria-valuenow={Math.round(s.pct)} aria-valuemin={0} aria-valuemax={100}>
              {Array.from({ length: 20 }).map((_, i) => (
                <motion.span
                  key={i}
                  initial={{ opacity: 0.15 }}
                  animate={{ opacity: i < Math.round(s.pct / 5) ? 1 : 0.15 }}
                  transition={{ delay: i * 0.03 }}
                  className={cx("h-4 flex-1 rounded-[2px]", s.over ? "bg-bad" : "bg-gold")}
                />
              ))}
            </div>
          </div>
        ))}
        <div className="font-mono text-xs text-muted sm:col-span-2">
          {t.settings.perVideo(money(perClip))} with Veo ({money(u.cost_per_sec_cents)}/sec × 8s) · {t.settings.freeMode.toLowerCase()} films cost $0.00
        </div>
      </div>
    );
}
