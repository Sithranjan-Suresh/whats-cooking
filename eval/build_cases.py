"""Build eval/cases.json: 12 photo cases (menu rows) + 8 sales scenarios with known answers.

Run: python eval/build_cases.py   (deterministic)
"""
import csv
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MENU = {r["name"]: r for r in csv.DictReader(open(ROOT / "seed" / "kumars_menu.csv"))}

PHOTO_CASES = [
    ("Chicken Biryani", "seed/photos/chicken-biryani.jpg"),
    ("Butter Chicken", "seed/photos/butter-chicken.jpg"),
    ("Palak Paneer", "seed/photos/palak-paneer.jpg"),
    ("Malai Kofta", "seed/photos/malai-kofta.jpg"),
    ("Tandoori Chicken", "seed/photos/tandoori-chicken.jpg"),
    ("Vegetable Samosa", "seed/photos/vegetable-samosa.jpg"),
    ("Garlic Naan", "seed/photos/garlic-naan.jpg"),
    ("Mango Lassi", "seed/photos/mango-lassi.jpg"),
    ("Lamb Rogan Josh", "eval/photos/lamb-rogan-josh.jpg"),
    ("Chana Masala", "eval/photos/chana-masala.jpg"),
    ("Gulab Jamun", "eval/photos/gulab-jamun.jpg"),
    ("Chef's Thali", "eval/photos/chefs-thali.jpg"),  # null price case
]


def row(name):
    m = MENU[name]
    price = f"${float(m['price']):.2f}" if m["price"] else None
    return {"name": name, "price": price, "description": m["description"] or None}


def weekly_rows(spec, end=date(2026, 11, 15)):
    """spec: {item: [w1..wn]} → CSV rows spread across each week."""
    out = []
    weeks = len(next(iter(spec.values())))
    start = end - timedelta(days=weeks * 7 - 1)
    for item, totals in spec.items():
        for w, t in enumerate(totals):
            per = [t // 7 + (1 if d < t % 7 else 0) for d in range(7)]
            for d, q in enumerate(per):
                if q:
                    out.append([(start + timedelta(days=w * 7 + d)).isoformat(), item, q])
    return out


SALES = [
    ("baseline_kumars", {"Butter Chicken": [105, 108, 112], "Chicken Biryani": [50, 63, 83], "Malai Kofta": [7, 6, 5], "Garlic Naan": [90, 92, 94]},
     "Butter Chicken", "Chicken Biryani"),
    ("rising_is_small_item", {"Butter Chicken": [100, 100, 100], "Mango Lassi": [10, 12, 30], "Chicken Biryani": [60, 60, 66]},
     "Butter Chicken", "Mango Lassi"),
    ("tiny_item_ignored", {"Butter Chicken": [90, 90, 92], "Gulab Jamun": [1, 2, 9], "Garlic Naan": [40, 40, 52]},
     "Butter Chicken", "Garlic Naan"),
    ("new_top_seller", {"Butter Chicken": [80, 80, 70], "Chicken Biryani": [60, 75, 95], "Palak Paneer": [30, 30, 31]},
     "Chicken Biryani", "Palak Paneer"),
    ("flat_week", {"Butter Chicken": [50, 50, 50], "Tandoori Chicken": [40, 40, 41], "Chana Masala": [20, 20, 22]},
     "Butter Chicken", "Chana Masala"),
    ("pos_spellings", {"Chicken Biriyani": [40, 40, 70], "Butter Chicken (LG)": [90, 92, 91], "Veg Samosa": [30, 30, 31]},
     "Butter Chicken", "Chicken Biryani"),
    ("declining_top", {"Garlic Naan": [150, 140, 120], "Mango Lassi": [40, 44, 60], "Butter Chicken": [100, 100, 101]},
     "Garlic Naan", "Mango Lassi"),
    ("short_history", {"Butter Chicken": [0, 0, 40], "Chicken Biryani": [0, 0, 55]},
     "Chicken Biryani", None),
]


def main():
    cases = []
    for i, (name, photo) in enumerate(PHOTO_CASES, 1):
        r = row(name)
        cases.append({"id": f"photo_{i:02d}", "type": "photo", "photo": photo, "menu_row": r,
                      "expected": {"name": r["name"], "price": r["price"]}})
    for i, (cid, spec, top, rising) in enumerate(SALES, 1):
        rows = weekly_rows({k: [x for x in v] for k, v in spec.items()})
        if cid == "short_history":  # only the last week exists
            rows = [r_ for r_ in rows if r_[0] >= "2026-11-09"]
        cases.append({"id": f"sales_{i:02d}_{cid}", "type": "sales", "csv_rows": rows,
                      "expected_top_seller": top, "expected_rising": rising})
    (ROOT / "eval" / "cases.json").write_text(json.dumps(cases, indent=1))
    print(len(cases), "cases")


if __name__ == "__main__":
    main()
