"""Generate deterministic seed inputs that don't need a human:

- kumars_sales_8w.csv  (8 weeks; Butter Chicken = top seller, Chicken Biryani ≈ +32% WoW, Malai Kofta = slow mover)
- music_upbeat.mp3     (synthesized here, so it's royalty-free by construction)
- logo.png             (placeholder monogram, only if no logo.png exists)
- photos/*.jpg         (placeholder illustrations, only for dishes with no real photo yet)

Run: python seed/build_assets.py   (idempotent; never overwrites real photos or a real logo)
"""
from __future__ import annotations

import csv
import math
import random
import struct
import subprocess
import wave
from datetime import date, timedelta
from pathlib import Path

SEED = Path(__file__).resolve().parent
PHOTOS = SEED / "photos"

# Dishes that have photos (file name = slug of the dish name).
PHOTO_DISHES = {
    "chicken-biryani": ("Chicken Biryani", (214, 150, 60), (250, 220, 120)),
    "butter-chicken": ("Butter Chicken", (205, 95, 40), (245, 200, 150)),
    "palak-paneer": ("Palak Paneer", (70, 110, 40), (245, 240, 220)),
    "malai-kofta": ("Malai Kofta", (225, 160, 80), (190, 120, 60)),
    "tandoori-chicken": ("Tandoori Chicken", (190, 60, 35), (240, 220, 200)),
    "vegetable-samosa": ("Vegetable Samosa", (215, 165, 75), (120, 160, 60)),
    "garlic-naan": ("Garlic Naan", (235, 205, 150), (110, 150, 60)),
    "mango-lassi": ("Mango Lassi", (250, 190, 60), (255, 240, 200)),
}

END = date(2026, 11, 15)  # last day of sales data (insights anchor to max date, so demos stay stable)
WEEKS = 8

# Exact weekly totals, oldest → newest week. Chosen so the picks are unambiguous.
WEEKLY = {
    "Butter Chicken": [104, 108, 101, 110, 106, 109, 107, 112],
    "Chicken Biryani": [40, 42, 45, 47, 50, 54, 63, 83],  # +32% WoW in the last week
    "Chicken Tikka Masala": [70, 72, 69, 73, 71, 70, 74, 72],
    "Garlic Naan": [92, 95, 90, 94, 93, 91, 95, 94],
    "Butter Naan": [70, 72, 68, 71, 73, 70, 72, 71],
    "Tandoori Chicken": [44, 46, 43, 45, 47, 44, 46, 45],
    "Vegetable Samosa": [60, 58, 62, 61, 59, 60, 62, 61],
    "Mango Lassi": [55, 57, 54, 56, 58, 55, 57, 58],
    "Palak Paneer": [30, 31, 29, 32, 30, 31, 30, 31],
    "Lamb Rogan Josh": [25, 24, 26, 25, 24, 26, 25, 26],
    "Goat Biryani": [18, 19, 17, 18, 19, 18, 19, 18],
    "Chana Masala": [22, 21, 23, 22, 21, 22, 23, 22],
    "Dal Makhani": [28, 27, 29, 28, 27, 28, 29, 28],
    "Chicken 65": [33, 34, 32, 33, 35, 33, 34, 34],
    "Onion Bhaji": [20, 21, 19, 20, 21, 20, 19, 20],
    "Masala Chai": [40, 41, 39, 42, 40, 41, 40, 41],
    "Gulab Jamun": [26, 25, 27, 26, 25, 26, 27, 26],
    "Malai Kofta": [8, 7, 8, 6, 7, 6, 5, 5],  # slow mover (has a photo)
    "Tandoori Roti": [35, 36, 34, 35, 36, 35, 34, 35],
}
PRICES = {
    "Butter Chicken": 15.99, "Chicken Biryani": 14.99, "Chicken Tikka Masala": 15.49, "Garlic Naan": 3.49,
    "Butter Naan": 2.99, "Tandoori Chicken": 14.49, "Vegetable Samosa": 5.99, "Mango Lassi": 4.49,
    "Palak Paneer": 13.49, "Lamb Rogan Josh": 17.99, "Goat Biryani": 16.99, "Chana Masala": 11.99,
    "Dal Makhani": 12.49, "Chicken 65": 9.99, "Onion Bhaji": 5.49, "Masala Chai": 2.99, "Gulab Jamun": 4.99,
    "Malai Kofta": 13.99, "Tandoori Roti": 2.49,
}
# How the POS spells some items (exercises normalized + fuzzy matching).
POS_NAMES = {"Garlic Naan": ["Garlic Naan", "Garlic Naan (LG)"], "Chicken Biryani": ["Chicken Biryani", "Chicken Biriyani"],
             "Vegetable Samosa": ["Veg Samosa", "Vegetable Samosa"]}
DAY_WEIGHTS = [0.11, 0.11, 0.12, 0.14, 0.18, 0.19, 0.15]  # Mon..Sun


def split_week(total: int, rng: random.Random) -> list[int]:
    raw = [w * total for w in DAY_WEIGHTS]
    out = [int(x) for x in raw]
    rem = total - sum(out)
    order = sorted(range(7), key=lambda i: -(raw[i] - out[i]))
    for i in order[:rem]:
        out[i] += 1
    return out


def build_sales() -> Path:
    rng = random.Random(42)
    start = END - timedelta(days=WEEKS * 7 - 1)
    rows = []
    for item, weeks in WEEKLY.items():
        for w, total in enumerate(weeks):
            days = split_week(total, rng)
            for d, qty in enumerate(days):
                day = start + timedelta(days=w * 7 + d)
                if qty <= 0:
                    continue
                names = POS_NAMES.get(item, [item])
                name = names[(w + d) % len(names)]
                rows.append([day.isoformat(), name, qty, f"{qty * PRICES[item]:.2f}"])
    # Realistic noise: refunds, a gift card (unmatched), a blank row.
    rows.append([(END - timedelta(days=3)).isoformat(), "Butter Chicken", -1, "-15.99"])
    rows.append([(END - timedelta(days=10)).isoformat(), "Gift Card", 2, "50.00"])
    rows.append(["", "", "", ""])
    rows.sort(key=lambda r: (r[0], str(r[1])))
    out = SEED / "kumars_sales_8w.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "item_name", "quantity", "revenue"])
        w.writerows(rows)
    return out


# ------------------------------------------------------------------ music

def build_music(path: Path, seconds: float = 32.0, sr: int = 44100) -> None:
    """Warm lo-fi loop: pad chords + plucked arpeggio + soft kick, 96 BPM."""
    bpm = 96
    beat = 60 / bpm
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]  # Am F C G
    n = int(seconds * sr)
    data = bytearray()

    def f(m: int) -> float:
        return 440 * 2 ** ((m - 69) / 12)

    for i in range(n):
        t = i / sr
        bar = int(t / (beat * 4)) % 4
        ch = chords[bar]
        tb = t % beat
        step = int(t / (beat / 2)) % 6
        pad = sum(math.sin(2 * math.pi * f(m - 12) * t) for m in ch) * 0.06
        note = ch[step % 3] + (12 if step >= 3 else 0)
        tp = t % (beat / 2)
        pluck = math.sin(2 * math.pi * f(note) * t) * math.exp(-tp * 9) * 0.16
        kick = math.sin(2 * math.pi * (50 + 60 * math.exp(-tb * 30)) * tb) * math.exp(-tb * 12) * 0.35 if int(t / beat) % 2 == 0 else 0
        hat = (random.random() * 2 - 1) * math.exp(-((t + beat / 2) % beat) * 60) * 0.03
        fade = min(1.0, t / 1.0, (seconds - t) / 1.0)
        s = max(-1.0, min(1.0, (pad + pluck + kick + hat) * fade))
        v = int(s * 32000)
        data += struct.pack("<hh", v, v)
    wav = path.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(data))
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav), "-b:a", "160k", str(path)], check=True)
    wav.unlink()


# ------------------------------------------------------------------ placeholders

def placeholder_photo(path: Path, title: str, base: tuple, accent: tuple) -> None:
    from PIL import Image, ImageDraw, ImageFilter

    rng = random.Random(title)
    W, H = 1200, 1500
    img = Image.new("RGB", (W, H), (38, 30, 24))
    d = ImageDraw.Draw(img)
    for y in range(H):  # wooden-table gradient
        c = 30 + int(18 * math.sin(y / 37) + 10 * (y / H))
        d.line([(0, y), (W, y)], fill=(c + 18, c + 8, c))
    cx, cy, r = W // 2, H // 2 + 40, 470
    d.ellipse((cx - r - 20, cy - r + 10, cx + r + 20, cy + r + 50), fill=(20, 16, 12))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(236, 232, 224))
    d.ellipse((cx - r + 70, cy - r + 70, cx + r - 70, cy + r - 70), fill=base)
    for _ in range(170):
        a = rng.random() * 2 * math.pi
        rr = rng.random() * (r - 110)
        x, y = cx + math.cos(a) * rr, cy + math.sin(a) * rr
        s = rng.randint(8, 26)
        col = tuple(min(255, max(0, c + rng.randint(-25, 25))) for c in (accent if rng.random() < 0.5 else base))
        d.ellipse((x - s, y - s * 0.6, x + s, y + s * 0.6), fill=col)
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 90), fill=(0, 0, 0))
    d.text((24, 28), f"PLACEHOLDER · replace with a real photo of {title}", fill=(255, 210, 120))
    img.save(path, quality=90)


def placeholder_logo(path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    fonts = SEED.parent / "backend" / "assets" / "fonts"
    img = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((20, 20, 580, 580), fill=(196, 154, 74, 255))
    d.ellipse((50, 50, 550, 550), outline=(24, 38, 29, 255), width=10)
    try:
        f = ImageFont.truetype(str(fonts / "Oswald.ttf"), 330)
        f.set_variation_by_name("Bold")
    except Exception:  # noqa: BLE001
        f = ImageFont.load_default()
    bbox = d.textbbox((0, 0), "K", font=f)
    d.text(((600 - (bbox[2] - bbox[0])) // 2 - bbox[0], (600 - (bbox[3] - bbox[1])) // 2 - bbox[1]), "K", font=f,
           fill=(24, 38, 29, 255))
    img.save(path)


def main() -> None:
    PHOTOS.mkdir(exist_ok=True)
    print("sales →", build_sales())
    music = SEED / "music_upbeat.mp3"
    if not music.exists():
        build_music(music)
        print("music →", music)
    logo = SEED / "logo.png"
    if not logo.exists():
        placeholder_logo(logo)
        print("logo (placeholder) →", logo)
    for slug, (title, base, accent) in PHOTO_DISHES.items():
        existing = [p for p in PHOTOS.glob(f"{slug}.*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        if not existing:
            placeholder_photo(PHOTOS / f"{slug}.jpg", title, base, accent)
            print("photo (placeholder) →", slug)


if __name__ == "__main__":
    main()
