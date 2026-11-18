"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { InsightsResponse } from "@/lib/types";
import { Spinner } from "@/components/ui";

// "/" → /insights when there are insight cards, otherwise /studio.
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    let done = false;
    const t = setTimeout(() => !done && router.replace("/studio"), 6000);
    api<InsightsResponse>("/insights")
      .then((r) => router.replace(r.cards.length ? "/insights" : "/studio"))
      .catch(() => router.replace("/studio"))
      .finally(() => {
        done = true;
        clearTimeout(t);
      });
    return () => clearTimeout(t);
  }, [router]);
  return (
    <main className="grid min-h-screen place-items-center">
      <div className="flex flex-col items-center gap-4 text-muted">
        <span className="font-display text-4xl uppercase tracking-wide text-cream">
          What&apos;s <span className="text-gold">Cooking?</span>
        </span>
        <Spinner className="h-5 w-5 text-gold" />
      </div>
    </main>
  );
}
