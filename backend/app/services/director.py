"""Director mode: plan the Short as a storyboard, refine it in a chat, preview a frame, then render.

Everything the user sees is cheap (text from Gemini Flash, one preview image a few cents). The expensive AI video
runs only when they press Action!. Every storyboard goes through the same grounding validator as normal scripts,
so a chat request can't make the narrator invent a price, a deal or a claim.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from ..config import get_settings
from . import formats, gemini, scripts
from .gemini import GeminiError

log = logging.getLogger(__name__)

LENGTH_S = 8

DIRECTOR_SCHEMA = {
    "type": "object",
    "properties": {
        **gemini.SCRIPT_SCHEMA["properties"],
        "shot": {"type": "string"},
        "reply": {"type": "string"},
        "suggestions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [*gemini.SCRIPT_SCHEMA["required"], "shot", "reply", "suggestions"],
}

SYSTEM = (
    "You are the creative director of a restaurant's 8-second vertical YouTube Short. You plan the video as a "
    "storyboard and refine it with the owner in a chat. Make it look delicious and feel on-brand.\n"
    + gemini.SCRIPT_RULES
    + """7. If the owner asks for something that breaks a HARD RULE (a discount, an award, a price change, a health claim,
   a famous or copyrighted character, a real person), keep the storyboard compliant and say briefly in `reply` why you
   left it out, then offer an alternative.
8. The video model animates the dish photo: keep `veo_prompt` to camera moves and real food action around this exact
   dish. No text, no logos, no faces.
9. You can ONLY change: the hook, the captions, the narration words, the camera shot / food action, the YouTube title,
   description and hashtags. You can NOT change music, sound effects, the narrator's voice, the video length, the
   logo ending, colors or fonts, and you can't add people, mascots or extra on-screen text. If asked, say so plainly
   in `reply` and do what you can with the parts you control. Never claim to have done something outside this list.
10. `suggestions` must only be things you can change (rule 9).
"""
)

STARTER_CHIPS = ["Steamy close-up", "Make it cozy", "More energy", "Mention the price", "Shorter captions"]


def _prompt(*, menu_row: dict, restaurant_name: str, tone: str, visual_notes: str, angle: Optional[str],
            current: Optional[dict], history: list[dict], message: Optional[str], fmt: str = "classic") -> str:
    f = formats.get(fmt)
    convo = "\n".join(f"{h['role'].upper()}: {h['text']}" for h in history[-8:]) or "(none yet)"
    task = (
        f"OWNER'S REQUEST: {message}\nUpdate the storyboard to follow it (keep what they didn't ask to change)."
        if message else "Write the first storyboard."
    )
    return f"""RESTAURANT: {restaurant_name}
MENU_ROW: {json.dumps(menu_row)}
VISUAL_NOTES: {visual_notes or 'n/a'}
ANGLE: {gemini.ANGLE_NOTES.get(angle, gemini.ANGLE_NOTES[None])}
TONE: {gemini.TONES.get(tone, gemini.TONES['upbeat'])}
FORMAT: {f.script_note}
CURRENT_STORYBOARD: {json.dumps(_public(current)) if current else '(none)'}
CONVERSATION SO FAR:
{convo}

{task}

Write JSON:
- hook: scroll-stopping opener, max 6 words.
- beats: 2 short on-screen captions, each max 2 lines of max 22 characters (use \\n), 'seconds' summing to about {LENGTH_S - gemini.END_CARD_S:g}.
- voiceover: {f'spoken script, max {gemini.vo_words(LENGTH_S)} words, mentions the dish name.' if f.narrated else 'an empty string (this format has no narrator; the dish name goes in a caption).'}
- veo_prompt: detailed prompt for the image-to-video model animating this exact photo as {f.veo_note} (no text/logos/faces).
- shot: the same shot in one plain sentence for the owner (e.g. "Slow push-in as cream is spooned over the curry, steam rising").
- title (max 70 chars, includes the dish name), description (1-2 sentences), hashtags (up to 5), facts_used.
- reply: 1-2 friendly sentences to the owner saying what you did (or why you left something out).
- suggestions: 3 short next ideas the owner could tap (max 5 words each).
"""


def _public(sb: Optional[dict]) -> Optional[dict]:
    if not sb:
        return None
    keys = ("hook", "beats", "voiceover", "shot", "veo_prompt", "title", "description", "hashtags")
    return {k: sb.get(k) for k in keys}


def finalize(raw: dict, menu_row: dict, *, narrated: bool = True) -> tuple[dict, list[str]]:
    """Normalize a storyboard (from the model or the browser) and check it against the menu row."""
    sb = scripts.normalize_script(raw, LENGTH_S)
    if not narrated:
        sb["voiceover"] = ""
    sb["shot"] = " ".join(str(raw.get("shot") or "").split())[:240] or "Slow cinematic push-in on the dish."
    problems = scripts.validate_script(sb, menu_row, LENGTH_S, narrated=narrated)
    return scripts.annotate_beats(sb, menu_row), problems


async def plan(*, menu_row: dict, restaurant_name: str, tone: str, visual_notes: str, angle: Optional[str] = None,
               current: Optional[dict] = None, history: Optional[list[dict]] = None,
               message: Optional[str] = None, fmt: str = "classic") -> dict:
    """One director turn. Returns {storyboard, reply, suggestions, source}."""
    history = history or []
    narrated = formats.get(fmt).narrated
    prompt = _prompt(menu_row=menu_row, restaurant_name=restaurant_name, tone=tone, visual_notes=visual_notes,
                     angle=angle, current=current, history=history, message=message, fmt=fmt)
    try:
        raw = await gemini.generate_json(prompt, DIRECTOR_SCHEMA, system=SYSTEM, timeout_s=30, temperature=0.7)
        sb, problems = finalize(raw, menu_row, narrated=narrated)
        if problems:
            log.info("director draft broke rules: %s → repair", problems)
            raw = await gemini.generate_json(
                prompt + f"\n\nYour previous answer broke a rule: {'; '.join(problems)}\nFix it; follow every HARD RULE.",
                DIRECTOR_SCHEMA, system=SYSTEM, timeout_s=30, temperature=0.2)
            sb, problems = finalize(raw, menu_row, narrated=narrated)
        if not problems:
            chips = [str(s)[:40] for s in (raw.get("suggestions") or []) if str(s).strip()][:3]
            return {"storyboard": sb, "reply": str(raw.get("reply") or "Here's the plan.")[:400],
                    "suggestions": chips or STARTER_CHIPS[:3], "source": "gemini"}
        reason = problems[0]
    except GeminiError as e:
        log.info("director call failed (%s)", e.kind)
        reason = None

    # Fall back: keep the current storyboard, or start from the safe template.
    if current:
        sb, problems = finalize(current, menu_row, narrated=narrated)
        if not problems:
            msg = (f"I couldn't make that change and keep the video accurate ({reason}). Try saying it another way."
                   if reason else "The AI director is busy right now. Your storyboard is unchanged; try again in a moment.")
            return {"storyboard": sb, "reply": msg, "suggestions": STARTER_CHIPS[:3], "source": "unchanged"}
    tpl = scripts.template_script(menu_row, angle, restaurant_name, LENGTH_S, fmt=fmt)
    tpl["shot"] = "Slow cinematic push-in on the dish with steam rising."
    sb, _ = finalize(tpl, menu_row, narrated=narrated)
    return {"storyboard": sb, "reply": "Here's a simple starting plan. Tell me what you'd like to change.",
            "suggestions": STARTER_CHIPS[:3], "source": "template"}


async def preview_frame(photo: tuple[bytes, str], storyboard: dict) -> tuple[bytes, str]:
    """A still from the planned shot (the dish photo + the shot), for the owner to judge before rendering."""
    from google.genai import errors as gerrors
    from google.genai import types

    client = gemini._get_client()
    prompt = (
        "Vertical 9:16 photoreal frame from a high-end food commercial, mid-shot of THIS exact dish (keep it "
        f"recognisably the same). Shot: {storyboard.get('shot') or ''} {storyboard.get('veo_prompt') or ''} "
        "Warm golden light, shallow depth of field. No text, no captions, no logos, no faces."
    )
    try:
        resp = await asyncio.wait_for(client.aio.models.generate_content(
            model=get_settings().director_image_model,
            contents=[types.Part.from_bytes(data=photo[0], mime_type=photo[1]), prompt],
            config=types.GenerateContentConfig(response_modalities=["IMAGE"],
                                               image_config=types.ImageConfig(aspect_ratio="9:16")),
        ), timeout=60)
    except asyncio.TimeoutError as e:
        raise GeminiError("timeout", "preview took too long") from e
    except gerrors.APIError as e:
        raise GeminiError("rate_limit" if getattr(e, "code", None) == 429 else "api", str(e)) from e
    for cand in resp.candidates or []:
        for part in (cand.content.parts if cand.content else []) or []:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data, part.inline_data.mime_type or "image/png"
    raise GeminiError("blocked", "no image returned")


def public_storyboard(sb: dict) -> dict[str, Any]:
    return {k: sb.get(k) for k in ("hook", "beats", "voiceover", "shot", "veo_prompt", "title", "description",
                                    "hashtags", "facts_used")}
