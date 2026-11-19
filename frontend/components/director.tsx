"use client";
// Director mode: the AI drafts a storyboard for the dish, the owner refines it in a chat (or with one-tap ideas),
// can preview a frame of the shot, and only then renders. The server re-checks the plan against the menu.
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, ApiError } from "@/lib/api";
import { cx } from "@/lib/format";
import type { DirectorPlan, DirectorTurn, Storyboard } from "@/lib/types";
import { Button, ErrorCallout, Modal, Spinner } from "@/components/ui";

const IDEAS = ["Steamy close-up", "Make it cozy", "More energy", "Slow and elegant", "Mention the price", "Shorter captions"];

export function DirectorPanel({
  menuItemId,
  dishName,
  storyboard,
  onStoryboard,
  onPreview,
}: {
  menuItemId: number;
  dishName: string;
  storyboard: Storyboard | null;
  onStoryboard: (sb: Storyboard | null) => void;
  onPreview: (url: string | null) => void;
}) {
  const [turns, setTurns] = useState<DirectorTurn[]>([]);
  const [chips, setChips] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewErr, setPreviewErr] = useState<ApiError | null>(null);
  const [zoom, setZoom] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);

  const ask = async (message?: string) => {
    setThinking(true);
    setError(null);
    const history = message ? [...turns, { role: "user" as const, text: message }] : turns;
    if (message) setTurns(history);
    try {
      const r = await api<DirectorPlan>("/director/plan", {
        json: { menu_item_id: menuItemId, message: message ?? null, storyboard, history: turns.slice(-16) },
      });
      onStoryboard(r.storyboard);
      setChips(r.suggestions);
      setTurns([...history, { role: "assistant", text: r.reply }]);
      if (r.source === "gemini" && message) {
        setPreview(null); // the shot may have changed
        onPreview(null);
      }
    } catch (e) {
      setError(e as ApiError);
      if (message) setTurns(turns); // let them resend
    } finally {
      setThinking(false);
    }
  };

  // First storyboard as soon as the panel opens for this dish.
  useEffect(() => {
    setTurns([]);
    setPreview(null);
    onPreview(null);
    if (!storyboard) ask();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menuItemId]);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [turns, thinking]);

  const send = (m: string) => {
    const msg = m.trim();
    if (!msg || thinking) return;
    setText("");
    ask(msg);
  };

  const makePreview = async () => {
    if (!storyboard) return;
    setPreviewing(true);
    setPreviewErr(null);
    try {
      const r = await api<{ url: string }>("/director/preview", { json: { menu_item_id: menuItemId, storyboard } });
      setPreview(r.url);
      onPreview(r.url);
    } catch (e) {
      setPreviewErr(e as ApiError);
    } finally {
      setPreviewing(false);
    }
  };

  return (
    <div className="mt-5 space-y-4">
      {/* ---------------- storyboard */}
      <section aria-label="Storyboard" className="rounded-xl border border-gold/40 bg-black/30 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="font-mono text-[11px] uppercase tracking-[.25em] text-gold">Storyboard · {dishName}</div>
          {thinking && <Spinner className="h-4 w-4 text-gold" />}
        </div>
        {!storyboard ? (
          <div className="space-y-2" aria-hidden>
            {[70, 90, 60, 80].map((w, i) => (
              <div key={i} className="h-4 animate-pulse rounded bg-panel2" style={{ width: `${w}%` }} />
            ))}
            <p className="pt-1 text-xs text-muted">The director is drafting your Short…</p>
          </div>
        ) : (
          <motion.div key={storyboard.hook + storyboard.shot} initial={{ opacity: 0.4 }} animate={{ opacity: 1 }} className="space-y-3">
            <div>
              <Label>Hook · first second</Label>
              <div className="font-display text-[26px] uppercase leading-tight tracking-[.02em] text-cream">{storyboard.hook}</div>
            </div>
            <div>
              <Label>Captions</Label>
              <ol className="space-y-1.5">
                {storyboard.beats.map((b, i) => (
                  <li key={i} className="flex items-start gap-3 rounded-lg bg-panel2/70 px-3 py-2 text-sm">
                    <span className="font-display text-lg leading-none text-gold">{i + 1}</span>
                    <span className="flex-1 whitespace-pre-line text-cream">{b.caption}</span>
                    <span className="font-mono text-[11px] text-muted">{b.seconds.toFixed(1)}s</span>
                  </li>
                ))}
                <li className="flex items-center gap-3 rounded-lg border border-dashed border-line px-3 py-2 text-xs text-muted">
                  <span className="font-display text-lg leading-none text-gold/60">★</span> Your logo, the dish and its price
                </li>
              </ol>
            </div>
            <div>
              <Label>🎙 Narration</Label>
              <p className="text-sm italic text-cream/90">&ldquo;{storyboard.voiceover}&rdquo;</p>
            </div>
            <div className="flex flex-wrap items-start gap-3">
              <div className="min-w-[180px] flex-1">
                <Label>🎥 The shot</Label>
                <p className="text-sm text-cream/90">{storyboard.shot}</p>
              </div>
              {preview ? (
                <button type="button" onClick={() => setZoom(true)} aria-label="Enlarge preview frame" className="overflow-hidden rounded-lg ring-1 ring-gold/50">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={preview} alt="Preview frame of the shot" className="h-28 w-16 object-cover" />
                </button>
              ) : (
                <Button variant="ghost" className="min-h-[40px]" onClick={makePreview} loading={previewing} disabled={thinking}>
                  {previewing ? "Painting a frame…" : "Preview a frame"}
                </Button>
              )}
            </div>
            {previewErr && <ErrorCallout error={previewErr} onRetry={makePreview} />}
          </motion.div>
        )}
      </section>

      {/* ---------------- chat */}
      <section aria-label="Director's chat" className="rounded-xl border border-line bg-black/30">
        <div className="max-h-72 space-y-2 overflow-y-auto p-4" aria-live="polite">
          {turns.length === 0 && !thinking && <p className="text-sm text-muted">Tell the director what you want: a mood, a detail to show, what to say.</p>}
          <AnimatePresence initial={false}>
            {turns.map((t, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className={cx("max-w-[85%] rounded-2xl px-3.5 py-2 text-sm", t.role === "user" ? "ml-auto rounded-br-md bg-gold text-ongold" : "rounded-bl-md bg-panel2 text-cream")}
              >
                {t.role === "assistant" && <span className="mr-1">🎬</span>}
                {t.text}
              </motion.div>
            ))}
          </AnimatePresence>
          {thinking && (
            <div className="inline-flex items-center gap-2 rounded-2xl rounded-bl-md bg-panel2 px-3.5 py-2 text-sm text-muted">
              <Spinner className="h-3.5 w-3.5" /> Directing…
            </div>
          )}
          <div ref={chatEnd} />
        </div>
        {error && (
          <div className="px-4 pb-3">
            <ErrorCallout error={error} onRetry={() => ask()} />
          </div>
        )}
        <div className="flex flex-wrap gap-2 border-t border-line px-4 pt-3">
          {[...chips, ...IDEAS.filter((i) => !chips.includes(i))].slice(0, 6).map((c) => (
            <button
              key={c}
              type="button"
              disabled={thinking || !storyboard}
              onClick={() => send(c)}
              className="min-h-[36px] rounded-full border border-line px-3 text-xs text-cream transition hover:border-gold/60 disabled:opacity-40"
            >
              {c}
            </button>
          ))}
        </div>
        <form
          className="flex gap-2 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            send(text);
          }}
        >
          <label htmlFor="director-input" className="sr-only">
            Message to the director
          </label>
          <input
            id="director-input"
            value={text}
            maxLength={400}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. Show the naan dipping in, make it feel like a rainy night"
            className="min-h-[46px] w-full rounded-xl border border-line bg-bg px-3 text-sm text-cream placeholder:text-muted/60 focus:border-gold focus:outline-none focus:ring-1 focus:ring-gold"
          />
          <Button type="submit" disabled={!text.trim() || thinking || !storyboard} className="shrink-0">
            Send
          </Button>
        </form>
      </section>
      <p className="text-center text-[11px] text-muted">Planning and previews don&apos;t use your AI videos. The video is made when you hit Action!</p>
      {zoom && preview && (
        <Modal open title="Preview frame" onClose={() => setZoom(false)}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={preview} alt="Preview frame of the shot" className="mx-auto max-h-[70vh] rounded-lg" />
          <p className="mt-3 text-center text-xs text-muted">A still of the planned shot. The video animates your real dish photo.</p>
        </Modal>
      )}
    </div>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">{children}</div>;
}
