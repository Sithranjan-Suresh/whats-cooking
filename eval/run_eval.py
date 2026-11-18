"""Grounding eval: production write_script (grounded) vs. an ungrounded photo-only prompt (baseline).

    make eval            (= backend/.venv/bin/python eval/run_eval.py)

Photo cases need GEMINI_API_KEY and a real photo at each case's path; missing photos are skipped
(and reported). Sales cases always run (pure Python). Writes eval/results.md.
"""
from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.services import gemini, scripts  # noqa: E402
from app.services.insights import build_matcher, parse_sales_csv, rank  # noqa: E402
from app.util import normalize_name  # noqa: E402

PRICE_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
CLAIM_RE = re.compile(r"(%|\boff\b|discount|award|best in|gluten|vegan|allergen|healthy)", re.I)
MENU_CSV = ROOT / "seed" / "kumars_menu.csv"


# ------------------------------------------------------------------ scoring

def score_text(text: str, row: dict) -> dict:
    name_ok = normalize_name(row["name"]) in normalize_name(text)
    amounts = [float(a) for a in PRICE_RE.findall(text)]
    if row["price"] is None:
        price_ok = not amounts
    else:
        want = float(row["price"].replace("$", ""))
        price_ok = all(abs(a - want) < 0.001 for a in amounts)
    desc = (row.get("description") or "").lower()
    regex_claims = sorted({m.group(0).lower() for m in CLAIM_RE.finditer(text) if m.group(0).lower() not in desc})
    return {"name_ok": name_ok, "price_ok": price_ok, "regex_claims": regex_claims, "amounts": amounts}


async def judge(text: str, row: dict) -> bool:
    try:
        return await gemini.judge_claims(text, row)
    except gemini.GeminiError:
        return True  # judge unavailable: fall back to the regex check only


async def run_photo_case(case: dict, sem: asyncio.Semaphore) -> dict:
    row = case["menu_row"]
    photo = ROOT / case["photo"]
    out = {"id": case["id"], "dish": row["name"], "price": row["price"]}
    if not photo.exists():
        out["skipped"] = f"missing photo {case['photo']}"
        return out
    image = (photo.read_bytes(), "image/png" if photo.suffix.lower() == ".png" else "image/jpeg")
    async with sem:
        # Grounded = the production path (prompt rules + validation + repair + template fallback)
        g_script, g_source, _ = await scripts.write_script(
            menu_row=row, restaurant_name="Kumar's", angle=None, tone="upbeat", style="bold",
            length_s=15, visual_notes="",
        )
        g_text = scripts.spoken_text(g_script)
        try:
            b = await gemini.baseline_script(image)
            b_text = "\n".join([str(b.get("hook", "")), *[str(c) for c in b.get("captions", [])], str(b.get("voiceover", ""))])
        except gemini.GeminiError as e:
            b_text = ""
            out["baseline_error"] = e.kind
        for label, text in (("grounded", g_text), ("baseline", b_text)):
            s = score_text(text, row)
            s["judge_ok"] = await judge(text, row) if text else False
            s["no_invented_claims"] = not s["regex_claims"] and s["judge_ok"]
            s["pass"] = bool(text) and s["name_ok"] and s["price_ok"] and s["no_invented_claims"]
            s["text"] = text
            out[label] = s
        out["grounded_source"] = g_source
    return out


def run_sales_case(case: dict, menu: list[tuple[int, str]]) -> dict:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "item_name", "quantity"])
    w.writerows(case["csv_rows"])
    parsed = parse_sales_csv(buf.getvalue())
    match = build_matcher(menu)
    names = dict(menu)
    sales = [(r.date, match(r.item_name), r.quantity) for r in parsed.rows if match(r.item_name)]
    picks = {p.angle: names[p.menu_item_id] for p in rank(sales, items_with_photo={i for i, _ in menu})}
    top_ok = picks.get("top_seller") == case["expected_top_seller"]
    rising_ok = picks.get("rising") == case["expected_rising"]
    return {"id": case["id"], "top": picks.get("top_seller"), "rising": picks.get("rising"),
            "expected_top": case["expected_top_seller"], "expected_rising": case["expected_rising"],
            "pass": top_ok and rising_ok}


# ------------------------------------------------------------------ report

def fail_reason(s: dict) -> str:
    r = []
    if not s.get("name_ok"):
        r.append("name missing")
    if not s.get("price_ok"):
        r.append(f"wrong/invented price {['$%.2f' % a for a in s.get('amounts', [])]}")
    if s.get("regex_claims"):
        r.append("claims: " + ", ".join(s["regex_claims"]))
    if not s.get("judge_ok", True):
        r.append("judge: invented facts")
    return "; ".join(r) or "ok"


def write_report(photo: list[dict], sales: list[dict], elapsed: float) -> str:
    ran = [p for p in photo if "skipped" not in p]
    g = sum(1 for p in ran if p["grounded"]["pass"])
    b = sum(1 for p in ran if p["baseline"]["pass"])
    sp = sum(1 for s in sales if s["pass"])
    headline = f"grounded {g}/{len(ran)} · baseline {b}/{len(ran)} · sales picks {sp}/{len(sales)}"
    if len(ran) < len(photo):
        headline += f" · {len(photo) - len(ran)} photo cases skipped"
    lines = [
        "# Eval results",
        "",
        f"_Run {datetime.now():%Y-%m-%d %H:%M} · model `{get_settings().gemini_text_model}` · {elapsed:.0f}s_",
        "",
        f"**{headline}**",
        "",
        "Pitch line: *On {n} real menu items, grounded scripts got the dish name and price right with no invented claims "
        "in {g}/{n} cases. An ungrounded photo-only prompt managed {b}/{n}.*".format(n=len(ran), g=g, b=b),
        "",
        "## Photo cases (script grounding)",
        "",
        "Pass = dish name present AND every $ amount equals the menu price (none when price is null) AND no invented claims "
        "(regex for %/off/discount/award/best in/gluten/vegan/allergen/healthy not in the menu description, plus an LLM judge).",
        "",
        "| Case | Dish | Menu price | Grounded | Baseline | Baseline failure |",
        "|---|---|---|---|---|---|",
    ]
    for p in photo:
        if "skipped" in p:
            lines.append(f"| {p['id']} | {p['dish']} | {p['price'] or '—'} | skipped | skipped | {p['skipped']} |")
            continue
        gs, bs = p["grounded"], p["baseline"]
        lines.append(
            f"| {p['id']} | {p['dish']} | {p['price'] or '—'} | {'✅' if gs['pass'] else '❌ ' + fail_reason(gs)}"
            f" ({p['grounded_source']}) | {'✅' if bs['pass'] else '❌'} | {'' if bs['pass'] else fail_reason(bs)} |"
        )
    lines += ["", "## Sales cases (promotion picks)", "", "| Case | Top seller (expected) | Rising (expected) | Pass |", "|---|---|---|---|"]
    for s in sales:
        lines.append(f"| {s['id']} | {s['top']} ({s['expected_top']}) | {s['rising']} ({s['expected_rising']}) | {'✅' if s['pass'] else '❌'} |")
    fails = [p for p in ran if not p["baseline"]["pass"]][:3]
    if fails:
        lines += ["", "## Example baseline failures", ""]
        for p in fails:
            lines += [f"**{p['dish']}** (menu price {p['price'] or 'none'}): {fail_reason(p['baseline'])}", "",
                      "> " + p["baseline"]["text"].replace("\n", " ")[:400], ""]
    (ROOT / "eval" / "results.md").write_text("\n".join(lines) + "\n")
    (ROOT / "eval" / "results.json").write_text(json.dumps({"photo": photo, "sales": sales}, indent=1, default=str))
    return headline


async def main() -> None:
    t0 = time.time()
    cases = json.loads((ROOT / "eval" / "cases.json").read_text())
    menu = [(i + 1, r["name"]) for i, r in enumerate(csv.DictReader(open(MENU_CSV)))]
    sales = [run_sales_case(c, menu) for c in cases if c["type"] == "sales"]
    photo_cases = [c for c in cases if c["type"] == "photo"]
    if not get_settings().gemini_enabled:
        print("GEMINI_API_KEY not set: photo cases skipped (sales cases still run).")
        photo = [{"id": c["id"], "dish": c["menu_row"]["name"], "price": c["menu_row"]["price"],
                  "skipped": "no GEMINI_API_KEY"} for c in photo_cases]
    else:
        sem = asyncio.Semaphore(2)  # stay inside free-tier rate limits
        photo = await asyncio.gather(*(run_photo_case(c, sem) for c in photo_cases))
    print(write_report(list(photo), sales, time.time() - t0))
    print("wrote eval/results.md")


if __name__ == "__main__":
    asyncio.run(main())
