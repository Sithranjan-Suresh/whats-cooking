"""Video formats. 'classic' is the original narrated ad; the others follow what tends to work in short-form food
video: the payoff in the first second, real food sound instead of a narrator, native-looking captions, and no
logo slate, so the Short loops (see docs/AUDIT.md and the research notes in the commit history)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Format:
    key: str
    narrated: bool        # a TTS narrator reads the voiceover
    overlay_end: bool     # True: corner logo + name at the end, loops; False: animated logo slate
    caption_style: str    # render.STYLE_PRESETS key
    script_note: str      # how Gemini should write hook/captions for this format
    veo_note: str         # how the AI motion should look and sound


FORMATS: dict[str, Format] = {
    "classic": Format(
        "classic", True, False, "bold",
        "Classic promo: a punchy hook, short captions and a narrator.",
        "a high-end food commercial: real action fitting this dish (sauce or garnish spooned on, sizzle, steam, a "
        "spoon lifting a portion) plus a smooth cinematic push-in",
    ),
    "money_shot": Format(
        "money_shot", False, True, "native",
        "MONEY SHOT: no narrator, the food sound does the talking. Captions read like a person posting, not an ad: "
        "lowercase, casual, max 5 words each (e.g. 'wait for the pour', 'butter chicken @ kumar's'). The hook is a "
        "tiny teaser shown in the first second (max 4 words, lowercase). Do not put the price in the captions.",
        "an extreme macro close-up that STARTS ALREADY MID-ACTION at the most satisfying moment for this dish (a thick "
        "sauce pour, a cheese pull, bread tearing and dipping, a crispy bite, a glossy drizzle), slow-motion feel, "
        "steam, and loud, crisp, appetizing sound: sizzle, crunch, bubbling, pouring. No music. The last moment "
        "should look close to the first so the clip loops",
    ),
    "chef_pov": Format(
        "chef_pov", False, True, "native",
        "CHEF POV: no narrator. The hook is the only line that starts with 'pov:' (e.g. 'pov: plating your "
        "butter chicken'). The captions are short, lowercase, first-person asides from the cook, max 5 words, no "
        "'pov:' (e.g. 'extra sauce, always', 'butter chicken @ kumar's'). Do not put the price in the captions.",
        "a first-person POV from the cook at the pass: their hands finishing this exact dish (garnishing, saucing, "
        "wiping the rim, sliding the plate toward the camera), handheld natural camera, starts already mid-action, "
        "real busy-kitchen sound (sizzle, clatter, a ticket printer). Hands only, no faces, no music",
    ),
}

DEFAULT = "classic"


def get(key: Optional[str]) -> Format:
    return FORMATS.get(key or DEFAULT, FORMATS[DEFAULT])
