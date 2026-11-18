"use client";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import useSWR from "swr";
import { api, fetcher, getOwnerToken, onOwnerTokenChange, ApiError } from "@/lib/api";
import type { Health, Job, Restaurant, Usage } from "@/lib/types";

export function useOwnerToken() {
  return useSyncExternalStore(onOwnerTokenChange, getOwnerToken, () => null);
}

/** Health also tells us whether the current viewer is the owner or a demo viewer. */
export function useHealth() {
  const token = useOwnerToken();
  return useSWR<Health, ApiError>(["/health", token], () => fetcher<Health>("/health"), {
    revalidateOnFocus: false,
  });
}

export function useIsOwner() {
  const { data } = useHealth();
  return data?.actor === "owner";
}

export function useRestaurant() {
  return useSWR<Restaurant, ApiError>("/restaurants/me", fetcher);
}

export function useUsage() {
  const token = useOwnerToken();
  return useSWR<Usage, ApiError>(["/usage", token], () => fetcher<Usage>("/usage"), { refreshInterval: 30000 });
}

const TERMINAL = new Set(["done", "failed", "needs_dish"]);

/** Polls /jobs/{id} every 1.5s until done | failed | needs_dish. */
export function useJob(id: number | null) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [tick, setTick] = useState(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (id == null) {
      setJob(null);
      setError(null);
      return;
    }
    let alive = true;
    const ctrl = new AbortController();
    let failures = 0;
    const poll = async () => {
      try {
        const j = await api<Job>(`/jobs/${id}`, { signal: ctrl.signal });
        if (!alive) return;
        failures = 0;
        setJob(j);
        setError(null);
        if (!TERMINAL.has(j.status)) timer.current = setTimeout(poll, 1500);
      } catch (e) {
        if (!alive || (e as Error).name === "AbortError") return;
        const err = e as ApiError;
        failures += 1;
        if (err.status === 404 || failures >= 5) {
          setError(err);
          return;
        }
        timer.current = setTimeout(poll, 1500 * failures);
      }
    };
    poll();
    return () => {
      alive = false;
      ctrl.abort();
      if (timer.current) clearTimeout(timer.current);
    };
  }, [id, tick]);

  return { job, error, isPolling: !!job && !TERMINAL.has(job.status), refresh: () => setTick((t) => t + 1) };
}
