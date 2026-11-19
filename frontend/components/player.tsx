"use client";
import { useEffect, useRef, useState } from "react";
import { cx } from "@/lib/format";
import { Button } from "@/components/ui";

export function PhonePlayer({
  src,
  poster,
  placeholder,
  playing,
  overlay,
  dim = true,
}: {
  src?: string | null;
  poster?: string | null;
  placeholder?: string | null;
  playing?: boolean;
  overlay?: React.ReactNode;
  dim?: boolean;
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
            <img src={placeholder} alt="" className={cx("h-full w-full object-cover", dim && "opacity-60")} />
          ) : (
            <div className="grain h-full w-full bg-panel" />
          )}
          {failed && <div className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-cream">Couldn&apos;t load the video. Use Download instead.</div>}
        </div>
      )}
      {overlay && <div className="pointer-events-none absolute inset-0 z-10">{overlay}</div>}
    </div>
  );
}

// ---------------------------------------------------------------- MenuPicker
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
