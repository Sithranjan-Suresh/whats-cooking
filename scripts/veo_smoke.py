"""Day-0 check (task 3): one real 8s Veo clip from a photo, timed. COSTS MONEY (~8 × VEO_COST_PER_SEC_CENTS).

    backend/.venv/bin/python scripts/veo_smoke.py seed/photos/chicken-biryani.jpg [runs]
"""
import asyncio
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import get_settings  # noqa: E402
from app.services import veo  # noqa: E402
from app.services.media import probe_video  # noqa: E402
from app.services.scripts import default_veo_prompt  # noqa: E402


async def main():
    photo = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "seed/photos/chicken-biryani.jpg")
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    s = get_settings()
    print(f"model={s.veo_model}  est cost/clip=${8 * s.veo_cost_per_sec_cents / 100:.2f}  runs={runs}")
    times = []
    for i in range(runs):
        out = ROOT / f"veo_smoke_{i}.mp4"
        t = time.time()
        try:
            await veo.generate_clip(photo, "image/jpeg", default_veo_prompt(), out)
        except veo.VeoError as e:
            print(f"run {i}: FAILED ({e.kind}) {e}")
            continue
        dt = time.time() - t
        times.append(dt)
        print(f"run {i}: {dt:.0f}s → {out.name} {await probe_video(out)}")
    if times:
        times.sort()
        p90 = times[min(len(times) - 1, int(round(0.9 * (len(times) - 1))))]
        print(f"latency: median {statistics.median(times):.0f}s, p90 {p90:.0f}s. "
              + ("OK for a live demo." if p90 <= 90 else "Too slow for live: demo with DEMO_CACHE=1."))


asyncio.run(main())
