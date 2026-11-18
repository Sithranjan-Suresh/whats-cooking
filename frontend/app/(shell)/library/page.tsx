"use client";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { api, fetcher, ApiError } from "@/lib/api";
import { cx, money, timeAgo } from "@/lib/format";
import type { Job, Privacy, Restaurant, Video } from "@/lib/types";
import { useIsOwner } from "@/hooks/data";
import { Badge, Button, EmptyState, ErrorCallout, Field, inputCls, Modal, SectionTitle, Skeleton, Spinner, useToast } from "@/components/ui";
import { PhonePlayer } from "@/components/studio";

export default function LibraryPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <Library />
    </Suspense>
  );
}

function Library() {
  const params = useSearchParams();
  const router = useRouter();
  const owner = useIsOwner();
  const videos = useSWR<Video[], ApiError>("/videos", fetcher, {
    refreshInterval: (data) => (data?.some((v) => v.publish_status === "publishing") ? 2000 : 0),
  });
  const active = useSWR<Job[], ApiError>("/jobs?status=active", fetcher, {
    refreshInterval: (data) => (data && data.length ? 2000 : 15000),
  });
  const restaurant = useSWR<Restaurant, ApiError>("/restaurants/me", fetcher);
  const [openId, setOpenId] = useState<number | null>(params.get("video") ? Number(params.get("video")) : null);
  const [prevActive, setPrevActive] = useState(0);

  // When an in-progress job finishes, pull the new video in.
  useEffect(() => {
    const n = active.data?.length ?? 0;
    if (n < prevActive) videos.mutate();
    setPrevActive(n);
  }, [active.data, prevActive, videos]);

  const open = videos.data?.find((v) => v.id === openId) ?? null;
  const close = () => {
    setOpenId(null);
    router.replace("/library", { scroll: false });
  };

  return (
    <div>
      <SectionTitle
        title="Library"
        sub={videos.data ? `${videos.data.length} video${videos.data.length === 1 ? "" : "s"} · newest first` : "Every Short you've made"}
        right={
          <Link href="/studio" className="inline-flex min-h-[44px] items-center rounded-xl bg-gold px-4 text-sm font-semibold text-bg hover:bg-gold2">
            + New video
          </Link>
        }
      />

      {videos.error && <ErrorCallout error={videos.error} onRetry={() => videos.mutate()} title="Couldn't load your videos" />}

      {!videos.data && !videos.error && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="aspect-[9/16]" />
          ))}
        </div>
      )}

      {videos.data && (
        <>
          {videos.data.length === 0 && !(active.data?.length) ? (
            <EmptyState
              icon={<span className="text-4xl">🎬</span>}
              title="No videos yet"
              body="Make your first Short in Studio. It lands here, ready to publish."
              action={
                <Link href="/studio" className="inline-flex min-h-[44px] items-center rounded-xl bg-gold px-4 text-sm font-semibold text-bg">
                  Open Studio
                </Link>
              }
            />
          ) : (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
              {(active.data ?? []).map((j) => (
                <ActiveTile key={`j${j.id}`} job={j} />
              ))}
              {videos.data.map((v) => (
                <VideoTile key={v.id} v={v} onOpen={() => setOpenId(v.id)} />
              ))}
            </div>
          )}
        </>
      )}

      {open && (
        <VideoModal
          v={open}
          owner={owner}
          ytConnected={!!restaurant.data?.youtube_connected}
          onClose={close}
          onChanged={() => videos.mutate()}
        />
      )}
    </div>
  );
}

function statusBadge(v: Video) {
  if (v.publish_status === "published") return <Badge tone="ok">Published</Badge>;
  if (v.publish_status === "publishing") return <Badge tone="gold">Publishing {v.publish_progress}%</Badge>;
  if (v.publish_status === "failed") return <Badge tone="bad">Publish failed</Badge>;
  return <Badge>Draft</Badge>;
}

function VideoTile({ v, onOpen }: { v: Video; onOpen: () => void }) {
  return (
    <article className="group animate-fadeup overflow-hidden rounded-xl border border-line bg-panel">
      <button onClick={onOpen} className="relative block aspect-[9/16] w-full overflow-hidden bg-black" aria-label={`Play ${v.dish ?? "video"}`}>
        {v.poster_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={v.poster_url} alt="" loading="lazy" className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]" />
        ) : (
          <div className="h-full w-full bg-panel2" />
        )}
        <span className="absolute inset-0 grid place-items-center opacity-0 transition group-hover:opacity-100">
          <span className="grid h-14 w-14 place-items-center rounded-full bg-black/60 text-2xl text-cream backdrop-blur">▶</span>
        </span>
        <span className="absolute left-2 top-2">{statusBadge(v)}</span>
        <span className="absolute bottom-2 right-2 rounded bg-black/70 px-1.5 py-0.5 font-mono text-[11px] text-cream">{Math.round(v.duration_s)}s</span>
      </button>
      <div className="p-3">
        <div className="truncate text-sm font-semibold text-cream">{v.dish ?? "Dish"}</div>
        <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted">
          <span>{timeAgo(v.created_at)}</span>
          <span className="flex items-center gap-1.5">
            <span className={cx("font-semibold uppercase", v.mode === "veo" ? "text-gold" : "text-muted")}>{v.mode === "veo" ? "Veo" : "Free"}</span>
            <span className="font-mono">{money(v.cost_cents)}</span>
          </span>
        </div>
        {v.youtube_url && (
          <a href={v.youtube_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex text-xs font-semibold text-ok hover:underline">
            Published ↗
          </a>
        )}
      </div>
    </article>
  );
}

function ActiveTile({ job }: { job: Job }) {
  const done = job.stages.filter((s) => s.status === "done").length;
  const current = job.stages.find((s) => s.status === "running");
  return (
    <Link href={`/studio?job=${job.id}`} className="overflow-hidden rounded-xl border border-gold/40 bg-panel">
      <div className="relative aspect-[9/16] bg-black">
        {job.photo_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={job.photo_url} alt="" className="h-full w-full object-cover opacity-40" />
        )}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-3 text-center">
          {job.status === "needs_dish" ? (
            <Badge tone="gold">Needs you</Badge>
          ) : (
            <Spinner className="h-8 w-8 text-gold" />
          )}
          <div className="font-display text-lg uppercase text-cream">{job.status === "needs_dish" ? "Pick the dish" : current?.name ?? "Queued"}</div>
          <div className="h-1.5 w-3/4 overflow-hidden rounded-full bg-bg">
            <div className="h-full bg-gold transition-all" style={{ width: `${(done / 5) * 100}%` }} />
          </div>
        </div>
      </div>
      <div className="p-3 text-sm font-semibold text-cream">{job.menu_item?.name ?? "New video"}</div>
    </Link>
  );
}

function VideoModal({ v, owner, ytConnected, onClose, onChanged }: { v: Video; owner: boolean; ytConnected: boolean; onClose: () => void; onChanged: () => void }) {
  const [publishing, setPublishing] = useState(false);
  return (
    <Modal open title={v.dish ?? "Video"} onClose={onClose} wide>
      <div className="grid gap-6 sm:grid-cols-[260px_1fr]">
        <PhonePlayer src={v.url} poster={v.poster_url} />
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {statusBadge(v)}
            <Badge tone={v.mode === "veo" ? "gold" : "neutral"}>{v.mode === "veo" ? "Veo" : "Free mode"}</Badge>
            <span className="font-mono text-xs text-muted">
              {money(v.cost_cents)} · {(v.bytes / 1e6).toFixed(1)} MB · {v.width}×{v.height}
            </span>
          </div>
          {v.title && <div className="text-sm font-semibold text-cream">{v.title}</div>}
          <CostReceipt v={v} />

          {v.youtube_url && (
            <div className="rounded-xl border border-ok/30 bg-ok/5 p-3 text-sm">
              <a href={v.youtube_url} target="_blank" rel="noreferrer" className="font-semibold text-ok hover:underline">
                Published on YouTube ↗
              </a>
              <div className="mt-1 break-all font-mono text-xs text-muted">{v.youtube_url}</div>
              {v.youtube_privacy && v.youtube_privacy !== "public" && (
                <div className="mt-2 text-xs text-cream/80">
                  YouTube status: <b className="capitalize">{v.youtube_privacy}</b>. YouTube keeps uploads from unverified apps private until review.
                </div>
              )}
            </div>
          )}
          {v.publish_status === "failed" && v.publish_error && <ErrorCallout error={`Publish failed · ${v.publish_error}`} />}
          {v.publish_status === "publishing" && (
            <div className="rounded-xl border border-line p-3">
              <div className="mb-2 flex justify-between text-sm text-cream">
                <span>Uploading to YouTube…</span>
                <span className="font-mono">{v.publish_progress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-bg">
                <div className="h-full bg-gold transition-all" style={{ width: `${v.publish_progress}%` }} />
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <a href={v.url} download className="inline-flex min-h-[44px] items-center rounded-xl border border-line px-4 text-sm font-semibold text-cream hover:border-gold/60">
              Download
            </a>
            {!owner ? (
              <span className="self-center text-xs text-muted">Publishing is owner-only in demo mode.</span>
            ) : !ytConnected ? (
              <Link href="/settings#youtube" className="inline-flex min-h-[44px] items-center rounded-xl bg-gold px-4 text-sm font-semibold text-bg">
                Connect YouTube
              </Link>
            ) : v.publish_status !== "publishing" ? (
              <Button onClick={() => setPublishing(true)}>{v.publish_status === "published" ? "Publish again" : v.publish_status === "failed" ? "Retry publish" : "Publish to YouTube"}</Button>
            ) : null}
          </div>
        </div>
      </div>
      {publishing && <PublishDialog v={v} onClose={() => setPublishing(false)} onDone={onChanged} />}
    </Modal>
  );
}

function PublishDialog({ v, onClose, onDone }: { v: Video; onClose: () => void; onDone: () => void }) {
  const [title, setTitle] = useState(v.title ?? v.dish ?? "");
  const [description, setDescription] = useState(v.description ?? "");
  const [tags, setTags] = useState((v.hashtags ?? []).join(" "));
  const [privacy, setPrivacy] = useState<Privacy>("private");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const toast = useToast();
  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api(`/videos/${v.id}/publish`, {
        json: { title, description, tags: tags.split(/[\s,]+/).filter(Boolean), privacy },
      });
      toast("Uploading to YouTube…", "info");
      onDone();
      onClose();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open title="Publish to YouTube" onClose={onClose}>
      <div className="space-y-4">
        <Field label="Title" htmlFor="pt" hint={<span className={cx(title.length > 70 && "text-gold")}>{title.length}/100 · keep it under 70 so it isn&apos;t cut off</span>}>
          <input id="pt" className={inputCls} value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label="Description" htmlFor="pd">
          <textarea id="pd" className={cx(inputCls, "min-h-[90px]")} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <Field label="Hashtags" htmlFor="ph" hint="#Shorts is added automatically">
          <input id="ph" className={inputCls} value={tags} onChange={(e) => setTags(e.target.value)} />
        </Field>
        <Field label="Privacy">
          <div className="grid grid-cols-3 gap-1 rounded-xl bg-bg p-1">
            {(["private", "unlisted", "public"] as Privacy[]).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPrivacy(p)}
                aria-pressed={privacy === p}
                className={cx("min-h-[38px] rounded-lg text-sm font-semibold capitalize", privacy === p ? "bg-panel2 text-gold" : "text-muted hover:text-cream")}
              >
                {p}
              </button>
            ))}
          </div>
        </Field>
        <p className="text-xs text-muted">Note: YouTube keeps uploads from unverified apps private until the app passes Google&apos;s review.</p>
        {error && <ErrorCallout error={error} onRetry={submit} />}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} loading={busy} disabled={!title.trim()}>
            Publish
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function CostReceipt({ v }: { v: Video }) {
  const usage = useSWR<{ cost_per_sec_cents: number }, ApiError>("/usage", fetcher);
  const rate = usage.data?.cost_per_sec_cents;
  const rows: [string, string][] = [
    ["Script + photo analysis (Gemini Flash, free tier)", "$0.00"],
    [v.mode === "veo" ? `AI motion: Veo 8s${rate ? ` × ${money(rate)}/s` : ""}` : "Visuals: Ken Burns (free mode)", v.mode === "veo" ? money(v.cost_cents) : "$0.00"],
    ["Voiceover (edge-tts)", "$0.00"],
    ["Render (ffmpeg, our server)", "$0.00"],
  ];
  return (
    <details className="rounded-xl border border-line bg-bg/40 px-3 py-2 text-sm">
      <summary className="flex cursor-pointer items-center justify-between text-cream">
        <span>Cost receipt</span>
        <span className="font-mono text-gold">{money(v.cost_cents)}</span>
      </summary>
      <table className="mt-2 w-full text-xs">
        <tbody>
          {rows.map(([k, val]) => (
            <tr key={k} className="border-t border-line/60">
              <td className="py-1.5 pr-2 text-muted">{k}</td>
              <td className="py-1.5 text-right font-mono text-cream">{val}</td>
            </tr>
          ))}
          <tr className="border-t border-line">
            <td className="py-1.5 font-semibold text-cream">Total</td>
            <td className="py-1.5 text-right font-mono font-semibold text-gold">{money(v.cost_cents)}</td>
          </tr>
        </tbody>
      </table>
      <p className="mt-1 text-[11px] text-muted">Veo is an estimate from the per-second rate; Google bills the same rate.</p>
    </details>
  );
}
