"use client";
import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { api, fetcher, ApiError } from "@/lib/api";
import { ANGLE_HINT, ANGLE_LABEL, cx, money } from "@/lib/format";
import type { InsightCard, InsightsResponse, MenuItem, Style } from "@/lib/types";
import { useIsOwner, useJob, useUsage } from "@/hooks/data";
import { Badge, Button, Card, ErrorCallout, SectionTitle, Skeleton, Toggle, useToast } from "@/components/ui";
import { DishPickerModal, EditCaptionsModal, MenuPicker, PhotoDrop, validatePhoto } from "@/components/studio";
import { GenerateButton, PlayerStage, ScriptSheet, StageBoard } from "@/components/themed/studio";
import { useTheme } from "@/lib/theme";

type Source = "photo" | "insight" | "menu";
const LAST_JOB = "wc_last_job";

export default function StudioPage() {
  return (
    <Suspense fallback={<Skeleton className="h-[600px]" />}>
      <Studio />
    </Suspense>
  );
}

function Studio() {
  const params = useSearchParams();
  const router = useRouter();
  const toast = useToast();
  const owner = useIsOwner();
  const { t, theme } = useTheme();
  const usage = useUsage();
  const menuQ = useSWR<MenuItem[], ApiError>("/menu", fetcher);
  const menu = menuQ.data ?? [];

  const insightParam = params.get("insight");
  const itemParam = params.get("item");
  const jobParam = params.get("job");

  const [source, setSource] = useState<Source>(insightParam ? "insight" : itemParam ? "menu" : "photo");
  const [insightId, setInsightId] = useState<number | null>(insightParam ? Number(insightParam) : null);
  const [itemId, setItemId] = useState<number | null>(itemParam ? Number(itemParam) : null);
  const [photoDishId, setPhotoDishId] = useState<number | null>(null);
  const [photo, setPhoto] = useState<{ id: number; url: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [style, setStyle] = useState<Style>("bold");
  const [length, setLength] = useState<15 | 30>(15);
  const [veo, setVeo] = useState(false);
  const [jobId, setJobId] = useState<number | null>(jobParam ? Number(jobParam) : null);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<ApiError | null>(null);
  const [editing, setEditing] = useState(false);

  // Restore the last job when returning to Studio with no params (job keeps running server-side).
  useEffect(() => {
    if (jobParam || insightParam || itemParam) return;
    try {
      const last = window.localStorage.getItem(LAST_JOB);
      if (last) setJobId(Number(last));
    } catch {
      /* ignore */
    }
  }, [jobParam, insightParam, itemParam]);

  useEffect(() => {
    if (insightParam) {
      setSource("insight");
      setInsightId(Number(insightParam));
      setJobId(null);
    }
    if (itemParam) {
      setSource("menu");
      setItemId(Number(itemParam));
      setJobId(null);
    }
  }, [insightParam, itemParam]);

  const insights = useSWR<InsightsResponse, ApiError>(source === "insight" ? "/insights" : null, fetcher);
  const insight: InsightCard | null = useMemo(() => insights.data?.cards.find((c) => c.id === insightId) ?? null, [insights.data, insightId]);
  const insightItem = insight ? menu.find((m) => m.id === insight.menu_item.id) ?? null : null;
  const menuItem = menu.find((m) => m.id === itemId) ?? null;

  const { job, error: jobError, refresh } = useJob(jobId);
  const busy = !!job && ["queued", "running"].includes(job.status);
  const restaurantQ = useSWR<{ name: string }, ApiError>("/restaurants/me", fetcher);
  const restaurantName = restaurantQ.data?.name;

  // Toast + usage refresh when a job finishes.
  const [notified, setNotified] = useState<number | null>(null);
  useEffect(() => {
    if (!job || notified === job.id) return;
    if (job.status === "done") {
      setNotified(job.id);
      toast(t.toast.done, "ok");
      usage.mutate();
    } else if (job.status === "failed") {
      setNotified(job.id);
      toast(job.error || t.toast.failed, "bad");
      usage.mutate();
    }
  }, [job, notified, toast, usage, t]);

  const veoInfo = usage.data?.veo;
  const veoAllowed = !!veoInfo?.allowed;
  useEffect(() => {
    if (!veoAllowed) setVeo(false);
  }, [veoAllowed]);

  const dish: MenuItem | null = source === "insight" ? insightItem : source === "menu" ? menuItem : menu.find((m) => m.id === photoDishId) ?? null;
  const needsPhoto = source !== "photo" && dish && !dish.photo_url;
  const previewImg = photo?.url ?? dish?.photo_url ?? null;

  const ready =
    (source === "photo" && !!photo) ||
    (source === "insight" && !!insight && (!!insightItem?.photo_url || !!photo)) ||
    (source === "menu" && !!menuItem && (!!menuItem.photo_url || !!photo));

  const uploadPhoto = async (f: File) => {
    const err = validatePhoto(f);
    if (err) {
      setPhotoError(err);
      return;
    }
    setPhotoError(null);
    setUploading(true);
    const form = new FormData();
    form.append("file", f);
    form.append("kind", "photo");
    try {
      const r = await api<{ asset_id: number; url: string }>("/uploads", { form });
      setPhoto({ id: r.asset_id, url: r.url });
      // Owners: save it as the dish photo so Insights/Studio reuse it next time.
      if (owner && source !== "photo" && dish && !dish.photo_url) {
        await api(`/menu/${dish.id}/photo`, { json: { asset_id: r.asset_id } }).catch(() => {});
        menuQ.mutate();
      }
    } catch (e) {
      setPhotoError((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const generate = async () => {
    setCreating(true);
    setCreateError(null);
    const body: Record<string, unknown> = { mode: source, style, length_s: length, veo: veo && veoAllowed };
    if (source === "photo") {
      body.photo_asset_id = photo?.id;
      if (photoDishId) body.menu_item_id = photoDishId;
    } else if (source === "insight") {
      body.insight_id = insightId;
      if (photo) body.photo_asset_id = photo.id;
    } else {
      body.menu_item_id = itemId;
      if (photo) body.photo_asset_id = photo.id;
    }
    try {
      const r = await api<{ job_id: number }>("/jobs", { json: body });
      startTracking(r.job_id);
    } catch (e) {
      setCreateError(e as ApiError);
    } finally {
      setCreating(false);
    }
  };

  const startTracking = useCallback(
    (id: number) => {
      setJobId(id);
      setNotified(null);
      try {
        window.localStorage.setItem(LAST_JOB, String(id));
      } catch {
        /* ignore */
      }
      router.replace(`/studio?job=${id}`, { scroll: false });
    },
    [router],
  );

  const retry = async () => {
    if (!job) return;
    try {
      const r = await api<{ job_id: number }>(`/jobs/${job.id}/retry`, { method: "POST" });
      startTracking(r.job_id);
    } catch (e) {
      toast((e as Error).message, "bad");
    }
  };

  const newVideo = () => {
    setJobId(null);
    try {
      window.localStorage.removeItem(LAST_JOB);
    } catch {
      /* ignore */
    }
    router.replace("/studio", { scroll: false });
  };

  // ------------------------------------------------------------ render
  const showResult = !!jobId;
  return (
    <div>
      <SectionTitle
        title={t.studio.title}
        eyebrow={t.studio.eyebrow}
        sub={t.studio.sub}
        right={
          showResult && !busy ? (
            <Button variant="ghost" onClick={newVideo}>
              + {t.studio.again}
            </Button>
          ) : null
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] xl:grid-cols-[minmax(0,1fr)_370px]">
        <div className="space-y-6">
          {!showResult && (
            <Card className="p-5">
              {/* Input picker */}
              <div role="tablist" aria-label="Start from" className="mb-5 grid grid-cols-3 gap-1 rounded-xl bg-bg p-1">
                {(
                  [
                    ["photo", t.studio.tabs.photo],
                    ["insight", t.studio.tabs.insight],
                    ["menu", t.studio.tabs.menu],
                  ] as [Source, string][]
                ).map(([k, label]) => (
                  <button
                    key={k}
                    role="tab"
                    aria-selected={source === k}
                    onClick={() => {
                      setSource(k);
                      setPhoto(null);
                    }}
                    className={cx("min-h-[40px] rounded-lg text-sm font-semibold transition", source === k ? "bg-panel2 text-gold shadow" : "text-muted hover:text-cream")}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {source === "photo" && (
                <div className="space-y-4">
                  <PhotoDrop onFile={uploadPhoto} busy={uploading} preview={photo?.url} />
                  {photoError && <p className="text-sm text-bad">{photoError}</p>}
                  <details className="rounded-xl border border-line px-3 py-2">
                    <summary className="cursor-pointer text-sm text-muted">
                      Which dish is it? <span className="text-cream">{photoDishId ? menu.find((m) => m.id === photoDishId)?.name : "Optional, we'll detect it"}</span>
                    </summary>
                    <div className="mt-3">
                      <MenuPicker menu={menu} value={photoDishId} onChange={(m) => setPhotoDishId(m.id === photoDishId ? null : m.id)} compact />
                    </div>
                  </details>
                </div>
              )}

              {source === "insight" && (
                <div>
                  {insights.error && <ErrorCallout error={insights.error} onRetry={() => insights.mutate()} />}
                  {!insights.data && !insights.error && <Skeleton className="h-24" />}
                  {insights.data && insights.data.cards.length === 0 && (
                    <p className="text-sm text-muted">
                      No insights yet. <Link href="/insights" className="text-gold underline">Upload sales data</Link> first.
                    </p>
                  )}
                  {insights.data && insights.data.cards.length > 0 && (
                    <div className="grid gap-2 sm:grid-cols-3">
                      {insights.data.cards.map((c) => (
                        <button
                          key={c.id}
                          onClick={() => setInsightId(c.id)}
                          className={cx("rounded-xl border p-3 text-left transition", insightId === c.id ? "border-gold bg-gold/10" : "border-line hover:border-gold/50")}
                        >
                          <Badge tone="gold">{ANGLE_LABEL[c.angle]}</Badge>
                          <div className="mt-2 text-sm font-semibold text-cream">{c.menu_item.name}</div>
                          <div className="font-mono text-xs text-muted">{c.metric_label}</div>
                        </button>
                      ))}
                    </div>
                  )}
                  {insight && (
                    <div className="mt-4 rounded-xl border border-line bg-bg/40 p-3 text-sm">
                      <span className="text-muted">Angle:</span> <b className="text-gold">{ANGLE_HINT[insight.angle]}</b>
                      <span className="text-muted"> · the hook will lean on this.</span>
                    </div>
                  )}
                </div>
              )}

              {source === "menu" && <MenuPicker menu={menu} value={itemId} onChange={(m) => setItemId(m.id)} />}

              {needsPhoto && (
                <div className="mt-4">
                  <PhotoDrop onFile={uploadPhoto} busy={uploading} preview={photo?.url} label={`${dish?.name} has no photo yet. Add one.`} />
                  {photoError && <p className="mt-2 text-sm text-bad">{photoError}</p>}
                </div>
              )}

              {/* Options */}
              <div className="mt-6 grid gap-4 border-t border-line pt-5 sm:grid-cols-2">
                <div>
                  <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">Style</div>
                  <div className="grid grid-cols-3 gap-1 rounded-xl bg-bg p-1">
                    {(["bold", "warm", "minimal"] as Style[]).map((s) => (
                      <button
                        key={s}
                        onClick={() => setStyle(s)}
                        aria-pressed={style === s}
                        className={cx("min-h-[38px] rounded-lg text-sm font-semibold capitalize", style === s ? "bg-panel2 text-gold" : "text-muted hover:text-cream")}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">Length</div>
                  <div className="grid grid-cols-2 gap-1 rounded-xl bg-bg p-1">
                    {([15, 30] as const).map((l) => (
                      <button
                        key={l}
                        onClick={() => setLength(l)}
                        aria-pressed={length === l}
                        className={cx("min-h-[38px] rounded-lg font-mono text-sm font-semibold", length === l ? "bg-panel2 text-gold" : "text-muted hover:text-cream")}
                      >
                        {l}s
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-4 flex items-center justify-between gap-4 rounded-xl border border-line bg-bg/40 px-4 py-3">
                <div className="min-w-0">
                  <label htmlFor="veo" className="text-sm font-semibold text-cream">
                    {t.studio.veo}{" "}
                    {veoInfo && <span className="font-mono text-gold">≈ {money(veoInfo.est_cents)}</span>}
                  </label>
                  <div className="text-xs text-muted">
                    {veoAllowed
                      ? t.studio.veoOn
                      : veoInfo?.message || "Loading budget…"}
                  </div>
                </div>
                <Toggle id="veo" label={t.studio.veo} checked={veo} onChange={setVeo} disabled={!veoAllowed} />
              </div>

              {createError && (
                <div className="mt-4">
                  <ErrorCallout error={createError} onRetry={generate} />
                </div>
              )}

              <GenerateButton onClick={generate} disabled={!ready} loading={creating} />
              {!ready && (
                <p className="mt-2 text-center text-xs text-muted">
                  {source === "photo" ? "Add a dish photo to start." : source === "insight" ? (insight ? "Add a photo for this dish." : "Pick an insight.") : menuItem ? "Add a photo for this dish." : "Pick a dish."}
                </p>
              )}
            </Card>
          )}

          {showResult && (
            <Card className="grid gap-6 p-5 md:grid-cols-2">
              <div>
                {jobError ? (
                  <ErrorCallout error={jobError} onRetry={refresh} title="Lost track of this job" />
                ) : !job ? (
                  <Skeleton className="h-72" />
                ) : (
                  <>
                    {job.menu_item && (
                      <div className="mb-4 flex items-center gap-2">
                        <span className={cx("text-cream", theme === "studio" ? "font-display text-[30px] uppercase tracking-[.04em]" : "font-display text-2xl")}>{job.menu_item.name}</span>
                        {job.angle && <Badge tone="gold">{ANGLE_LABEL[job.angle]}</Badge>}
                      </div>
                    )}
                    <StageBoard job={job} />
                    {job.status === "failed" && (
                      <div className="mt-4">
                        <ErrorCallout error={job.error || "Render failed."} title={`Failed at ${job.error_stage ?? "a stage"}`} onRetry={retry} />
                      </div>
                    )}
                    {job.analyze?.warning && job.status !== "failed" && <p className="mt-3 text-xs text-gold">⚠ {job.analyze.warning}</p>}
                    {job.flags?.captions_only && <p className="mt-3 text-xs text-gold">Voice was unavailable, so this video has captions and music only.</p>}
                  </>
                )}
              </div>
              <div className="md:border-l md:border-line md:pl-6">
                <ScriptSheet script={job?.script ?? null} loading={busy} restaurant={restaurantName} />
              </div>
            </Card>
          )}
        </div>

        {/* Player column */}
        <div className={cx("lg:sticky lg:top-8 lg:self-start", showResult && "order-first lg:order-none")}>
          <PlayerStage job={job} previewImg={previewImg} busy={busy} />
          {job?.status === "done" && job.video && (
            <div className="mx-auto mt-4 max-w-[320px] space-y-2">
              <div className="flex items-center justify-center gap-2 text-xs text-muted">
                <Badge tone={job.veo_used ? "gold" : "neutral"}>{job.veo_used ? "Veo" : theme === "studio" ? "Free rig" : "Free"}</Badge>
                <span className="font-mono">{theme === "studio" ? `Cost to make: ${money(job.cost_cents)}` : `On the bill: ${money(job.cost_cents)}`}</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <a
                  href={job.video.url}
                  download={`${(job.menu_item?.name ?? "short").replace(/\W+/g, "-").toLowerCase()}.mp4`}
                  className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-line text-sm font-semibold text-cream hover:border-gold/60"
                >
                  Download
                </a>
                <button
                  onClick={() => setEditing(true)}
                  className="order-last col-span-2 inline-flex min-h-[44px] items-center justify-center rounded-xl border border-line text-sm font-semibold text-cream hover:border-gold/60"
                >
                  Edit captions &amp; re-render
                </button>
                <Link href={`/library?video=${job.video.id}`} className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-gold text-sm font-semibold text-ongold hover:bg-gold2">
                  {owner ? (theme === "studio" ? "Premiere →" : "Run it →") : `${t.nav.library} →`}
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>

      {job?.status === "needs_dish" && <DishPickerModal job={job} menu={menu} onResolved={refresh} />}
      {editing && job?.script && <EditCaptionsModal jobId={job.id} script={job.script} onClose={() => setEditing(false)} onStarted={startTracking} />}
    </div>
  );
}

