"""Day-0 check (tasks 1-2): list the Gemini Flash + Veo models this API key can use.

    backend/.venv/bin/python scripts/check_models.py
Copy the IDs you want into .env as GEMINI_TEXT_MODEL and VEO_MODEL.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import get_settings  # noqa: E402

s = get_settings()
if not s.gemini_api_key:
    sys.exit("Set GEMINI_API_KEY in .env first.")
from google import genai  # noqa: E402

client = genai.Client(api_key=s.gemini_api_key)
flash, veo = [], []
for m in client.models.list():
    name = m.name.replace("models/", "")
    actions = getattr(m, "supported_actions", None) or []
    if "veo" in name:
        veo.append((name, actions))
    elif "flash" in name and "generateContent" in actions and "image" not in name and "tts" not in name:
        flash.append((name, actions))
print("Gemini Flash (text + vision):")
for n, _ in sorted(flash):
    print("  ", n, "  <- current GEMINI_TEXT_MODEL" if n == s.gemini_text_model else "")
print("\nVeo (video):")
for n, a in sorted(veo):
    print("  ", n, a, "  <- current VEO_MODEL" if n == s.veo_model else "")
if s.gemini_text_model not in [n for n, _ in flash]:
    print(f"\n!! GEMINI_TEXT_MODEL={s.gemini_text_model} is not in the list above. Pick one.")
if s.veo_model not in [n for n, _ in veo]:
    print(f"!! VEO_MODEL={s.veo_model} is not in the list above. Pick one (prefer a 'fast'/'lite' variant).")
