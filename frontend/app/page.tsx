"use client";
// One page, one flow: 1) logo → 2) pick the dish (sales CSV or a dish photo) → 3) Action! → Post to YouTube.
// Below it: every video you've made, and which ones are on YouTube.
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { motion } from "framer-motion";
import { api, fetcher, setYtBlob, ApiError } from "@/lib/api";
import { cx, timeAgo } from "@/lib/format";
import type { InsightCard, InsightsResponse, MenuItem, Restaurant, SalesImportResult, Video } from "@/lib/types";
import { useHealth, useJob, useRestaurant } from "@/hooks/data";
import { ThemeProvider, useTheme } from "@/lib/theme";
import { Button, ErrorCallout, Field, inputCls, Modal, Spinner, Toaster, useToast } from "@/components/ui";
import { PhotoDrop, validatePhoto } from "@/components/studio";
import { GenerateButton, PlayerStage } from "@/components/themed/studio";
import { Celebration } from "@/components/themed/library";
import { BulbRow } from "@/components/BulbRow";
import { fanfare } from "@/lib/sfx";

const LAST_JOB = "wc_last_job";

export default function Page() {
  return (
    <ThemeProvider>
      <Toaster>
        <div className="grain-layer" aria-hidden />
        <Suspense fallback={null}>
          <App />
        </Suspense>
      </Toaster>
    </ThemeProvider>
  );
}

function App() {
  const params = useSearchParams();
  const toast = useToast();
  const restaurant = useRestaurant();
  const health = useHealth();
  const [jobId, setJobId] = useState<number | null>(null);
  const { job, error: jobError, refresh } = useJob(jobId);
  const busy = !!job && ["queued", "running"].includes(job.status);

  useEffect(() => {
    try {
      const last = window.localStorage.getItem(LAST_JOB);
      if (last) setJobId(Number(last));
    } catch {
      /* ignore */
    }
    const hash = window.location.hash;
    if (hash.startsWith("#yt=")) {
      setYtBlob(decodeURIComponent(hash.slice(4)));
      restaurant.mutate();
    }
    const yt = params.get("youtube");
    if (yt === "connected") toast("YouTube connected. Hit Post to YouTube.", "ok");
    if (yt === "error") toast(`YouTube connection failed (${params.get("reason") ?? "unknown"})`, "bad");
    if (yt || hash) window.history.replaceState(null, "", "/");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const track = (id: number) => {
    setJobId(id);
    try {
      window.localStorage.setItem(LAST_JOB, String(id));
    } catch {
      /* ignore */
    }
  };

  const loading = !restaurant.data && !restaurant.error;
  return (
    <main className="mx-auto w-full max-w-6xl px-4 pb-20 pt-6 sm:px-6 sm:pt-10">
      <Header />
      {restaurant.error && (
        <div className="mt-6">
          <ErrorCallout
            error={restaurant.error.status === 0 ? "The video server is waking up (free hosting sleeps when idle). Give it about a minute, then retry." : restaurant.error}
            onRetry={() => restaurant.mutate()}
          />
        </div>
      )}
      {loading && (
        <div className="mt-16 flex flex-col items-center gap-3 text-muted">
          <Spinner className="h-7 w-7 text-gold" />
          <span className="font-mono text-xs uppercase tracking-widest">Warming up the studio…</span>
        </div>
      )}
      {restaurant.data && (
        <>
          <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
            <div className="min-w-0 space-y-6">
              <StepLogo r={restaurant.data} onChange={() => restaurant.mutate()} />
              <StepDish onStarted={track} busy={busy} />
            </div>
            <div className={cx("lg:sticky lg:top-8 lg:order-none lg:self-start", jobId ? "order-first" : "order-last")}>
              <ResultPanel jobId={jobId} job={job} jobError={jobError} refresh={refresh} busy={busy} r={restaurant.data} ytConfigured={!!(restaurant.data.youtube_configured ?? health.data?.youtube_configured)} />
            </div>
          </div>
          <History r={restaurant.data} ytConfigured={!!(restaurant.data.youtube_configured ?? health.data?.youtube_configured)} />
        </>
      )}
    </main>
  );
}

function Header() {
  return (
    <header className="text-center">
      <div className="relative mx-auto inline-block rounded-2xl bg-black/60 px-8 pb-4 pt-5 ring-1 ring-gold/30">
        <BulbRow className="absolute inset-x-4 top-1.5" n={13} />
        <h1 className="font-display text-[44px] uppercase leading-none tracking-[.04em] text-cream sm:text-[64px]">
          What&apos;s <span className="animate-flicker text-gold [text-shadow:0_0_22px_rgb(var(--gold)/.55)]">Cooking?</span>
        </h1>
        <p className="mt-2 font-mono text-[11px] uppercase tracking-[.25em] text-muted">Your dish · an 8-second Short · straight to YouTube</p>
      </div>
    </header>
  );
}

function StepCard({ n, title, done, children }: { n: number; title: string; done?: boolean; children: React.ReactNode }) {
  return (
    <section className="card rounded-xl border p-5 sm:p-6">
      <div className="mb-4 flex items-center gap-3">
        <span className={cx("grid h-9 w-9 shrink-0 place-items-center rounded-full font-display text-xl", done ? "bg-gold text-ongold" : "border border-gold/50 text-gold")}>
          {done ? "✓" : n}
        </span>
        <h2 className="font-display text-[28px] uppercase leading-none tracking-[.04em] text-cream">{title}</h2>
      </div>
      {children}
    </section>
  );
}

// ---------------------------------------------------------------- 1. logo

function StepLogo({ r, onChange }: { r: Restaurant; onChange: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(r.name);
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  useEffect(() => setName(r.name), [r.name]);

  const saveName = async () => {
    const n = name.trim();
    if (!n || n === r.name) return;
    try {
      await api<Restaurant>("/restaurants/me", { method: "PATCH", json: { name: n } });
      onChange();
    } catch (e) {
      toast((e as Error).message, "bad");
    }
  };
  const upload = async (f: File) => {
    if (!["image/png", "image/jpeg", "image/webp"].includes(f.type) || f.size > 10 * 1024 * 1024) {
      toast("Use a PNG or JPG under 10 MB", "bad");
      return;
    }
    setBusy(true);
    const fd = new FormData();
    fd.append("file", f);
    fd.append("kind", "logo");
    try {
      const a = await api<{ asset_id: number }>("/uploads", { form: fd });
      await api<Restaurant>("/restaurants/me", { method: "PATCH", json: { logo_asset_id: a.asset_id } });
      onChange();
      toast("Logo saved. It closes every video.", "ok");
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setBusy(false);
    }
  };

  return (
    <StepCard n={1} title="Your logo" done={!!r.logo_url}>
      <div className="flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={() => file.current?.click()}
          aria-label="Upload your logo"
          className="group relative grid h-20 w-20 shrink-0 place-items-center overflow-hidden rounded-full bg-[#f6efe4] ring-2 ring-gold/60 transition hover:ring-gold"
        >
          {r.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={r.logo_url} alt="Your logo" className="h-full w-full object-contain p-2" />
          ) : (
            <span className="font-display text-3xl text-[#1a0d0b]">+</span>
          )}
          {busy && (
            <span className="absolute inset-0 grid place-items-center bg-black/60">
              <Spinner className="h-5 w-5 text-gold" />
            </span>
          )}
        </button>
        <input
          ref={file}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload(f);
            e.target.value = "";
          }}
        />
        <div className="min-w-[200px] flex-1">
          <Field label="Restaurant name" htmlFor="rname">
            <input id="rname" className={inputCls} value={name} maxLength={60} onChange={(e) => setName(e.target.value)} onBlur={saveName} onKeyDown={(e) => e.key === "Enter" && (e.currentTarget as HTMLInputElement).blur()} />
          </Field>
          <Button variant="ghost" className="mt-3 min-h-[38px]" onClick={() => file.current?.click()} loading={busy}>
            {r.logo_url ? "Change logo" : "Upload logo"}
          </Button>
        </div>
      </div>
    </StepCard>
  );
}

// ---------------------------------------------------------------- 2. pick the dish

function StepDish({ onStarted, busy }: { onStarted: (id: number) => void; busy: boolean }) {
  const [source, setSource] = useState<"csv" | "photo">("photo");
  const [error, setError] = useState<ApiError | null>(null);
  const [creating, setCreating] = useState(false);
  // photo path
  const [photo, setPhoto] = useState<{ id: number; url: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [photoErr, setPhotoErr] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [desc, setDesc] = useState("");
  // csv path
  const [picks, setPicks] = useState<InsightCard[] | null>(null);
  const [chosen, setChosen] = useState<InsightCard | null>(null);
  const [imported, setImported] = useState<SalesImportResult | null>(null);

  const uploadPhoto = async (f: File): Promise<{ id: number; url: string } | null> => {
    const err = validatePhoto(f);
    if (err) {
      setPhotoErr(err);
      return null;
    }
    setPhotoErr(null);
    setUploading(true);
    const form = new FormData();
    form.append("file", f);
    form.append("kind", "photo");
    try {
      const r = await api<{ asset_id: number; url: string }>("/uploads", { form });
      const p = { id: r.asset_id, url: r.url };
      setPhoto(p);
      return p;
    } catch (e) {
      setPhotoErr((e as Error).message);
      return null;
    } finally {
      setUploading(false);
    }
  };

  const start = async (veo = true) => {
    setCreating(true);
    setError(null);
    try {
      let menuItemId: number;
      if (source === "photo") {
        const d = await api<MenuItem>("/dishes", { json: { name: name.trim(), price: price.trim() || null, description: desc.trim() || null, photo_asset_id: photo!.id } });
        menuItemId = d.id;
      } else {
        menuItemId = chosen!.menu_item.id;
        if (photo) await api(`/menu/${menuItemId}/photo`, { json: { asset_id: photo.id } });
      }
      const r = await api<{ job_id: number }>("/jobs", { json: { mode: "menu", menu_item_id: menuItemId, length_s: 8, style: "bold", veo } });
      onStarted(r.job_id);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setCreating(false);
    }
  };

  const csvReady = !!chosen && (!!chosen.menu_item.photo_url || !!photo);
  const photoReady = !!photo && name.trim().length > 0;
  const ready = source === "photo" ? photoReady : csvReady;
  const capHit = error?.code === "budget_cap_reached";

  return (
    <StepCard n={2} title="Pick the dish">
      <div role="tablist" className="mb-5 grid grid-cols-2 gap-1 rounded-xl bg-bg p-1">
        {(
          [
            ["photo", "📷 Upload a dish photo"],
            ["csv", "📈 Upload sales CSV"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            role="tab"
            aria-selected={source === k}
            onClick={() => {
              setSource(k);
              setPhoto(null);
              setError(null);
            }}
            className={cx("min-h-[46px] rounded-lg text-sm font-semibold transition", source === k ? "bg-panel2 text-gold shadow" : "text-muted hover:text-cream")}
          >
            {label}
          </button>
        ))}
      </div>

      {source === "photo" ? (
        <div className="space-y-4">
          <PhotoDrop onFile={uploadPhoto} busy={uploading} preview={photo?.url} />
          {photoErr && <p className="text-sm text-bad">{photoErr}</p>}
          <div className="grid gap-3 sm:grid-cols-[1fr_120px]">
            <Field label="Dish name" htmlFor="dname">
              <input id="dname" className={inputCls} value={name} maxLength={80} placeholder="e.g. Masala Dosa" onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Price" htmlFor="dprice">
              <input id="dprice" inputMode="decimal" className={inputCls} value={price} maxLength={10} placeholder="11.50" onChange={(e) => setPrice(e.target.value)} />
            </Field>
          </div>
          <Field label="What's in it (optional)" htmlFor="ddesc" hint="The narrator only says what you type, so nothing gets made up.">
            <input id="ddesc" className={inputCls} value={desc} maxLength={240} placeholder="Crispy rice crepe with spiced potato" onChange={(e) => setDesc(e.target.value)} />
          </Field>
        </div>
      ) : (
        <CsvPicker
          picks={picks}
          chosen={chosen}
          imported={imported}
          onImported={(r, cards) => {
            setImported(r);
            setPicks(cards);
            setChosen(cards[0] ?? null);
            setPhoto(null);
          }}
          onChoose={(c) => {
            setChosen(c);
            setPhoto(null);
          }}
          photo={photo}
          uploading={uploading}
          photoErr={photoErr}
          onPhoto={uploadPhoto}
        />
      )}

      {error && (
        <div className="mt-4 space-y-2">
          <ErrorCallout error={error} title={capHit ? "$10 budget cap reached" : undefined} />
          {capHit && (
            <Button variant="ghost" onClick={() => start(false)} loading={creating}>
              Make it free instead (photo motion)
            </Button>
          )}
        </div>
      )}

      <GenerateButton onClick={() => start(true)} disabled={!ready || busy} loading={creating} />
      {!ready && (
        <p className="mt-2 text-center text-xs text-muted">
          {source === "photo"
            ? photo
              ? "Give the dish a name."
              : "Add a dish photo and its name."
            : !picks
              ? "Upload your sales CSV and we'll pick the dish."
              : "Add a photo of this dish."}
        </p>
      )}
    </StepCard>
  );
}

function CsvPicker({
  picks,
  chosen,
  imported,
  onImported,
  onChoose,
  photo,
  uploading,
  photoErr,
  onPhoto,
}: {
  picks: InsightCard[] | null;
  chosen: InsightCard | null;
  imported: SalesImportResult | null;
  onImported: (r: SalesImportResult, cards: InsightCard[]) => void;
  onChoose: (c: InsightCard) => void;
  photo: { id: number; url: string } | null;
  uploading: boolean;
  photoErr: string | null;
  onPhoto: (f: File) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const upload = async (f: File) => {
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", f);
    try {
      const r = await api<SalesImportResult>("/sales/import", { form });
      const ins = await api<InsightsResponse>("/insights");
      onImported(r, ins.cards);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  };
  const label = (c: InsightCard) =>
    c.angle === "rising" ? `up ${c.metric.wow_pct ?? 0}% this week` : c.angle === "top_seller" ? `your #1 seller (${c.metric.qty_7d ?? 0} this week)` : `under-ordered, worth a push`;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border-2 border-dashed border-line p-4">
        <div className="min-w-0 flex-1 text-sm">
          <div className="font-semibold text-cream">{imported ? `${imported.rows.toLocaleString()} sales rows read` : "Your item-sales export (CSV)"}</div>
          <div className="text-xs text-muted">From Toast, Square or Clover: date, item, quantity (revenue optional)</div>
        </div>
        <Button variant="ghost" onClick={() => input.current?.click()} loading={busy}>
          {imported ? "Upload another" : "Choose CSV"}
        </Button>
        <a href="/sample_sales.csv" download className="text-xs text-gold underline-offset-4 hover:underline">
          sample CSV
        </a>
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upload(f);
            e.target.value = "";
          }}
        />
      </div>
      {error && <ErrorCallout error={error} />}
      {picks && picks.length === 0 && <p className="text-sm text-muted">No dishes found in that file. Check it has date, item and quantity columns.</p>}
      {picks && picks.length > 0 && chosen && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
          <div className="font-mono text-[11px] uppercase tracking-[.25em] text-gold">★ Feature this dish</div>
          <div className="flex items-center gap-4 rounded-xl border border-gold/50 bg-gold/5 p-4">
            {chosen.menu_item.photo_url || photo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={photo?.url ?? chosen.menu_item.photo_url!} alt="" className="h-20 w-20 shrink-0 rounded-lg object-cover" />
            ) : (
              <div className="grid h-20 w-20 shrink-0 place-items-center rounded-lg bg-bg text-2xl">🍽️</div>
            )}
            <div className="min-w-0">
              <div className="font-display text-[30px] uppercase leading-none text-cream">{chosen.menu_item.name}</div>
              <div className="mt-1 text-sm text-gold">{label(chosen)}</div>
              <div className="mt-1 text-xs text-muted">{chosen.reason}</div>
            </div>
          </div>
          {picks.length > 1 && (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="self-center text-muted">Or:</span>
              {picks
                .filter((c) => c.id !== chosen.id)
                .map((c) => (
                  <button key={c.id} onClick={() => onChoose(c)} className="rounded-full border border-line px-3 py-1.5 text-cream hover:border-gold/60">
                    {c.menu_item.name} · {label(c)}
                  </button>
                ))}
            </div>
          )}
          {!chosen.menu_item.photo_url && (
            <div>
              <PhotoDrop onFile={onPhoto} busy={uploading} preview={photo?.url} label={`Add a photo of ${chosen.menu_item.name}`} />
              {photoErr && <p className="mt-2 text-sm text-bad">{photoErr}</p>}
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 3. the video + post

function ResultPanel({
  jobId,
  job,
  jobError,
  refresh,
  busy,
  r,
  ytConfigured,
}: {
  jobId: number | null;
  job: ReturnType<typeof useJob>["job"];
  jobError: ApiError | null;
  refresh: () => void;
  busy: boolean;
  r: Restaurant;
  ytConfigured: boolean;
}) {
  const videos = useSWR<Video[], ApiError>("/videos", fetcher);
  const video = job?.video ? videos.data?.find((v) => v.id === job.video!.id) : undefined;
  useEffect(() => {
    if (job?.status === "done") videos.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.status]);
  const running = job?.stages.find((s) => s.status === "running");
  const doneCount = job?.stages.filter((s) => s.status === "done").length ?? 0;

  return (
    <div>
      <PlayerStage job={job} previewImg={null} busy={busy} />
      {busy && (
        <div className="mx-auto mt-4 max-w-[320px]">
          <div className="h-1.5 overflow-hidden rounded-full bg-panel2">
            <motion.div className="h-full bg-gold" animate={{ width: `${Math.max(8, (doneCount / 5) * 100)}%` }} transition={{ duration: 0.6 }} />
          </div>
          <div className="mt-2 text-center font-mono text-xs text-muted">{running?.note || "Rolling…"} · about a minute</div>
        </div>
      )}
      {job?.status === "failed" && (
        <div className="mx-auto mt-4 max-w-[320px]">
          <ErrorCallout error={job.error || "That take failed."} />
        </div>
      )}
      {jobError && jobId && (
        <div className="mx-auto mt-4 max-w-[320px]">
          <ErrorCallout error="Lost track of that video. It may still appear below in Your videos." onRetry={refresh} />
        </div>
      )}
      {job?.status === "done" && job.video && (
        <div className="mx-auto mt-4 grid max-w-[320px] grid-cols-2 gap-2">
          <a
            href={job.video.url}
            download={`${(job.menu_item?.name ?? "short").replace(/\W+/g, "-").toLowerCase()}.mp4`}
            className="inline-flex min-h-[48px] items-center justify-center rounded-xl border border-line text-sm font-semibold text-cream hover:border-gold/60"
          >
            Download
          </a>
          {video && <PostButton v={video} r={r} ytConfigured={ytConfigured} onChanged={() => videos.mutate()} full />}
          {!ytConfigured && <p className="col-span-2 text-center text-[11px] text-muted">YouTube posting switches on once it&apos;s connected on the server. Download works now.</p>}
        </div>
      )}
    </div>
  );
}

function PostButton({ v, r, ytConfigured, onChanged, full }: { v: Video; r: Restaurant; ytConfigured: boolean; onChanged: () => void; full?: boolean }) {
  const [open, setOpen] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const toast = useToast();
  const cls = cx("inline-flex min-h-[48px] items-center justify-center rounded-xl px-4 text-sm font-semibold", full && "w-full");
  if (v.youtube_url)
    return (
      <a href={v.youtube_url} target="_blank" rel="noreferrer" className={cx(cls, "border border-ok/50 text-ok hover:bg-ok/10")}>
        On YouTube ↗
      </a>
    );
  if (v.publish_status === "publishing")
    return (
      <span className={cx(cls, "gap-2 bg-ember/80 text-cream")}>
        <Spinner className="h-4 w-4" /> Posting {v.publish_progress}%
      </span>
    );
  if (!r.youtube_connected) {
    return (
      <button
        disabled={!ytConfigured || connecting}
        title={ytConfigured ? undefined : "YouTube isn't set up on the server yet"}
        onClick={async () => {
          setConnecting(true);
          try {
            const { url } = await api<{ url: string }>("/youtube/auth/url");
            window.location.href = url;
          } catch (e) {
            toast((e as Error).message, "bad");
            setConnecting(false);
          }
        }}
        className={cx(cls, "bg-[#ff0033] text-white hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40")}
      >
        {connecting ? <Spinner className="h-4 w-4" /> : "Connect YouTube"}
      </button>
    );
  }
  return (
    <>
      <button onClick={() => setOpen(true)} className={cx(cls, "bg-[#ff0033] text-white hover:brightness-110")}>
        {v.publish_status === "failed" ? "Retry post" : "Post to YouTube"}
      </button>
      {open && <PostDialog v={v} onClose={() => setOpen(false)} onDone={onChanged} />}
    </>
  );
}

function PostDialog({ v, onClose, onDone }: { v: Video; onClose: () => void; onDone: () => void }) {
  const [title, setTitle] = useState(v.title ?? v.dish ?? "");
  const [privacy, setPrivacy] = useState<"public" | "unlisted" | "private">("public");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const toast = useToast();
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/videos/${v.id}/publish`, { json: { title, description: v.description ?? "", tags: v.hashtags, privacy } });
      toast("Posting to YouTube…", "info");
      onDone();
      onClose();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open title="Post to YouTube" onClose={onClose}>
      <div className="space-y-4">
        <Field label="Title" htmlFor="yt-title">
          <input id="yt-title" className={inputCls} value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <div className="grid grid-cols-3 gap-1 rounded-xl bg-bg p-1">
          {(["public", "unlisted", "private"] as const).map((p) => (
            <button key={p} onClick={() => setPrivacy(p)} aria-pressed={privacy === p} className={cx("min-h-[38px] rounded-lg text-sm font-semibold capitalize", privacy === p ? "bg-panel2 text-gold" : "text-muted")}>
              {p}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted">YouTube keeps uploads from apps it hasn&apos;t reviewed yet private, even if you pick Public. The real status shows below once it&apos;s posted.</p>
        {error && <ErrorCallout error={error} />}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!title.trim()}>
            Post
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------- history

function History({ r, ytConfigured }: { r: Restaurant; ytConfigured: boolean }) {
  const { sound } = useTheme();
  const videos = useSWR<Video[], ApiError>("/videos", fetcher, {
    refreshInterval: (d) => (d?.some((v) => v.publish_status === "publishing") ? 2000 : 15000),
  });
  const [celebrate, setCelebrate] = useState(false);
  const prev = useRef<Record<number, string>>({});
  useEffect(() => {
    if (!videos.data) return;
    let fire = false;
    for (const v of videos.data) {
      if (prev.current[v.id] === "publishing" && v.publish_status === "published") fire = true;
      prev.current[v.id] = v.publish_status;
    }
    if (fire) {
      setCelebrate(true);
      if (sound) fanfare();
    }
  }, [videos.data, sound]);
  const [filter, setFilter] = useState<"all" | "posted">("all");
  const list = videos.data ?? [];
  const uploads = useSWR<YtUploads, ApiError>(r.youtube_connected ? "/youtube/uploads" : null, fetcher, { refreshInterval: 60000 });
  useEffect(() => {
    if (celebrate) uploads.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [celebrate]);
  const postedCount = r.youtube_connected ? uploads.data?.videos.length ?? 0 : list.filter((v) => v.youtube_url).length;

  return (
    <section className="mt-14">
      <Celebration show={celebrate} onDone={() => setCelebrate(false)} />
      <YouTubeStatus r={r} ytConfigured={ytConfigured} />
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <h2 className="font-display text-[40px] uppercase leading-none tracking-[.03em] text-cream">Your videos</h2>
        <div className="flex rounded-full border border-line bg-black/40 p-0.5 text-xs font-semibold">
          {(
            [
              ["all", `All (${videos.data?.length ?? 0})`],
              ["posted", `On YouTube (${postedCount})`],
            ] as const
          ).map(([k, label]) => (
            <button key={k} onClick={() => setFilter(k)} className={cx("rounded-full px-3 py-1.5", filter === k ? "bg-gold text-ongold" : "text-muted hover:text-cream")}>
              {label}
            </button>
          ))}
        </div>
      </div>
      {filter === "posted" ? (
        <YouTubeList connected={r.youtube_connected} uploads={uploads.data} error={uploads.error} retry={() => uploads.mutate()} local={list.filter((v) => v.youtube_url)} />
      ) : (
        <>
      {videos.error && <ErrorCallout error={videos.error} onRetry={() => videos.mutate()} />}
      {videos.data && list.length === 0 && (
        <p className="rounded-xl border border-dashed border-line px-5 py-8 text-center text-sm text-muted">Your videos will show up here.</p>
      )}
      <ul className="grid gap-3 sm:grid-cols-2">
        {list.map((v) => (
          <li key={v.id} className="card flex gap-3 rounded-xl border p-3">
            <a href={v.url} target="_blank" rel="noreferrer" className="relative block aspect-[9/16] w-20 shrink-0 overflow-hidden rounded-md bg-black">
              {v.poster_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={v.poster_url} alt="" loading="lazy" className="h-full w-full object-cover" />
              )}
              <span className="absolute inset-0 grid place-items-center text-cream/90">▶</span>
            </a>
            <div className="flex min-w-0 flex-1 flex-col">
              <div className="truncate font-display text-xl uppercase tracking-[.03em] text-cream">{v.dish ?? "Video"}</div>
              <div className="text-xs text-muted">
                {timeAgo(v.created_at)} · {Math.round(v.duration_s)}s · {v.mode === "veo" ? "AI motion" : "photo motion"}
              </div>
              {v.youtube_url ? (
                <a href={v.youtube_url} target="_blank" rel="noreferrer" className="mt-1 truncate text-xs text-ok hover:underline">
                  ✓ Posted{v.youtube_privacy && v.youtube_privacy !== "public" ? ` (${v.youtube_privacy})` : ""} · {v.youtube_url.replace("https://", "")}
                </a>
              ) : v.publish_status === "failed" ? (
                <span className="mt-1 text-xs text-bad">Post failed: {v.publish_error}</span>
              ) : (
                <span className="mt-1 text-xs text-muted">Not posted yet</span>
              )}
              <div className="mt-auto flex gap-2 pt-2">
                <a href={v.url} download className="inline-flex min-h-[36px] items-center rounded-lg border border-line px-3 text-xs font-semibold text-cream hover:border-gold/60">
                  Download
                </a>
                {!v.youtube_url && (
                  <div className="[&>button]:min-h-[36px] [&>button]:rounded-lg [&>button]:px-3 [&>button]:text-xs [&>span]:min-h-[36px] [&>span]:text-xs">
                    <PostButton v={v} r={r} ytConfigured={ytConfigured} onChanged={() => videos.mutate()} />
                  </div>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
        </>
      )}
    </section>
  );
}

type YtUploads = { channel_title: string | null; videos: { id: string; title: string; url: string; published_at: string; thumbnail: string | null; privacy: string | null }[] };

/** "On YouTube": read live from the connected channel, so it survives server restarts. */
function YouTubeList({ connected, uploads, error, retry, local }: { connected: boolean; uploads?: YtUploads; error?: ApiError; retry: () => void; local: Video[] }) {
  if (!connected) {
    return local.length ? (
      <ul className="grid gap-3 sm:grid-cols-2">
        {local.map((v) => (
          <li key={v.id} className="card rounded-xl border p-3 text-sm">
            <div className="font-display text-xl uppercase text-cream">{v.dish}</div>
            <a href={v.youtube_url!} target="_blank" rel="noreferrer" className="text-xs text-ok hover:underline">
              {v.youtube_url}
            </a>
          </li>
        ))}
      </ul>
    ) : (
      <p className="rounded-xl border border-dashed border-line px-5 py-8 text-center text-sm text-muted">Connect YouTube to see everything you&apos;ve posted.</p>
    );
  }
  if (error) return <ErrorCallout error={error} onRetry={retry} />;
  if (!uploads)
    return (
      <div className="flex justify-center py-8">
        <Spinner className="h-6 w-6 text-gold" />
      </div>
    );
  if (!uploads.videos.length)
    return <p className="rounded-xl border border-dashed border-line px-5 py-8 text-center text-sm text-muted">Nothing on {uploads.channel_title ?? "your channel"} yet.</p>;
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {uploads.videos.map((y) => (
        <li key={y.id} className="card flex gap-3 rounded-xl border p-3">
          <a href={y.url} target="_blank" rel="noreferrer" className="relative block h-[90px] w-[120px] shrink-0 overflow-hidden rounded-md bg-black">
            {y.thumbnail && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={y.thumbnail} alt="" loading="lazy" className="h-full w-full object-cover" />
            )}
            <span className="absolute inset-0 grid place-items-center text-xl text-white/90">▶</span>
          </a>
          <div className="min-w-0 flex-1">
            <div className="line-clamp-2 text-sm font-semibold text-cream">{y.title}</div>
            <div className="mt-1 text-xs text-muted">
              {y.published_at ? timeAgo(y.published_at) : ""}
              {y.privacy && y.privacy !== "public" ? ` · ${y.privacy}` : ""}
            </div>
            <a href={y.url} target="_blank" rel="noreferrer" className="mt-1 block truncate text-xs text-ok hover:underline">
              Open on YouTube ↗
            </a>
          </div>
        </li>
      ))}
    </ul>
  );
}

function YouTubeStatus({ r, ytConfigured }: { r: Restaurant; ytConfigured: boolean }) {
  const restaurant = useRestaurant();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  if (!ytConfigured) return null;
  const connect = async () => {
    setBusy(true);
    try {
      const { url } = await api<{ url: string }>("/youtube/auth/url");
      window.location.href = url;
    } catch (e) {
      toast((e as Error).message, "bad");
      setBusy(false);
    }
  };
  const disconnect = async () => {
    setBusy(true);
    try {
      await api("/youtube/disconnect", { method: "POST" });
      setYtBlob(null);
      await restaurant.mutate();
      toast("YouTube disconnected. Connect again to pick a channel.", "info");
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-black/40 px-4 py-3 text-sm">
      <div className="flex min-w-0 items-center gap-2">
        <span className="grid h-7 w-10 shrink-0 place-items-center rounded-md bg-[#ff0033] text-[11px] font-bold text-white">▶</span>
        {r.youtube_connected ? (
          <span className="truncate text-cream">
            Posting to <b>{r.youtube_channel_title ?? "your channel"}</b>
          </span>
        ) : (
          <span className="text-muted">YouTube not connected</span>
        )}
      </div>
      {r.youtube_connected ? (
        <Button variant="ghost" className="min-h-[36px]" onClick={disconnect} loading={busy}>
          Switch channel
        </Button>
      ) : (
        <Button className="min-h-[36px]" onClick={connect} loading={busy}>
          Connect YouTube
        </Button>
      )}
    </div>
  );
}
