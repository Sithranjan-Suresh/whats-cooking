"""Small shared helpers."""
import hashlib
import re
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

ABBREVIATIONS = {"veg": "vegetable", "chkn": "chicken", "ckn": "chicken", "chix": "chicken",
                 "bir": "biryani", "biriyani": "biryani", "briyani": "biryani", "pnr": "paneer"}
SIZE_WORDS = {"lg", "large", "sm", "small", "md", "medium", "regular", "reg", "half", "full", "xl"}


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation and size words, collapse whitespace."""
    s = (name or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\([^)]*\)", " ", s)  # drop parentheticals like "(lg)"
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    words = [ABBREVIATIONS.get(w, w) for w in s.split() if w not in SIZE_WORDS]
    return " ".join(words)


def parse_price_cents(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    s = str(raw).strip().replace("$", "").replace(",", "")
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if v < 0:
        return None
    return int(round(v * 100))


def fmt_price(cents: Optional[int]) -> Optional[str]:
    if cents is None:
        return None
    return f"${cents / 100:.2f}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "restaurant"


# ---------- Fernet ----------

def _fernet() -> Fernet:
    key = get_settings().app_secret
    if not key:
        raise RuntimeError("APP_SECRET is not set (generate one with `make secret`).")
    return Fernet(key.encode())


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError("Could not decrypt stored token (APP_SECRET changed?)") from e
