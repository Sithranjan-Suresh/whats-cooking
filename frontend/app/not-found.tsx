import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center">
      <p className="font-mono text-xs uppercase tracking-[.3em] text-gold">Scene missing</p>
      <h1 className="mt-3 font-display text-[64px] uppercase leading-none tracking-[.04em] text-cream">404</h1>
      <p className="mt-3 text-sm text-muted">This page isn&apos;t in the script.</p>
      <Link href="/" className="mt-8 inline-flex min-h-[48px] items-center rounded-xl bg-gold px-6 text-sm font-semibold text-ongold hover:bg-gold2">
        Back to the studio
      </Link>
    </main>
  );
}
