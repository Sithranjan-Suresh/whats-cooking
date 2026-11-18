"""Gemini Flash wrapper: analyze_photo, write_script, insight_reasons.

Every public function either returns validated data or raises GeminiError(kind),
where kind is one of: unavailable | timeout | rate_limit | malformed | blocked | api.
Callers decide the fallback (manual picker, template script, rule-based reasons).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from ..config import get_settings

END_CARD_S = 2.8  # keep in sync with render.END_CARD_S

log = logging.getLogger("app.gemini")

_client = None


# ---------------------------------------------------------------- tiny LRU cache (saves free-tier quota on retries/rehearsals)
import hashlib
from collections import OrderedDict

_cache: "OrderedDict[str, Any]" = OrderedDict()
_CACHE_MAX = 256


def cache_key(*parts: Any) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else json.dumps(p, sort_keys=True, default=str).encode())
        h.update(b"|")
    return h.hexdigest()


def cache_get(key: str) -> Any:
    if key in _cache:
        _cache.move_to_end(key)
        return json.loads(json.dumps(_cache[key]))  # defensive copy
    return None


def cache_put(key: str, value: Any) -> None:
    _cache[key] = value
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


def cache_clear() -> None:
    _cache.clear()


class GeminiError(Exception):
    def __init__(self, kind: str, message: str = ""):
        super().__init__(message or kind)
        self.kind = kind


def _get_client():
    global _client
    s = get_settings()
    if not s.gemini_api_key:
        raise GeminiError("unavailable", "GEMINI_API_KEY is not set")
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=s.gemini_api_key)
    return _client


def set_client_for_tests(client) -> None:
    global _client
    _client = client


async def generate_json(
    prompt: str,
    schema: dict,
    *,
    system: Optional[str] = None,
    image: Optional[tuple[bytes, str]] = None,
    timeout_s: float = 25,
    temperature: float = 0.4,
    rate_limit_retries: int = 2,
) -> Any:
    """One structured-output call. Handles timeout and 429 backoff; returns parsed JSON."""
    from google.genai import errors as gerrors
    from google.genai import types

    client = _get_client()
    contents: list[Any] = []
    if image:
        contents.append(types.Part.from_bytes(data=image[0], mime_type=image[1]))
    contents.append(prompt)
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json",
        response_json_schema=schema,
    )
    attempt = 0
    while True:
        try:
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=get_settings().gemini_text_model, contents=contents, config=cfg
                ),
                timeout=timeout_s,
            )
            break
        except asyncio.TimeoutError as e:
            raise GeminiError("timeout", f"Gemini took longer than {timeout_s}s") from e
        except gerrors.APIError as e:
            code = getattr(e, "code", None)
            if code == 429:
                if attempt < rate_limit_retries:
                    attempt += 1
                    await asyncio.sleep(5)
                    continue
                raise GeminiError("rate_limit", "Gemini rate limit") from e
            raise GeminiError("api", f"Gemini API error {code}: {e}") from e
        except GeminiError:
            raise
        except Exception as e:  # network etc.
            raise GeminiError("api", str(e)) from e

    # Safety blocks / empty candidates
    text = None
    try:
        text = resp.text
    except Exception:  # noqa: BLE001
        text = None
    if not text:
        fb = getattr(resp, "prompt_feedback", None)
        if fb is not None and getattr(fb, "block_reason", None):
            raise GeminiError("blocked", f"blocked: {fb.block_reason}")
        raise GeminiError("blocked", "empty response")
    try:
        return json.loads(text)
    except ValueError as e:
        raise GeminiError("malformed", f"not JSON: {text[:200]}") from e


# ---------------------------------------------------------------- analyze

ANALYZE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_food": {"type": "boolean"},
        "dish_guess": {"type": "string"},
        "menu_item_id": {"type": ["integer", "null"]},
        "confidence": {"type": "number"},
        "visual_notes": {"type": "string"},
        "quality": {"type": "string", "enum": ["good", "dark", "blurry"]},
    },
    "required": ["is_food", "dish_guess", "menu_item_id", "confidence", "visual_notes", "quality"],
}

DESCRIBE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_food": {"type": "boolean"},
        "visual_notes": {"type": "string"},
        "quality": {"type": "string", "enum": ["good", "dark", "blurry"]},
    },
    "required": ["is_food", "visual_notes", "quality"],
}


def _validate_analyze(d: Any, menu_ids: set[int]) -> dict:
    if not isinstance(d, dict):
        raise GeminiError("malformed", "analyze: not an object")
    out = {
        "is_food": bool(d.get("is_food", True)),
        "dish_guess": str(d.get("dish_guess") or "")[:120],
        "menu_item_id": d.get("menu_item_id"),
        "confidence": float(d.get("confidence") or 0),
        "visual_notes": str(d.get("visual_notes") or "")[:400],
        "quality": d.get("quality") if d.get("quality") in ("good", "dark", "blurry") else "good",
    }
    if out["menu_item_id"] is not None:
        try:
            out["menu_item_id"] = int(out["menu_item_id"])
        except (TypeError, ValueError):
            out["menu_item_id"] = None
    if out["menu_item_id"] not in menu_ids:
        out["menu_item_id"] = None
    out["confidence"] = max(0.0, min(1.0, out["confidence"]))
    return out


async def analyze_photo(image: tuple[bytes, str], menu: list[dict]) -> dict:
    """menu: [{id, name, price, description}] (max 150 used)."""
    menu = menu[:150]
    key = cache_key("analyze", get_settings().gemini_text_model, image[0], menu)
    hit = cache_get(key)
    if hit is not None:
        return hit
    out = await _analyze_photo(image, menu)
    cache_put(key, out)
    return out


async def _analyze_photo(image: tuple[bytes, str], menu: list[dict]) -> dict:
    lines = "\n".join(
        f"- id={m['id']} | {m['name']} | {m.get('price') or 'no price'} | {(m.get('description') or '')[:120]}"
        for m in menu
    )
    prompt = (
        "You are matching a restaurant dish photo to the restaurant's menu.\n"
        f"MENU:\n{lines}\n\n"
        "Return JSON: is_food (is this a photo of prepared food?), dish_guess (what dish it looks like), "
        "menu_item_id (id of the best matching MENU item, or null if none fits), confidence 0-1 for that match, "
        "visual_notes (one sentence describing what is visible: colors, garnish, steam, plating, vessel), "
        "quality (good, dark or blurry)."
    )
    ids = {int(m["id"]) for m in menu}
    try:
        raw = await generate_json(prompt, ANALYZE_SCHEMA, image=image, timeout_s=20, temperature=0.1)
        return _validate_analyze(raw, ids)
    except GeminiError as e:
        if e.kind == "timeout":
            raw = await generate_json(prompt, ANALYZE_SCHEMA, image=image, timeout_s=20, temperature=0.1)
            return _validate_analyze(raw, ids)
        if e.kind == "malformed":
            raw = await generate_json(
                prompt + "\nReturn ONLY valid JSON matching the schema.",
                ANALYZE_SCHEMA,
                image=image,
                timeout_s=20,
                temperature=0.0,
            )
            return _validate_analyze(raw, ids)
        raise


async def describe_photo(image: tuple[bytes, str], dish_name: str) -> dict:
    key = cache_key("describe", get_settings().gemini_text_model, image[0], dish_name)
    hit = cache_get(key)
    if hit is not None:
        return hit
    out = await _describe_photo(image, dish_name)
    cache_put(key, out)
    return out


async def _describe_photo(image: tuple[bytes, str], dish_name: str) -> dict:
    prompt = (
        f"This is a photo of '{dish_name}' from a restaurant. Return JSON: is_food, visual_notes "
        "(one sentence: colors, garnish, steam, plating, vessel), quality (good, dark or blurry)."
    )
    raw = await generate_json(prompt, DESCRIBE_SCHEMA, image=image, timeout_s=20, temperature=0.1)
    if not isinstance(raw, dict):
        raise GeminiError("malformed", "describe: not an object")
    return {
        "is_food": bool(raw.get("is_food", True)),
        "visual_notes": str(raw.get("visual_notes") or "")[:400],
        "quality": raw.get("quality") if raw.get("quality") in ("good", "dark", "blurry") else "good",
    }


# ---------------------------------------------------------------- insight reasons

REASONS_SCHEMA = {
    "type": "object",
    "properties": {
        "reasons": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"angle": {"type": "string"}, "reason": {"type": "string"}},
                "required": ["angle", "reason"],
            },
        }
    },
    "required": ["reasons"],
}


async def insight_reasons(restaurant_name: str, picks: list[dict]) -> dict[str, str]:
    """picks: [{angle, dish, metrics:{...}}] → {angle: reason}."""
    prompt = (
        f"You advise {restaurant_name}, a restaurant, on which dish to promote in a short video.\n"
        "For each pick below, write ONE plain-English sentence (max 22 words) explaining why to promote it. "
        "Use only the numbers given. Do not invent numbers, prices, awards or claims.\n\n"
        + json.dumps(picks, indent=1)
    )
    raw = await generate_json(prompt, REASONS_SCHEMA, timeout_s=20, temperature=0.5)
    out: dict[str, str] = {}
    for r in (raw or {}).get("reasons", []):
        if isinstance(r, dict) and r.get("angle") and r.get("reason"):
            out[str(r["angle"])] = str(r["reason"]).strip()[:220]
    return out


# ---------------------------------------------------------------- script

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "hook": {"type": "string"},
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"caption": {"type": "string"}, "seconds": {"type": "number"}},
                "required": ["caption", "seconds"],
            },
        },
        "voiceover": {"type": "string"},
        "veo_prompt": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "facts_used": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": ["name", "price", "description"]},
                    "value": {"type": "string"},
                },
                "required": ["field", "value"],
            },
        },
    },
    "required": ["hook", "beats", "voiceover", "veo_prompt", "title", "description", "hashtags", "facts_used"],
}

TONES = {
    "friendly": "warm, welcoming, neighborly",
    "upbeat": "energetic, punchy, fun",
    "elegant": "refined, calm, appetizing",
}

STYLE_NOTES = {
    "bold": "short punchy captions, fast pacing",
    "warm": "soft cozy captions, slower pacing",
    "minimal": "very short understated captions",
}

ANGLE_NOTES = {
    "top_seller": "This is the restaurant's best seller right now: lean on 'everyone is ordering it'.",
    "rising": "Orders for this dish are climbing fast: lean on 'people keep coming back for it'.",
    "slow_mover": "This dish is under-ordered: lean on 'an underrated favorite you should try'.",
    None: "Introduce the dish and make it look irresistible.",
}

SCRIPT_RULES = """HARD RULES (never break these):
1. Only mention the dish name, price and description from MENU_ROW. Use the dish name exactly as written.
2. Never invent discounts, deals, percentages off, awards, rankings ("best in town"), health, diet or allergen claims (gluten-free, vegan, healthy...), or prices.
3. If MENU_ROW.price is null, do not mention any price or dollar amount anywhere.
4. If you mention the price, write it exactly as MENU_ROW.price (e.g. $14.99).
5. Do not mention ingredients that are not in MENU_ROW.description or visible in VISUAL_NOTES.
6. List every menu fact you used in facts_used.
"""


def build_script_prompt(
    *,
    menu_row: dict,
    restaurant_name: str,
    angle: Optional[str],
    tone: str,
    style: str,
    length_s: int,
    visual_notes: str,
    angle_metric: Optional[str] = None,
) -> tuple[str, str]:
    words = 38 if length_s <= 15 else 75
    n_beats = "3-4" if length_s <= 15 else "5-6"
    main_len = length_s - END_CARD_S
    system = (
        "You write scripts for vertical YouTube Shorts promoting a single restaurant dish.\n" + SCRIPT_RULES
    )
    prompt = f"""RESTAURANT: {restaurant_name}
MENU_ROW: {json.dumps(menu_row)}
VISUAL_NOTES: {visual_notes or 'n/a'}
ANGLE: {ANGLE_NOTES.get(angle, ANGLE_NOTES[None])}{(' Real sales fact you may use: ' + angle_metric) if angle_metric else ''}
TONE: {TONES.get(tone, TONES['upbeat'])}
STYLE: {STYLE_NOTES.get(style, STYLE_NOTES['bold'])}
LENGTH: {length_s} seconds total (the last {END_CARD_S:g}s is an animated logo end card).

Write JSON:
- hook: scroll-stopping opener, max 8 words.
- beats: {n_beats} on-screen captions. Each caption max 2 lines of max 22 characters per line (use \\n for the line break). 'seconds' per beat must sum to about {main_len:g}.
- voiceover: spoken script, max {words} words, natural to read aloud, mentions the dish name.
- veo_prompt: a prompt for an image-to-video model animating this exact photo like a high-end food commercial: real action fitting this dish (e.g. chef's hands spooning sauce or garnish, sizzle, steam billowing, a spoon lifting a portion) plus a smooth cinematic push-in. No faces, no text, no logos; keep the dish recognisable.
- title: YouTube title, max 70 characters, includes the dish name.
- description: 1-2 sentences for the YouTube description, follows the hard rules.
- hashtags: up to 5, each starting with #, no spaces.
- facts_used: every MENU_ROW field you used, with the value you used.
"""
    return system, prompt


async def write_script_raw(system: str, prompt: str, *, repair_note: Optional[str] = None) -> dict:
    p = prompt
    if repair_note:
        p += f"\n\nYour previous answer broke a rule: {repair_note}\nFix it and follow every HARD RULE exactly."
    raw = await generate_json(p, SCRIPT_SCHEMA, system=system, timeout_s=25, temperature=0.6 if not repair_note else 0.2)
    if not isinstance(raw, dict):
        raise GeminiError("malformed", "script: not an object")
    return raw


async def baseline_script(image: tuple[bytes, str]) -> dict:
    """Ungrounded baseline for the eval: photo only, no menu, no rules."""
    schema = {
        "type": "object",
        "properties": {
            "hook": {"type": "string"},
            "captions": {"type": "array", "items": {"type": "string"}},
            "voiceover": {"type": "string"},
        },
        "required": ["hook", "captions", "voiceover"],
    }
    return await generate_json(
        "Write a short promo script for this dish (hook, 3-4 captions, voiceover).",
        schema,
        image=image,
        timeout_s=30,
        temperature=0.6,
    )


async def judge_claims(text: str, menu_row: dict) -> bool:
    """LLM judge: True if the text makes NO claims beyond the menu row."""
    schema = {
        "type": "object",
        "properties": {"invented": {"type": "boolean"}, "why": {"type": "string"}},
        "required": ["invented", "why"],
    }
    raw = await generate_json(
        "MENU_ROW: " + json.dumps(menu_row) + "\n\nPROMO TEXT:\n" + text + "\n\n"
        "Does the promo text state any factual claim NOT supported by MENU_ROW? Count: invented prices, "
        "discounts, awards/rankings, health/diet/allergen claims, ingredients not in the description, "
        "a different dish name. Vague appetizing adjectives (delicious, fragrant) do NOT count. "
        "Return invented=true/false and a short why.",
        schema,
        timeout_s=20,
        temperature=0.0,
    )
    return not bool((raw or {}).get("invented", False))
