import { cx } from "@/lib/format";

/** A row of marquee bulbs that flicker out of phase. */
export function BulbRow({ n, className, offset }: { n: number; className?: string; offset?: boolean }) {
  return (
    <div className={cx("flex justify-between", className)} aria-hidden>
      {Array.from({ length: n }).map((_, i) => (
        <span key={i} className="bulb animate-flicker" style={{ animationDelay: `${((i + (offset ? 1 : 0)) % 4) * 0.37}s`, width: 6, height: 6 }} />
      ))}
    </div>
  );
}
