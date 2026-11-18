"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { cx, elapsed, FALLBACK_LABEL } from "@/lib/format";
import type { Job, MenuItem, Script, Stage } from "@/lib/types";
import { Badge, Button, ErrorCallout, inputCls, Modal, Spinner } from "@/components/ui";

const STAGE_LABEL: Record<string, { title: string; sub: string }> = {
  analyze: { title: "Analyze", sub: "Reads the photo, matches your menu" },
  script: { title: "Script", sub: "Hook, captions, voiceover from your menu" },
  visuals: { title: "Visuals", sub: "AI motion or Ken Burns" },
  voice: { title: "Voice", sub: "Neural voiceover" },
  assemble: { title: "Assemble", sub: "Captions, music, end card" },
};

// ---------------------------------------------------------------- StageStepper
export function StageStepper({ job }: { job: Job | null }) {
  const [now, setNow] = useState(Date.now());
  const running = job && ["queued", "running"].includes(job.status);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [running]);
  const stages: Stage[] =
    job?.stages ?? (["analyze", "script", "visuals", "voice", "assemble"] as const).map((n) => ({ name: n, status: "pending", started_at: null, ended_at: null, note: null }));
  const total = job ? elapsed(job.created_at, job.finished_at, now) : null;
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">Progress</span>
        {total != null && <span className="font-mono text-xs text-muted">{total.toFixed(1)}s</span>}
      </div>
      <ol className="space-y-1" aria-live="polite">
        {stages.map((st) => {
          const t = elapsed(st.started_at, st.ended_at, now);
          const waiting = job?.status === "needs_dish" && st.name === "analyze";
          return (
            <li key={st.name} className={cx("flex items-start gap-3 rounded-xl px-3 py-2.5 transition", st.status === "running" && "bg-gold/10")}>
              <StageIcon status={waiting ? "waiting" : st.status} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className={cx("font-display text-lg uppercase tracking-wide", st.status === "pending" ? "text-muted" : "text-cream")}>
                    {STAGE_LABEL[st.name].title}
                  </span>
                  {t != null && st.status !== "pending" && <span className="font-mono text-xs text-muted">{t.toFixed(1)}s</span>}
                </div>
                <div className="text-xs text-muted">{st.note || STAGE_LABEL[st.name].sub}</div>
                {st.name === "visuals" && job?.fallback_reason && st.status === "done" && (
                  <Badge tone="info" className="mt-1.5">
                    Free mode · {FALLBACK_LABEL[job.fallback_reason] ?? "Veo unavailable"}
                  </Badge>
                )}
                {st.name === "visuals" && job?.veo_used && st.status === "done" && (
                  <Badge tone="gold" className="mt-1.5">
                    Veo AI motion
                  </Badge>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StageIcon({ status }: { status: string }) {
  if (status === "done")
    return (
      <span className="mt-0.5 grid h-6 w-6 shrink-0 animate-pop place-items-center rounded-full bg-ok text-bg">
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="3" aria-label="done">
          <path d="M5 12l5 5L20 7" />
        </svg>
      </span>
    );
  if (status === "failed")
    return <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-bad text-xs font-bold text-bg" aria-label="failed">✕</span>;
  if (status === "running") return <Spinner className="mt-0.5 h-6 w-6 shrink-0 text-gold" />;
  if (status === "waiting")
    return <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full border-2 border-gold text-xs font-bold text-gold" aria-label="waiting">?</span>;
  if (status === "skipped") return <span className="mt-0.5 h-6 w-6 shrink-0 rounded-full border-2 border-dashed border-line" aria-label="skipped" />;
  return <span className="mt-0.5 h-6 w-6 shrink-0 rounded-full border-2 border-line" aria-label="pending" />;
}

// ---------------------------------------------------------------- ScriptPanel
export function ScriptPanel({ script, loading }: { script: Script | null; loading: boolean }) {
  if (!script) {
    return (
      <div>
        <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Script</div>
        {loading ? (
          <div className="space-y-2" aria-hidden>
            {[80, 95, 70, 88].map((w, i) => (
              <div key={i} className="h-4 animate-pulse rounded bg-panel2" style={{ width: `${w}%` }} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted">The hook, captions and voiceover appear here as soon as they&apos;re written. Every fact comes from your menu.</p>
        )}
      </div>
    );
  }
  return (
    <div className="animate-fadeup">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted">Script</span>
        <Badge tone={script.source === "template" ? "info" : "ok"}>
          {script.source === "template" ? "Template · from menu" : script.source === "edited" ? "Edited · grounding checked" : "Grounded in your menu"}
        </Badge>
      </div>
      <div className="font-display text-2xl uppercase leading-tight text-gold">{script.hook}</div>
      <ol className="mt-3 space-y-2">
        {script.beats.map((b, i) => (
          <li key={i} className="animate-fadeup rounded-xl border border-line bg-bg/40 px-3 py-2" style={{ animationDelay: `${i * 90}ms` }}>
            <div className="whitespace-pre-line text-sm font-semibold text-cream">{b.caption}</div>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[11px] text-muted">{b.seconds.toFixed(1)}s</span>
              {(b.facts ?? []).map((f) => (
                <span key={f} className="rounded-full bg-ok/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ok">
                  from menu: {f}
                </span>
              ))}
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-4">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Voiceover</div>
        <p className="mt-1 text-sm leading-relaxed text-cream/90">{script.voiceover}</p>
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted hover:text-cream">YouTube title, description &amp; hashtags</summary>
        <div className="mt-2 space-y-1 text-cream/90">
          <div className="font-semibold">{script.title}</div>
          <div className="text-muted">{script.description}</div>
          <div className="text-gold">{script.hashtags.join(" ")}</div>
        </div>
      </details>
    </div>
  );
}

// ---------------------------------------------------------------- PhonePlayer
export function PhonePlayer({
  src,
  poster,
  placeholder,
  playing,
  overlay,
}: {
  src?: string | null;
  poster?: string | null;
  placeholder?: string | null;
  playing?: boolean;
  overlay?: React.ReactNode;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
    setMuted(true);
  }, [src]);
  return (
    <div className={cx("relative mx-auto aspect-[9/16] w-full max-w-[300px] overflow-hidden rounded-[32px] border-[6px] border-[#0a110d] bg-black transition-shadow duration-700", src && playing !== false && "shadow-glow")}>
      <div className="absolute left-1/2 top-2 z-20 h-1.5 w-16 -translate-x-1/2 rounded-full bg-[#0a110d]" />
      {src && !failed ? (
        <>
          <video
            ref={ref}
            key={src}
            src={src}
            poster={poster ?? undefined}
            className="h-full w-full object-cover"
            playsInline
            autoPlay
            muted={muted}
            loop
            preload="metadata"
            onError={() => setFailed(true)}
            onClick={() => {
              const v = ref.current;
              if (!v) return;
              if (muted) {
                setMuted(false);
                v.muted = false;
                v.play().catch(() => {});
              } else if (v.paused) v.play().catch(() => {});
              else v.pause();
            }}
          />
          {muted && (
            <button
              onClick={() => {
                setMuted(false);
                if (ref.current) {
                  ref.current.muted = false;
                  ref.current.play().catch(() => {});
                }
              }}
              className="absolute bottom-4 left-1/2 z-10 -translate-x-1/2 animate-fadeup rounded-full bg-black/70 px-4 py-2 text-xs font-semibold text-cream backdrop-blur"
            >
              🔊 Tap to unmute
            </button>
          )}
        </>
      ) : (
        <div className="relative h-full w-full">
          {placeholder ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={placeholder} alt="" className="h-full w-full object-cover opacity-60" />
          ) : (
            <div className="grain h-full w-full bg-panel" />
          )}
          {failed && <div className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-cream">Couldn&apos;t load the video. Use Download instead.</div>}
        </div>
      )}
      {overlay && <div className="absolute inset-0 z-10">{overlay}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- MenuPicker
export function MenuPicker({ menu, value, onChange, compact }: { menu: MenuItem[]; value: number | null; onChange: (m: MenuItem) => void; compact?: boolean }) {
  const [q, setQ] = useState("");
  const list = useMemo(() => {
    const n = q.trim().toLowerCase();
    return n ? menu.filter((m) => m.name.toLowerCase().includes(n) || (m.category ?? "").toLowerCase().includes(n)) : menu;
  }, [menu, q]);
  return (
    <div>
      <input className={inputCls} placeholder="Search your menu…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search menu" />
      <ul className={cx("mt-2 space-y-1 overflow-y-auto pr-1", compact ? "max-h-56" : "max-h-72")}>
        {list.map((m) => (
          <li key={m.id}>
            <button
              type="button"
              onClick={() => onChange(m)}
              className={cx(
                "flex w-full items-center gap-3 rounded-xl border px-2 py-2 text-left transition",
                value === m.id ? "border-gold bg-gold/10" : "border-transparent hover:bg-panel2",
              )}
            >
              {m.photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={m.photo_url} alt="" loading="lazy" className="h-10 w-10 shrink-0 rounded-lg object-cover" />
              ) : (
                <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-bg text-[10px] text-muted">no photo</div>
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-cream">{m.name}</div>
                <div className="truncate text-xs text-muted">{m.category}</div>
              </div>
              <span className="font-mono text-xs text-muted">{m.price ?? "—"}</span>
            </button>
          </li>
        ))}
        {list.length === 0 && <li className="px-2 py-4 text-sm text-muted">No dishes match “{q}”.</li>}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- DishPickerModal
export function DishPickerModal({ job, menu, onResolved }: { job: Job; menu: MenuItem[]; onResolved: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [browse, setBrowse] = useState(false);
  const a = job.analyze;
  const notFood = a?.reason === "not_food";
  const confirm = async (menuItemId: number | null, key: string) => {
    setBusy(key);
    setError(null);
    try {
      await api(`/jobs/${job.id}/confirm-dish`, { json: { menu_item_id: menuItemId, continue_anyway: true } });
      onResolved();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(null);
    }
  };
  return (
    <Modal open title={notFood ? "Is this a dish?" : "Which dish is this?"} onClose={() => {}}>
      {notFood ? (
        <p className="mb-4 text-sm text-cream/90">This doesn&apos;t look like a dish photo. Try another photo, or pick the dish and continue anyway.</p>
      ) : a?.reason === "analyze_failed" ? (
        <p className="mb-4 text-sm text-cream/90">We couldn&apos;t read the photo automatically. Pick the dish so the captions use the right name and price.</p>
      ) : (
        <p className="mb-4 text-sm text-cream/90">
          We&apos;re not sure{a?.dish_guess ? <> (it looks like <b>{a.dish_guess}</b>)</> : null}. Pick the dish so the captions use the right name and price.
        </p>
      )}
      {!browse && (
        <div className="space-y-2">
          {(a?.candidates ?? []).map((m) => (
            <button
              key={m.id}
              onClick={() => confirm(m.id, String(m.id))}
              disabled={!!busy}
              className="flex w-full items-center gap-3 rounded-xl border border-line px-3 py-2.5 text-left transition hover:border-gold disabled:opacity-50"
            >
              {m.photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={m.photo_url} alt="" className="h-11 w-11 rounded-lg object-cover" />
              ) : (
                <div className="h-11 w-11 rounded-lg bg-bg" />
              )}
              <span className="flex-1 text-sm font-semibold text-cream">{m.name}</span>
              <span className="font-mono text-xs text-muted">{m.price ?? ""}</span>
              {busy === String(m.id) && <Spinner className="h-4 w-4 text-gold" />}
            </button>
          ))}
          <button onClick={() => setBrowse(true)} className="w-full rounded-xl px-3 py-2 text-left text-sm text-gold hover:bg-panel2">
            Search the full menu →
          </button>
        </div>
      )}
      {browse && <MenuPicker menu={menu} value={null} onChange={(m) => confirm(m.id, String(m.id))} compact />}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4">
        <Button variant="ghost" onClick={() => confirm(null, "none")} loading={busy === "none"} disabled={!!busy && busy !== "none"}>
          Not on menu
        </Button>
        <span className="text-xs text-muted">“Not on menu” skips the price and uses only what&apos;s visible.</span>
      </div>
      {error && (
        <div className="mt-3">
          <ErrorCallout error={error} />
        </div>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------- PhotoDrop
export function PhotoDrop({ onFile, busy, preview, label = "Add a dish photo" }: { onFile: (f: File) => void; busy?: boolean; preview?: string | null; label?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={cx("flex items-center gap-4 rounded-xl border-2 border-dashed p-3 transition", drag ? "border-gold bg-gold/5" : "border-line")}
    >
      {preview ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={preview} alt="Selected dish" className="h-20 w-20 shrink-0 rounded-lg object-cover" />
      ) : (
        <div className="grid h-20 w-20 shrink-0 place-items-center rounded-lg bg-bg text-2xl">📷</div>
      )}
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-cream">{preview ? "Photo ready" : label}</div>
        <div className="text-xs text-muted">JPG, PNG or WEBP, up to 10 MB</div>
        <Button variant="ghost" className="mt-2 min-h-[36px]" onClick={() => input.current?.click()} loading={busy}>
          {preview ? "Change photo" : "Choose photo"}
        </Button>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}

export function validatePhoto(f: File): string | null {
  if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) return "Use a JPG or PNG under 10 MB.";
  if (f.size > 10 * 1024 * 1024) return "Use a JPG or PNG under 10 MB.";
  return null;
}

// ---------------------------------------------------------------- EditCaptionsModal
export function EditCaptionsModal({ jobId, script, onClose, onStarted }: { jobId: number; script: Script; onClose: () => void; onStarted: (id: number) => void }) {
  const [beats, setBeats] = useState(script.beats.map((b) => b.caption.replace(/\n/g, " ")));
  const [hook, setHook] = useState(script.hook);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ job_id: number }>(`/jobs/${jobId}/edit`, { json: { hook, beats: beats.filter((b) => b.trim()).map((caption) => ({ caption })) } });
      onStarted(r.job_id);
      onClose();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open title="Edit captions" onClose={onClose}>
      <p className="mb-4 text-sm text-muted">Change any line and re-render. Edits go through the same menu check as the AI, so a wrong price or an invented claim is blocked.</p>
      <div className="space-y-3">
        <div>
          <label htmlFor="hook" className="mb-1 block text-xs font-semibold uppercase tracking-wider text-muted">Hook</label>
          <input id="hook" className={inputCls} value={hook} maxLength={60} onChange={(e) => setHook(e.target.value)} />
        </div>
        {beats.map((b, i) => (
          <div key={i}>
            <label htmlFor={`beat${i}`} className="mb-1 flex justify-between text-xs font-semibold uppercase tracking-wider text-muted">
              <span>Caption {i + 1}</span>
              <span className={cx("font-mono normal-case", b.length > 44 && "text-gold")}>{b.length}/44</span>
            </label>
            <input id={`beat${i}`} className={inputCls} value={b} maxLength={60} onChange={(e) => setBeats((xs) => xs.map((x, j) => (j === i ? e.target.value : x)))} />
          </div>
        ))}
      </div>
      {error && (
        <div className="mt-3">
          <ErrorCallout error={error} />
        </div>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={submit} loading={busy} disabled={!beats.some((b) => b.trim())}>
          Re-render
        </Button>
      </div>
    </Modal>
  );
}
