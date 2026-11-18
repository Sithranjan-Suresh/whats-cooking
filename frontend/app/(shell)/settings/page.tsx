"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import { api, fetcher, setOwnerToken, ApiError } from "@/lib/api";
import { cx, money } from "@/lib/format";
import type { AppSettings, Restaurant } from "@/lib/types";
import { useHealth, useIsOwner, useOwnerToken, useRestaurant, useUsage } from "@/hooks/data";
import { Badge, Button, Card, ErrorCallout, Field, inputCls, SectionTitle, Skeleton, Toggle, useToast } from "@/components/ui";
import { useTheme } from "@/lib/theme";
import { BudgetSummary } from "@/components/themed/budget";

export default function SettingsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <Settings />
    </Suspense>
  );
}

function Settings() {
  const owner = useIsOwner();
  const params = useSearchParams();
  const toast = useToast();
  const r = useRestaurant();
  const { t } = useTheme();
  useEffect(() => {
    const yt = params.get("youtube");
    if (yt === "connected") {
      toast("YouTube connected", "ok");
      r.mutate();
    } else if (yt === "error") toast(`YouTube connection failed (${params.get("reason") ?? "unknown"})`, "bad");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  return (
    <div>
      <SectionTitle title={t.settings.title} eyebrow={t.settings.eyebrow} sub={t.settings.sub} />
      <OwnerUnlock />
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <BudgetCard owner={owner} />
          <YouTubeCard owner={owner} restaurant={r.data} />
        </div>
        <BrandCard owner={owner} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- owner unlock
function OwnerUnlock() {
  const token = useOwnerToken();
  const health = useHealth();
  const [value, setValue] = useState("");
  const toast = useToast();
  const owner = health.data?.actor === "owner";
  const badToken = health.error?.code === "bad_owner_token";
  useEffect(() => {
    if (badToken) {
      setOwnerToken(null);
      toast("That owner token is wrong", "bad");
    }
  }, [badToken, toast]);
  if (owner && token) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ok/30 bg-ok/5 px-4 py-3 text-sm">
        <span>
          <b className="text-ok">Owner mode</b> <span className="text-muted">· Veo, publishing and settings are unlocked on this device.</span>
        </span>
        <Button variant="ghost" className="min-h-[36px]" onClick={() => setOwnerToken(null)}>
          Lock
        </Button>
      </div>
    );
  }
  if (owner) return null; // local dev without a token configured
  return (
    <Card className="p-4">
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (value.trim()) setOwnerToken(value.trim());
          setValue("");
        }}
      >
        <div className="min-w-[220px] flex-1">
          <Field label="Owner unlock" htmlFor="tok" hint="Demo viewers can look around. The owner token unlocks Veo, publishing and editing.">
            <input id="tok" type="password" autoComplete="current-password" className={inputCls} value={value} onChange={(e) => setValue(e.target.value)} placeholder="Owner token" />
          </Field>
        </div>
        <Button type="submit" disabled={!value.trim()}>
          Unlock
        </Button>
      </form>
    </Card>
  );
}

// ---------------------------------------------------------------- budget
function BudgetCard({ owner }: { owner: boolean }) {
  const { t } = useTheme();
  const restaurantName = useRestaurant().data?.name;
  const usage = useUsage();
  const settings = useSWR<AppSettings, ApiError>("/settings", fetcher);
  const [limit, setLimit] = useState<string>("");
  const [cap, setCap] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const toast = useToast();

  useEffect(() => {
    if (settings.data) {
      setLimit(String(settings.data.daily_veo_clip_limit));
      setCap((settings.data.monthly_cap_cents / 100).toFixed(2));
    }
  }, [settings.data]);

  const patch = async (body: Partial<AppSettings>) => {
    setSaving(true);
    setErr(null);
    try {
      const s = await api<AppSettings>("/settings", { method: "PATCH", json: body });
      settings.mutate(s, { revalidate: false });
      usage.mutate();
      return true;
    } catch (e) {
      setErr(e as ApiError);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const u = usage.data;
  const limitN = Number(limit);
  const capN = Number(cap);
  const limitValid = Number.isInteger(limitN) && limitN >= 0 && limitN <= 50;
  const capValid = !Number.isNaN(capN) && capN >= 0 && capN <= 100;
  const dirty = settings.data && (limitN !== settings.data.daily_veo_clip_limit || Math.round(capN * 100) !== settings.data.monthly_cap_cents);

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-3xl uppercase tracking-wide kitchen:text-2xl kitchen:normal-case">{t.settings.budget}</h2>
        {u && <Badge tone={u.free_mode ? "info" : "gold"}>{u.free_mode ? t.settings.freeMode : "Veo enabled"}</Badge>}
      </div>
      {usage.error && <ErrorCallout error={usage.error} onRetry={() => usage.mutate()} />}
      {!u && !usage.error && <Skeleton className="h-40" />}
      {u && (
        <>
          <BudgetSummary u={u} restaurant={restaurantName} />

          <div className="mt-5 flex items-center justify-between gap-4 rounded-xl border border-line bg-bg/40 px-4 py-3">
            <div>
              <label htmlFor="free" className="text-sm font-semibold text-cream">
                {t.settings.freeMode}
              </label>
              <div className="text-xs text-muted">{t.settings.freeModeSub}</div>
            </div>
            <Toggle
              id="free"
              label={t.settings.freeMode}
              checked={u.free_mode}
              disabled={!owner || saving}
              onChange={async (v) => {
                if (await patch({ free_mode: v })) toast(v ? `${t.settings.freeMode} on: $0 per video` : `${t.settings.freeMode} off`, "ok");
              }}
            />
          </div>

          <form
            className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!limitValid || !capValid) return;
              if (await patch({ daily_veo_clip_limit: limitN, monthly_cap_cents: Math.round(capN * 100) })) toast("Limits saved", "ok");
            }}
          >
            <Field label="Daily Veo clip limit" htmlFor="lim" hint={!limitValid ? <span className="text-bad">0 to 50</span> : undefined}>
              <input id="lim" inputMode="numeric" className={inputCls} value={limit} onChange={(e) => setLimit(e.target.value)} disabled={!owner} />
            </Field>
            <Field label="Monthly cap ($)" htmlFor="cap" hint={!capValid ? <span className="text-bad">$0 to $100</span> : undefined}>
              <input id="cap" inputMode="decimal" className={inputCls} value={cap} onChange={(e) => setCap(e.target.value)} disabled={!owner} />
            </Field>
            <Button type="submit" disabled={!owner || !dirty || !limitValid || !capValid} loading={saving}>
              Save
            </Button>
          </form>
          {err && (
            <div className="mt-3">
              <ErrorCallout error={err} />
            </div>
          )}
          <p className="mt-4 text-xs leading-relaxed text-muted">
            Three layers keep spend capped: prepaid API credits with auto-reload off, a monthly cap on the AI Studio project, and this in-app guard, which reserves each clip
            before calling Veo and refuses any clip over the daily limit or the monthly cap.
          </p>
          {!owner && <p className="mt-2 text-xs text-gold">Unlock as owner to change limits.</p>}
        </>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- YouTube
function YouTubeCard({ owner, restaurant }: { owner: boolean; restaurant?: Restaurant }) {
  const { t } = useTheme();
  const health = useHealth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const toast = useToast();
  const r = useRestaurant();
  const connect = async () => {
    setBusy(true);
    setErr(null);
    try {
      const { url } = await api<{ url: string }>("/youtube/auth/url");
      window.location.href = url;
    } catch (e) {
      setErr(e as ApiError);
      setBusy(false);
    }
  };
  const disconnect = async () => {
    try {
      await api("/youtube/disconnect", { method: "POST" });
      r.mutate();
      toast("YouTube disconnected", "info");
    } catch (e) {
      toast((e as Error).message, "bad");
    }
  };
  return (
    <Card className="p-5">
      <div id="youtube" className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-3xl uppercase tracking-wide kitchen:text-2xl kitchen:normal-case">{t.settings.youtube}</h2>
        {restaurant && <Badge tone={restaurant.youtube_connected ? "ok" : "neutral"}>{restaurant.youtube_connected ? "Connected" : "Not connected"}</Badge>}
      </div>
      {restaurant?.youtube_connected ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-cream">
            Publishing to <b>{restaurant.youtube_channel_title ?? "your channel"}</b>
          </div>
          {owner && (
            <Button variant="ghost" onClick={disconnect} className="min-h-[36px]">
              Disconnect
            </Button>
          )}
        </div>
      ) : (
        <>
          <p className="text-sm text-muted">Connect the restaurant&apos;s channel once. Then every video publishes in one click from Library.</p>
          {health.data && !health.data.youtube_configured && <p className="mt-2 text-xs text-gold">The server has no Google OAuth client yet.</p>}
          <Button className="mt-4" onClick={connect} loading={busy} disabled={!owner || (health.data && !health.data.youtube_configured)}>
            Connect YouTube
          </Button>
          {!owner && <p className="mt-2 text-xs text-muted">Owner only.</p>}
        </>
      )}
      {err && (
        <div className="mt-3">
          <ErrorCallout error={err} />
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- brand
const TONES = [
  { id: "friendly", label: "Friendly" },
  { id: "upbeat", label: "Upbeat" },
  { id: "elegant", label: "Elegant" },
] as const;

function BrandCard({ owner }: { owner: boolean }) {
  const { t } = useTheme();
  const r = useRestaurant();
  const [form, setForm] = useState<Partial<Restaurant>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const [logoBusy, setLogoBusy] = useState(false);
  const logoInput = useRef<HTMLInputElement>(null);
  const toast = useToast();

  useEffect(() => {
    if (r.data) setForm(r.data);
  }, [r.data]);

  if (r.error) return <ErrorCallout error={r.error} onRetry={() => r.mutate()} />;
  if (!r.data) return <Skeleton className="h-[520px]" />;

  const set = <K extends keyof Restaurant>(k: K, v: Restaurant[K]) => setForm((f) => ({ ...f, [k]: v }));
  const hex = /^#[0-9A-Fa-f]{6}$/;
  const valid = !!form.name?.trim() && hex.test(form.color_primary ?? "") && hex.test(form.color_accent ?? "");
  const dirty = (["name", "color_primary", "color_accent", "voice_tone", "tts_voice"] as const).some((k) => form[k] !== r.data![k]);

  const save = async () => {
    setSaving(true);
    setErr(null);
    try {
      const out = await api<Restaurant>("/restaurants/me", {
        method: "PATCH",
        json: { name: form.name, color_primary: form.color_primary, color_accent: form.color_accent, voice_tone: form.voice_tone, tts_voice: form.tts_voice },
      });
      r.mutate(out, { revalidate: false });
      toast("Brand saved. It applies to the next render.", "ok");
    } catch (e) {
      setErr(e as ApiError);
    } finally {
      setSaving(false);
    }
  };

  const uploadLogo = async (f: File) => {
    if (!["image/png", "image/jpeg", "image/webp"].includes(f.type) || f.size > 10 * 1024 * 1024) {
      toast("Use a PNG under 10 MB", "bad");
      return;
    }
    setLogoBusy(true);
    const fd = new FormData();
    fd.append("file", f);
    fd.append("kind", "logo");
    try {
      const a = await api<{ asset_id: number }>("/uploads", { form: fd });
      const out = await api<Restaurant>("/restaurants/me", { method: "PATCH", json: { logo_asset_id: a.asset_id } });
      r.mutate(out, { revalidate: false });
      toast("Logo updated", "ok");
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setLogoBusy(false);
    }
  };

  return (
    <Card className="p-5">
      <h2 className="mb-4 font-display text-3xl uppercase tracking-wide kitchen:text-2xl kitchen:normal-case">{t.settings.brand}</h2>
      <CaptionPreview name={form.name ?? ""} primary={form.color_primary ?? "#C49A4A"} accent={form.color_accent ?? "#F3EBDD"} logo={r.data.logo_url} />
      <fieldset disabled={!owner} className="mt-5 space-y-4 disabled:opacity-70">
        <Field label="Restaurant name" htmlFor="rn">
          <input id="rn" className={inputCls} value={form.name ?? ""} maxLength={60} onChange={(e) => set("name", e.target.value)} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          {(["color_primary", "color_accent"] as const).map((k) => (
            <Field key={k} label={k === "color_primary" ? "Primary color" : "Accent color"} htmlFor={k}>
              <div className="flex items-center gap-2">
                <input aria-label={`${k} picker`} type="color" className="h-11 w-12 shrink-0 cursor-pointer" value={hex.test(form[k] ?? "") ? form[k] : "#000000"} onChange={(e) => set(k, e.target.value.toUpperCase())} />
                <input id={k} className={cx(inputCls, "font-mono uppercase", !hex.test(form[k] ?? "") && "border-bad")} value={form[k] ?? ""} onChange={(e) => set(k, e.target.value)} />
              </div>
            </Field>
          ))}
        </div>
        <Field label="Logo">
          <div className="flex items-center gap-3">
            {r.data.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={r.data.logo_url} alt="Logo" className="h-12 w-12 rounded-lg bg-bg object-contain p-1" />
            ) : (
              <div className="h-12 w-12 rounded-lg bg-bg" />
            )}
            <Button variant="ghost" type="button" onClick={() => logoInput.current?.click()} loading={logoBusy} className="min-h-[40px]">
              Upload PNG
            </Button>
            <input
              ref={logoInput}
              type="file"
              accept="image/png,image/webp,image/jpeg"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) uploadLogo(f);
                e.target.value = "";
              }}
            />
          </div>
        </Field>
        <Field label="Voice tone">
          <div className="grid grid-cols-3 gap-1 rounded-xl bg-bg p-1">
            {TONES.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => set("voice_tone", t.id)}
                aria-pressed={form.voice_tone === t.id}
                className={cx("min-h-[38px] rounded-lg text-sm font-semibold", form.voice_tone === t.id ? "bg-panel2 text-gold" : "text-muted hover:text-cream")}
              >
                {t.label}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Voiceover voice" htmlFor="voice">
          <select id="voice" className={inputCls} value={form.tts_voice ?? ""} onChange={(e) => set("tts_voice", e.target.value)}>
            {r.data.voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
              </option>
            ))}
          </select>
        </Field>
      </fieldset>
      {err && (
        <div className="mt-3">
          <ErrorCallout error={err} />
        </div>
      )}
      <div className="mt-5 flex justify-end gap-2">
        {dirty && (
          <Button variant="ghost" onClick={() => setForm(r.data!)}>
            Reset
          </Button>
        )}
        <Button onClick={save} disabled={!owner || !dirty || !valid} loading={saving}>
          Save brand
        </Button>
      </div>
    </Card>
  );
}

/** Mirrors the burned-in ASS caption style (Oswald bold, accent text, dark outline) and the end card. */
function CaptionPreview({ name, primary, accent, logo }: { name: string; primary: string; accent: string; logo: string | null }) {
  const outline = "0 0 1px #0b0b0b, 2px 2px 0 #0b0b0b, -2px 2px 0 #0b0b0b, 2px -2px 0 #0b0b0b, -2px -2px 0 #0b0b0b, 0 3px 6px rgba(0,0,0,.6)";
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="relative aspect-[9/16] overflow-hidden rounded-xl bg-gradient-to-b from-[#5a3b1c] via-[#7a5124] to-[#3a2714]">
        <div className="absolute inset-x-0 top-[17%] px-3 text-center [font-family:var(--f-bebas)] tracking-wide text-[min(5.5vw,26px)] font-bold uppercase leading-tight" style={{ color: primary, textShadow: outline }}>
          People keep coming back
        </div>
        <div className="absolute inset-x-0 bottom-[22%] px-3 text-center [font-family:var(--f-bebas)] tracking-wide text-[min(5vw,24px)] font-bold leading-tight" style={{ color: accent, textShadow: outline }}>
          Chicken Biryani
        </div>
        <div className="absolute bottom-2 left-2 rounded bg-black/50 px-1.5 text-[10px] uppercase tracking-wider text-cream/80">Captions</div>
      </div>
      <div className="relative flex aspect-[9/16] flex-col items-center justify-center overflow-hidden rounded-xl p-3 text-center" style={{ background: primary }}>
        {logo && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={logo} alt="" className="mb-3 h-14 w-14 object-contain" />
        )}
        <div className="[font-family:var(--f-bebas)] tracking-wide text-[min(6vw,28px)] font-bold uppercase leading-none" style={{ color: endCardText(primary, accent) }}>
          {name || "Your name"}
        </div>
        <div className="my-2 h-0.5 w-10" style={{ background: endCardText(primary, accent) }} />
        <div className="text-xs font-semibold" style={{ color: endCardText(primary, accent) }}>
          Chicken Biryani
        </div>
        <div className="text-xl [font-family:var(--f-bebas)]" style={{ color: endCardText(primary, accent) }}>
          $14.99
        </div>
        <div className="absolute bottom-2 left-2 rounded bg-black/50 px-1.5 text-[10px] uppercase tracking-wider text-cream/80">End card</div>
      </div>
    </div>
  );
}

function lum(h: string) {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(h);
  if (!m) return 0;
  const [r, g, b] = [m[1], m[2], m[3]].map((x) => parseInt(x, 16) / 255);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
// Same contrast rule as render.render_end_card.
function endCardText(primary: string, accent: string) {
  if (lum(primary) >= 0.5) return "#141814";
  return lum(accent) < 0.45 ? "#F3EBDD" : accent;
}
