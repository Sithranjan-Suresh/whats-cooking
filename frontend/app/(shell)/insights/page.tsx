"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import useSWR from "swr";
import { api, fetcher, ApiError } from "@/lib/api";
import { ANGLE_HINT, ANGLE_LABEL, cx, shortDate } from "@/lib/format";
import type { InsightCard, InsightsResponse, MenuItem, SalesImportResult, SalesSummary } from "@/lib/types";
import { useIsOwner } from "@/hooks/data";
import { useTheme } from "@/lib/theme";
import { InsightBoard } from "@/components/themed/insights";
import { Badge, Button, Card, EmptyState, ErrorCallout, inputCls, SectionTitle, Skeleton, useToast } from "@/components/ui";

export default function InsightsPage() {
  const owner = useIsOwner();
  const { t } = useTheme();
  const ins = useSWR<InsightsResponse, ApiError>("/insights", fetcher);
  const summary = useSWR<SalesSummary, ApiError>("/sales/summary", fetcher);
  const [refreshing, setRefreshing] = useState(false);
  const toast = useToast();

  const refresh = async () => {
    setRefreshing(true);
    try {
      await ins.mutate(api<InsightsResponse>("/insights/refresh", { method: "POST" }), { revalidate: false });
      toast("Insights refreshed", "ok");
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setRefreshing(false);
    }
  };

  const s = summary.data;
  return (
    <div>
      <SectionTitle
        title={t.insights.title}
        eyebrow={t.insights.eyebrow}
        sub={
          s && s.rows > 0
            ? t.insights.sub(s.rows.toLocaleString(), `${shortDate(s.date_from!)} – ${shortDate(s.date_to!)}`)
            : "Upload your sales export and we'll tell you which dish to promote."
        }
        right={
          owner && s && s.rows > 0 ? (
            <Button variant="ghost" onClick={refresh} loading={refreshing}>
              {t.insights.refresh}
            </Button>
          ) : null
        }
      />

      {ins.error && <ErrorCallout error={ins.error} onRetry={() => ins.mutate()} title="Couldn't load insights" />}

      {!ins.data && !ins.error && (
        <div className="grid gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[380px]" />
          ))}
        </div>
      )}

      {ins.data && ins.data.cards.length === 0 && (
        <EmptyState
          icon={<span className="text-4xl">📈</span>}
          title={t.insights.empty}
          body={
            <>
              Export item sales from Toast, Square or Clover as CSV (<code className="font-mono text-cream">date, item_name, quantity, revenue</code>) and upload it below.
            </>
          }
          action={
            <a href="/sample_sales.csv" download className="text-sm font-semibold text-gold underline-offset-4 hover:underline">
              Download a sample CSV
            </a>
          }
        />
      )}

      {ins.data && ins.data.cards.length > 0 && (
        <InsightBoard cards={ins.data.cards} />
      )}

      {ins.data && ins.data.cards.length > 0 && ins.data.cards.length < 3 && (
        <p className="mt-3 text-sm text-muted">Only the top seller is shown. Rising and slow-mover picks need at least 14 days of sales data.</p>
      )}

      <div className="mt-12 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        {owner ? (
          <SalesUpload onDone={() => {
            ins.mutate();
            summary.mutate();
          }} />
        ) : (
          <Card className="p-5 text-sm text-muted">
            <div className="mb-1 font-semibold text-cream">Where these come from</div>
            Kumar&apos;s 8-week item-sales export is already loaded. Picks are computed from the last 7 days vs. the 7 before, then Gemini writes the one-line reason. Unlock as owner in Brand &amp; Budget to upload your own.
          </Card>
        )}
        <Card className="p-5">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">How picks work</div>
          <ul className="space-y-2 text-sm text-cream/90">
            <li><b className="text-gold">Rising:</b> biggest week-over-week growth (10+ sold this week)</li>
            <li><b className="text-gold">Top seller:</b> most sold in the last 7 days</li>
            <li><b className="text-gold">Slow mover:</b> fewest sold in 14 days, among dishes with a photo</li>
          </ul>
          {s && s.unmatched_items.length > 0 && (
            owner ? (
              <UnmatchedMapper items={s.unmatched_items} onMapped={() => {
                summary.mutate();
                ins.mutate();
              }} />
            ) : (
              <div className="mt-4 border-t border-line pt-3 text-xs text-muted">
                Not on your menu (ignored): {s.unmatched_items.slice(0, 8).join(", ")}
                {s.unmatched_items.length > 8 && ` +${s.unmatched_items.length - 8} more`}
              </div>
            )
          )}
        </Card>
      </div>
    </div>
  );
}

function SalesUpload({ onDone }: { onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SalesImportResult | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const toast = useToast();

  const upload = async (f: File) => {
    if (!/\.(csv|txt)$/i.test(f.name) && f.type !== "text/csv") {
      setError(new ApiError("bad_csv", "Upload a .csv file.", false, 400));
      return;
    }
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("file", f);
    try {
      const r = await api<SalesImportResult>("/sales/import", { form });
      setResult(r);
      toast(`Imported ${r.rows.toLocaleString()} rows`, "ok");
      onDone();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5">
      <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted">Upload sales CSV</div>
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
          if (f) upload(f);
        }}
        className={cx("flex flex-col items-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition", drag ? "border-gold bg-gold/5" : "border-line")}
      >
        <p className="text-sm text-cream">Drop your item-sales export here</p>
        <p className="mt-1 text-xs text-muted">Toast, Square or Clover · columns date, item_name, quantity (revenue optional)</p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <Button onClick={() => input.current?.click()} loading={busy}>
            Choose CSV
          </Button>
          <a href="/sample_sales.csv" download className="inline-flex min-h-[44px] items-center px-3 text-sm text-gold hover:underline">
            Sample CSV
          </a>
        </div>
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
      {error && (
        <div className="mt-3">
          <ErrorCallout error={error} />
        </div>
      )}
      {result && (
        <div className="mt-3 rounded-xl border border-line bg-bg/40 p-3 text-sm">
          <div className="text-cream">
            <b>{result.rows.toLocaleString()}</b> rows · {shortDate(result.date_from)} – {shortDate(result.date_to)} ({result.days} days)
          </div>
          {result.dropped > 0 && <div className="text-muted">{result.dropped} invalid rows dropped (refunds, blanks, bad dates)</div>}
          {result.unmatched_items.length > 0 && <div className="text-muted">Not matched to your menu: {result.unmatched_items.join(", ")}</div>}
        </div>
      )}
    </Card>
  );
}

function UnmatchedMapper({ items, onMapped }: { items: string[]; onMapped: () => void }) {
  const menu = useSWR<MenuItem[], ApiError>("/menu", fetcher);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const toast = useToast();
  const map = async (raw: string) => {
    const id = Number(choice[raw]);
    if (!id) return;
    setBusy(raw);
    try {
      const r = await api<{ mapped: number }>("/sales/map", { json: { raw_item_name: raw, menu_item_id: id } });
      toast(`Mapped ${r.mapped} rows of “${raw}”`, "ok");
      onMapped();
    } catch (e) {
      toast((e as Error).message, "bad");
    } finally {
      setBusy(null);
    }
  };
  return (
    <div className="mt-4 border-t border-line pt-3">
      <div className="mb-2 text-xs text-muted">Sales items that didn&apos;t match your menu. Map them, or leave them ignored (gift cards, fees).</div>
      <ul className="space-y-2">
        {items.slice(0, 10).map((raw) => (
          <li key={raw} className="flex flex-wrap items-center gap-2">
            <span className="min-w-[110px] flex-1 truncate text-sm text-cream" title={raw}>{raw}</span>
            <select
              aria-label={`Menu item for ${raw}`}
              className={cx(inputCls, "w-auto min-w-[150px] flex-1 py-2")}
              value={choice[raw] ?? ""}
              onChange={(e) => setChoice((c) => ({ ...c, [raw]: e.target.value }))}
            >
              <option value="">Ignore</option>
              {(menu.data ?? []).map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
            <Button variant="ghost" className="min-h-[38px]" disabled={!choice[raw]} loading={busy === raw} onClick={() => map(raw)}>
              Map
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
