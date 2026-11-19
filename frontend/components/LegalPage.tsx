import Link from "next/link";
import type { ReactNode } from "react";

/** Shared layout for the privacy policy and terms pages. */
export function LegalPage({ title, updated, children }: { title: string; updated: string; children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-2xl px-5 pb-20 pt-10">
      <Link href="/" className="font-display text-2xl uppercase tracking-[.05em] text-cream">
        What&apos;s <span className="text-gold">Cooking?</span>
      </Link>
      <h1 className="mt-8 font-display text-5xl uppercase leading-none tracking-[.03em] text-cream">{title}</h1>
      <p className="mt-2 font-mono text-xs uppercase tracking-widest text-muted">Last updated {updated}</p>
      <div className="mt-8 space-y-5 text-[15px] leading-relaxed text-cream/90 [&_a]:text-gold [&_a]:underline [&_h2]:mt-8 [&_h2]:font-display [&_h2]:text-2xl [&_h2]:uppercase [&_h2]:tracking-[.03em] [&_h2]:text-cream [&_li]:ml-5 [&_li]:list-disc">
        {children}
      </div>
    </main>
  );
}
