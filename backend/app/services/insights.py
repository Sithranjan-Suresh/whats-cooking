"""Sales CSV parsing, menu matching and promotion ranking (pure Python, engineering spec §5.3)."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from rapidfuzz import fuzz, process

from ..util import normalize_name, parse_price_cents

ALIASES = {
    "date": ["date", "order_date", "business_date", "order date", "business date", "day"],
    "item_name": ["item_name", "item", "menu_item", "item name", "menu item", "name", "product"],
    "quantity": ["quantity", "qty", "count", "quantity sold", "qty sold", "units", "items sold"],
    "revenue": ["revenue", "net sales", "net_sales", "amount", "gross sales", "sales"],
}

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%m-%Y", "%Y/%m/%d", "%b %d, %Y", "%d %b %Y", "%m-%d-%Y")


@dataclass
class ParsedRow:
    date: date
    item_name: str
    quantity: int
    revenue_cents: Optional[int]


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    dropped: int = 0
    missing_columns: list[str] = field(default_factory=list)


class CsvFormatError(ValueError):
    pass


def _map_columns(header: list[str]) -> dict[str, int]:
    norm = [h.strip().lower().replace("﻿", "") for h in header]
    out: dict[str, int] = {}
    for key, names in ALIASES.items():
        for i, h in enumerate(norm):
            if h in names or h.replace(" ", "_") in names:
                out[key] = i
                break
    return out


def parse_date(raw: str) -> Optional[date]:
    raw = (raw or "").strip()
    if not raw:
        return None
    raw = raw.split("T")[0].split(" ")[0] if ("T" in raw or (raw.count(" ") == 1 and ":" in raw)) else raw
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(raw, f).date()
        except ValueError:
            continue
    return None


def parse_sales_csv(text: str) -> ParseResult:
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as e:
        raise CsvFormatError("The file is empty.") from e
    cols = _map_columns(header)
    missing = [k for k in ("date", "item_name", "quantity") if k not in cols]
    if missing:
        raise CsvFormatError(
            "Missing column(s): " + ", ".join(missing) + ". Expected date, item_name, quantity (revenue optional)."
        )
    res = ParseResult()
    for row in reader:
        if not row or all(not c.strip() for c in row):
            continue
        try:
            d = parse_date(row[cols["date"]])
            name = row[cols["item_name"]].strip()
            qraw = row[cols["quantity"]].strip().replace(",", "")
            q = int(float(qraw)) if qraw else None
        except (IndexError, ValueError):
            res.dropped += 1
            continue
        if d is None or not name or q is None or q <= 0:  # refunds / voids / blanks
            res.dropped += 1
            continue
        rev = None
        if "revenue" in cols and cols["revenue"] < len(row):
            rev = parse_price_cents(row[cols["revenue"]])
        res.rows.append(ParsedRow(d, name, q, rev))
    return res


def build_matcher(menu: list[tuple[int, str]]):
    """menu: [(id, name)] → function(raw_name) -> Optional[id]"""
    exact = {name.strip().lower(): mid for mid, name in menu}
    normed = {normalize_name(name): mid for mid, name in menu}
    choices = list(normed.keys())
    cache: dict[str, Optional[int]] = {}

    def match(raw: str) -> Optional[int]:
        if raw in cache:
            return cache[raw]
        key = raw.strip().lower()
        mid = exact.get(key)
        if mid is None:
            n = normalize_name(raw)
            mid = normed.get(n)
            if mid is None and n and choices:
                best = process.extractOne(n, choices, scorer=fuzz.ratio)
                if best and best[1] >= 85:
                    mid = normed[best[0]]
        cache[raw] = mid
        return mid

    return match


def top_matches(query: str, menu: list[tuple[int, str]], k: int = 3) -> list[int]:
    if not menu:
        return []
    names = {mid: normalize_name(n) for mid, n in menu}
    scored = process.extract(normalize_name(query or ""), names, scorer=fuzz.WRatio, limit=k)
    return [mid for (_n, _score, mid) in scored]


# ------------------------------------------------------------------ ranking

@dataclass
class Pick:
    angle: str
    menu_item_id: int
    metric: dict


def rank(
    sales: Iterable[tuple[date, int, int]],
    items_with_photo: set[int],
) -> list[Pick]:
    """sales: (date, menu_item_id, quantity) for matched rows only.

    Windows are anchored to the max date in the data (not today).
    """
    sales = list(sales)
    if not sales:
        return []
    max_d = max(d for d, _, _ in sales)
    min_d = min(d for d, _, _ in sales)
    span_days = (max_d - min_d).days + 1
    w7 = max_d - timedelta(days=6)
    p7_start, p7_end = max_d - timedelta(days=13), max_d - timedelta(days=7)
    qty7: dict[int, int] = defaultdict(int)
    qprev: dict[int, int] = defaultdict(int)
    qty14: dict[int, int] = defaultdict(int)
    all_items = set()
    for d, mid, q in sales:
        all_items.add(mid)
        if d >= w7:
            qty7[mid] += q
        if p7_start <= d <= p7_end:
            qprev[mid] += q
        if d >= p7_start:
            qty14[mid] += q

    picks: list[Pick] = []
    used: set[int] = set()
    # Top seller
    top = max(all_items, key=lambda m: (qty7[m], qty14[m], -m))
    if qty7[top] > 0:
        picks.append(Pick("top_seller", top, {"qty_7d": qty7[top], "qty_14d": qty14[top]}))
        used.add(top)
    if span_days < 14:
        return picks
    # Rising
    rising_cands = [m for m in all_items if m not in used and qty7[m] >= 10 and qprev[m] >= 3]
    if rising_cands:
        def wow(m):
            return (qty7[m] - qprev[m]) / qprev[m]

        r = max(rising_cands, key=lambda m: (wow(m), qty7[m]))
        if wow(r) > 0:
            picks.append(
                Pick("rising", r, {"qty_7d": qty7[r], "qty_prev_7d": qprev[r], "wow_pct": round(wow(r) * 100)})
            )
            used.add(r)
    # Slow mover (needs a photo so we can make a video)
    slow_cands = [m for m in all_items | items_with_photo if m not in used and m in items_with_photo]
    if slow_cands:
        s = min(slow_cands, key=lambda m: (qty14[m], qty7[m], m))
        picks.append(Pick("slow_mover", s, {"qty_7d": qty7[s], "qty_14d": qty14[s]}))
    return picks


def metric_label(angle: str, m: dict) -> str:
    if angle == "rising":
        return f"+{m.get('wow_pct', 0)}% WoW · {m.get('qty_7d', 0)} sold"
    if angle == "top_seller":
        return f"#1 this week · {m.get('qty_7d', 0)} sold"
    return f"{m.get('qty_14d', 0)} sold in 14 days"


def rule_reason(angle: str, dish: str, m: dict) -> str:
    if angle == "rising":
        return f"{dish} is up {m.get('wow_pct', 0)}% vs last week with {m.get('qty_7d', 0)} sold. Ride the momentum."
    if angle == "top_seller":
        return f"{dish} is your best seller this week with {m.get('qty_7d', 0)} sold. Show people what everyone orders."
    return f"Only {m.get('qty_14d', 0)} {dish} sold in the last 14 days. A video can introduce it to new guests."
