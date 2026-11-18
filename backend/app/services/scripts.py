"""Grounded script generation: Gemini → post-validate → repair → template fallback."""
from __future__ import annotations

import logging
import re
import textwrap
from typing import Optional

from ..util import fmt_price, normalize_name
from . import gemini
from .gemini import END_CARD_S, vo_words

log = logging.getLogger("app.scripts")

PRICE_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)")
CLAIM_RE = re.compile(
    r"(\d+\s?%|\$?\d+\s?(?:%\s?)?off\b|\boff (?:your|the|any|all)\b|discount|\bdeals?\b|award|best in|#1\b|number one|gluten|vegan|allergen|healthy|organic|keto|dairy[- ]free|half price|free\b(?! from))",
    re.I,
)
MAX_LINE = 22


def menu_row_for(item) -> dict:
    return {
        "name": item.name,
        "price": fmt_price(item.price_cents),
        "description": item.description or None,
    }


def wrap_caption(text: str, max_line: int = MAX_LINE) -> str:
    """≤2 lines of ≤max_line chars (longer is allowed only if a single word is longer)."""
    text = " ".join(text.replace("\\n", " ").replace("\n", " ").split())
    lines = textwrap.wrap(text, max_line, break_long_words=False)
    if len(lines) <= 2:
        return "\n".join(lines)
    # Too long: keep two lines, dropping trailing words.
    out = lines[:2]
    out[1] = out[1].rstrip(",.;:") + "…" if len(out[1]) < max_line else out[1]
    return "\n".join(out)


def _all_text(script: dict) -> str:
    parts = [script.get("hook", ""), script.get("voiceover", ""), script.get("title", ""), script.get("description", "")]
    parts += [b.get("caption", "") for b in script.get("beats", [])]
    return "\n".join(str(p) for p in parts)


def spoken_text(script: dict) -> str:
    """What the viewer sees/hears: hook, captions, voiceover."""
    parts = [script.get("hook", ""), script.get("voiceover", "")]
    parts += [b.get("caption", "") for b in script.get("beats", [])]
    return "\n".join(str(p) for p in parts)


def find_invented_claims(text: str, menu_description: Optional[str]) -> list[str]:
    desc = (menu_description or "").lower()
    hits = []
    for m in CLAIM_RE.finditer(text):
        word = m.group(0).lower().strip()
        if word and word not in desc:
            hits.append(word)
    return hits


def validate_script(script: dict, menu_row: dict, length_s: int, *, not_on_menu: bool = False) -> list[str]:
    """Return a list of problems (empty = valid)."""
    problems: list[str] = []
    for key in ("hook", "beats", "voiceover", "title"):
        if not script.get(key):
            problems.append(f"missing {key}")
    if problems:
        return problems

    text = _all_text(script)
    seen_text = spoken_text(script)
    price = menu_row.get("price")
    amounts = PRICE_RE.findall(text)
    if price is None or not_on_menu:
        if amounts:
            problems.append("mentions a price but the menu has none; remove every dollar amount")
    else:
        want = float(price.replace("$", ""))
        for a in amounts:
            if abs(float(a) - want) > 0.001:
                problems.append(f"price ${a} does not match the menu price {price}")
    if not not_on_menu:
        name_norm = normalize_name(menu_row["name"])
        if name_norm and name_norm not in normalize_name(seen_text):
            problems.append(f"the dish name '{menu_row['name']}' must appear in the captions or voiceover")
    claims = find_invented_claims(seen_text + "\n" + str(script.get("description", "")), menu_row.get("description"))
    if claims:
        problems.append(f"invented claims not in the menu: {', '.join(sorted(set(claims)))}")
    words = len(str(script.get("voiceover", "")).split())
    max_words = vo_words(length_s)
    if words > max_words + (3 if length_s <= 8 else 6):
        problems.append(f"voiceover is {words} words; keep it under {max_words}")
    if len(script.get("hook", "").split()) > 10:
        problems.append("hook must be 8 words or fewer")
    return problems


def normalize_script(script: dict, length_s: int) -> dict:
    """Coerce shapes, wrap captions, fix timing, cap hashtags. Doesn't change meaning."""
    main_len = length_s - END_CARD_S
    beats = []
    for b in script.get("beats") or []:
        if not isinstance(b, dict) or not str(b.get("caption", "")).strip():
            continue
        try:
            sec = float(b.get("seconds") or 0)
        except (TypeError, ValueError):
            sec = 0
        beats.append({"caption": wrap_caption(str(b["caption"])), "seconds": max(sec, 0.8)})
    if not beats:
        beats = [{"caption": wrap_caption(script.get("hook", "")), "seconds": main_len}]
    total = sum(b["seconds"] for b in beats)
    if abs(total - main_len) > 1.0 or total <= 0:
        scale = main_len / total if total > 0 else 1
        for b in beats:
            b["seconds"] = round(b["seconds"] * scale, 2)
    tags = []
    for t in script.get("hashtags") or []:
        t = "#" + re.sub(r"[^A-Za-z0-9_]", "", str(t).lstrip("#"))
        if len(t) > 1 and t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    facts = [
        {"field": f.get("field"), "value": str(f.get("value", ""))}
        for f in (script.get("facts_used") or [])
        if isinstance(f, dict) and f.get("field") in ("name", "price", "description")
    ]
    return {
        "hook": " ".join(str(script.get("hook", "")).split())[:80],
        "beats": beats,
        "voiceover": " ".join(str(script.get("voiceover", "")).split()),
        "veo_prompt": str(script.get("veo_prompt") or default_veo_prompt()),
        "title": str(script.get("title", ""))[:70],
        "description": str(script.get("description", ""))[:900],
        "hashtags": tags[:5],
        "facts_used": facts,
    }


def default_veo_prompt(visual_notes: str = "") -> str:
    base = (
        "Photorealistic commercial food cinematography of this exact dish in a busy, warm restaurant kitchen: "
        "real motion and action such as steam billowing, sauce or garnish being spooned on by a chef's hands, oil sizzling, "
        "a serving spoon lifting a portion, then a smooth cinematic push-in. Shallow depth of field, golden lighting. "
        "Keep the dish recognisably the same. No faces, no text, no logos."
    )
    return base + (f" Details: {visual_notes}" if visual_notes else "")


def _beat_facts(caption: str, menu_row: dict) -> list[str]:
    out = []
    c = normalize_name(caption)
    if menu_row.get("name") and normalize_name(menu_row["name"]) in c:
        out.append("name")
    if menu_row.get("price") and menu_row["price"].replace("$", "") in caption:
        out.append("price")
    desc = normalize_name(menu_row.get("description") or "")
    if desc:
        dwords = {w for w in desc.split() if len(w) > 3}
        if dwords & set(c.split()):
            out.append("description")
    return out


def annotate_beats(script: dict, menu_row: dict) -> dict:
    for b in script["beats"]:
        b["facts"] = _beat_facts(b["caption"], menu_row)
    return script


ANGLE_HOOKS = {
    "top_seller": "Everyone's ordering this",
    "rising": "People keep coming back for this",
    "slow_mover": "The underrated favorite",
    None: "You need to try this",
}


def template_script(menu_row: dict, angle: Optional[str], restaurant_name: str, length_s: int = 15,
                    *, not_on_menu: bool = False, visual_notes: str = "") -> dict:
    name = menu_row.get("name") or "our special"
    price = None if not_on_menu else menu_row.get("price")
    desc = (menu_row.get("description") or "").rstrip(".")
    hook = ANGLE_HOOKS.get(angle, ANGLE_HOOKS[None])
    main_len = length_s - END_CARD_S
    short_video = length_s <= 8
    beats = [hook, name if not not_on_menu else "Fresh from our kitchen"]
    if desc and not short_video:
        short = desc if len(desc) <= 44 else desc[:41].rsplit(" ", 1)[0] + "…"
        beats.append(short)
    beats.append(f"Only {price}" if price else f"At {restaurant_name}")
    per = round(main_len / len(beats), 2)
    vo_parts = [f"{hook}."]
    if not not_on_menu:
        vo_parts.append(f"The {name} at {restaurant_name}.")
    else:
        vo_parts.append(f"Fresh from the kitchen at {restaurant_name}.")
    if desc and not short_video:
        vo_parts.append(desc + ".")
    if price:
        vo_parts.append(f"Just {price}.")
    if not short_video:
        vo_parts.append("Come try it today.")
    voiceover = " ".join(vo_parts)
    words = voiceover.split()
    if len(words) > vo_words(length_s) + 2:
        voiceover = " ".join(words[: vo_words(length_s) + 2]).rstrip(",.") + "."
    facts = [{"field": "name", "value": name}] if not not_on_menu else []
    if desc:
        facts.append({"field": "description", "value": desc})
    if price:
        facts.append({"field": "price", "value": price})
    def _tag(s: str) -> str:
        return "#" + re.sub(r"[^A-Za-z0-9]", "", re.sub(r"['’]", "", s).title())[:30]

    tag, rest_tag = _tag(name), _tag(restaurant_name)
    script = {
        "hook": hook,
        "beats": [{"caption": wrap_caption(b), "seconds": per} for b in beats],
        "voiceover": voiceover,
        "veo_prompt": default_veo_prompt(visual_notes),
        "title": f"{name} at {restaurant_name}"[:70],
        "description": f"{name} at {restaurant_name}." + (f" {desc}." if desc else ""),
        "hashtags": [t for t in [tag, rest_tag, "#food", "#foodie"] if len(t) > 1][:5],
        "facts_used": facts,
    }
    return annotate_beats(script, menu_row)


async def write_script(
    *,
    menu_row: dict,
    restaurant_name: str,
    angle: Optional[str],
    tone: str,
    style: str,
    length_s: int,
    visual_notes: str,
    angle_metric: Optional[str] = None,
    not_on_menu: bool = False,
    use_cache: bool = True,
) -> tuple[dict, str, Optional[str]]:
    """Returns (script, source, note). source ∈ gemini|gemini_repaired|template.

    Successful AI scripts are cached per (menu row, angle, tone, style, length, visual notes), so retries and
    rehearsals don't burn free-tier quota. Pass use_cache=False to force a fresh draft.
    """
    key = gemini.cache_key("script", menu_row, restaurant_name, angle, tone, style, length_s, visual_notes, angle_metric, not_on_menu)
    if use_cache:
        hit = gemini.cache_get(key)
        if hit is not None:
            return hit["script"], hit["source"], None
    script, source, note = await _write_script(
        menu_row=menu_row, restaurant_name=restaurant_name, angle=angle, tone=tone, style=style, length_s=length_s,
        visual_notes=visual_notes, angle_metric=angle_metric, not_on_menu=not_on_menu,
    )
    if source != "template":
        gemini.cache_put(key, {"script": script, "source": source})
    return script, source, note


async def _write_script(
    *,
    menu_row: dict,
    restaurant_name: str,
    angle: Optional[str],
    tone: str,
    style: str,
    length_s: int,
    visual_notes: str,
    angle_metric: Optional[str] = None,
    not_on_menu: bool = False,
) -> tuple[dict, str, Optional[str]]:
    row = dict(menu_row)
    if not_on_menu:
        row = {"name": None, "price": None, "description": None}
    system, prompt = gemini.build_script_prompt(
        menu_row=row,
        restaurant_name=restaurant_name,
        angle=angle,
        tone=tone,
        style=style,
        length_s=length_s,
        visual_notes=visual_notes,
        angle_metric=angle_metric,
    )
    note = None
    try:
        raw = await gemini.write_script_raw(system, prompt)
        script = normalize_script(raw, length_s)
        problems = validate_script(script, menu_row, length_s, not_on_menu=not_on_menu)
        if not problems:
            return annotate_beats(script, menu_row), "gemini", None
        log.info("script failed validation: %s → repair", problems)
        raw = await gemini.write_script_raw(system, prompt, repair_note="; ".join(problems))
        script = normalize_script(raw, length_s)
        problems = validate_script(script, menu_row, length_s, not_on_menu=not_on_menu)
        if not problems:
            return annotate_beats(script, menu_row), "gemini_repaired", None
        note = "Template script (AI draft broke a grounding rule)"
        log.warning("repair still invalid: %s → template", problems)
    except gemini.GeminiError as e:
        note = {
            "unavailable": "Template script (AI not configured)",
            "rate_limit": "Template script (AI rate limit)",
            "timeout": "Template script (AI timed out)",
            "blocked": "Template script (AI declined)",
        }.get(e.kind, "Template script (AI error)")
        log.warning("script gemini error %s → template", e.kind)
    return (
        template_script(menu_row, angle, restaurant_name, length_s, not_on_menu=not_on_menu, visual_notes=visual_notes),
        "template",
        note,
    )
