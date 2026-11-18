"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Restaurant } from "@/lib/types";
import { useIsOwner, useRestaurant } from "@/hooks/data";
import { Button, inputCls, Spinner, useToast } from "@/components/ui";
import { BulbRow } from "@/components/Shell";
import { cx } from "@/lib/format";

/** Top of On Set: the restaurant's name + logo, used on every video's animated ending. */
export function StudioBranding() {
  const owner = useIsOwner();
  const r = useRestaurant();
  const toast = useToast();
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [logoBusy, setLogoBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (r.data) setName(r.data.name);
  }, [r.data]);

  const saveName = async () => {
    if (!name.trim() || name.trim() === r.data?.name) return;
    setSaving(true);
    try {
      const out = await api<Restaurant>("/restaurants/me", { method: "PATCH", json: { name: name.trim() } });
      r.mutate(out, { revalidate: false });
      toast("Studio name saved", "ok");
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setSaving(false);
    }
  };

  const uploadLogo = async (f: File) => {
    if (!["image/png", "image/jpeg", "image/webp"].includes(f.type) || f.size > 10 * 1024 * 1024) {
      toast("Use a PNG or JPG under 10 MB", "bad");
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
      toast("Logo updated. It closes every video.", "ok");
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setLogoBusy(false);
    }
  };

  return (
    <div className="relative mb-6 overflow-hidden rounded-[14px] border border-gold/25 bg-black/50 px-4 py-4 sm:px-5">
      <BulbRow className="absolute inset-x-4 top-1" n={18} />
      <div className="mt-2 flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={() => owner && file.current?.click()}
          disabled={!owner || logoBusy}
          aria-label="Upload your logo"
          className={cx(
            "group relative grid h-16 w-16 shrink-0 place-items-center overflow-hidden rounded-full bg-[#f6efe4] ring-2 ring-gold/60 transition",
            owner && "hover:ring-gold",
          )}
        >
          {r.data?.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={r.data.logo_url} alt="Your logo" className="h-full w-full object-contain p-1.5" />
          ) : (
            <span className="font-display text-2xl text-[#1a0d0b]">+</span>
          )}
          {logoBusy ? (
            <span className="absolute inset-0 grid place-items-center bg-black/60">
              <Spinner className="h-5 w-5 text-gold" />
            </span>
          ) : owner ? (
            <span className="absolute inset-x-0 bottom-0 bg-black/70 py-0.5 text-center text-[9px] font-semibold uppercase tracking-wider text-cream opacity-0 transition group-hover:opacity-100">
              Change
            </span>
          ) : null}
        </button>
        <input
          ref={file}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) uploadLogo(f);
            e.target.value = "";
          }}
        />
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[10.5px] uppercase tracking-[.25em] text-muted">Your studio · logo &amp; name close every video</div>
          {owner ? (
            <form
              className="mt-1 flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                saveName();
              }}
            >
              <input
                aria-label="Restaurant name"
                className={cx(inputCls, "max-w-xs bg-transparent font-display !text-2xl uppercase tracking-[.04em]")}
                value={name}
                maxLength={60}
                onChange={(e) => setName(e.target.value)}
                onBlur={saveName}
              />
              {name.trim() !== (r.data?.name ?? "") && (
                <Button type="submit" variant="ghost" className="min-h-[38px]" loading={saving}>
                  Save
                </Button>
              )}
            </form>
          ) : (
            <div className="mt-1 font-display text-3xl uppercase tracking-[.04em] text-cream">{r.data?.name ?? "…"}</div>
          )}
        </div>
        {owner && !r.data?.logo_url && (
          <Button variant="ghost" onClick={() => file.current?.click()} loading={logoBusy}>
            Upload logo
          </Button>
        )}
      </div>
    </div>
  );
}
