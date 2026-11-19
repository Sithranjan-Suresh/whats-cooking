# What's Cooking?

**Turn one dish photo, or your sales data, into a narrated 8-second YouTube Short, then post it in one tap.**

**Try it:** https://whats-cooking-jade.vercel.app

Built for small restaurants that know they should post short videos but have no time, no editor and no idea which
dish to feature. Started at the LLMSoftware × UT Dallas Hackathon (Nov 2026, Special Recognition); this version
generates the videos for real.

## Using it

1. **Your logo:** upload it and type the restaurant name. Both close every video.
2. **Pick the dish**, either:
   - **Upload a dish photo** and type its name, price and (optionally) what's in it, or
   - **Upload a sales CSV** (Toast / Square / Clover item-sales export). The app creates your dishes from it and
     recommends one to feature ("up 32% this week"); you add its photo.
3. **Action!** In about 2–3 minutes you get an 8-second vertical Short:
   AI motion of your dish → narrator voice → short captions → animated logo ending with the dish and price.
4. **Post to YouTube:** connect *your own* channel once, then post. **On YouTube** lists the videos you've
   posted with the app (read live from your channel).

Try the **sample CSV** (link on the CSV tab) to see the sales pick without your own data.

## How it works

```
Browser (Next.js on Vercel) ──REST──▶ FastAPI on Render (Docker, ffmpeg)
                                        ├─ Gemini 3.5 Flash   reads the photo, writes hook/captions/narration/YouTube title
                                        ├─ Gemini Omni        image → 8s video ("AI motion"), with its own kitchen sound
                                        ├─ edge-tts           narrator voice (gTTS fallback, then captions-only)
                                        ├─ ffmpeg             captions, music ducked under the voice, animated logo ending
                                        ├─ budget guard       reserves each AI video before calling the model; hard cap
                                        └─ YouTube Data API   resumable upload to the visitor's channel
```

- **Grounded scripts.** The narrator may only state the dish name, price and description you typed. Code checks every
  script: each `$` amount must equal your price, the dish name must appear, and claims like "gluten-free", "award",
  "% off" are rejected unless they're in your description. A failing draft gets one repair attempt, then a safe
  template built from your fields (`backend/app/services/scripts.py`).
- **Picks from sales data are plain Python**, not AI: last 7 days vs the 7 before, anchored to the data's last date.
  Gemini only writes the one-line reason (`backend/app/services/insights.py`).
- **Nothing depends on a paid or slow call.** If AI motion fails, times out or the budget is used up, the video still
  renders with free photo motion (Ken Burns). If the voice fails, it ships with captions and music.
- **Cost control.** A shared test budget (default **$10**, about 15 AI videos at an estimated $0.64 each, max 10/day)
  is enforced in code before every AI-motion call. The page shows how many are left and switches to free motion at zero.
- **YouTube is per visitor.** Your connection is encrypted with the server's key and kept in *your browser*; the server
  stores none, so every visitor posts to their own channel. Posted descriptions carry a `#WhatsCookingApp` tag, which is
  how **On YouTube** shows only app-made videos from your channel.

## Run it locally

Requirements: Python 3.12+, Node 20+, ffmpeg.

```bash
make setup                 # backend venv + frontend deps
cp .env.example .env       # optional: add GEMINI_API_KEY and Google OAuth values
make secrets               # paste APP_SECRET into .env
make seed                  # demo restaurant (Kumar's): menu, sample photos, 8 weeks of sales
make back                  # API → http://localhost:8000
make front                 # web → http://localhost:3000
```

With no keys at all it still works end to end: template scripts, free photo motion, no YouTube.
`make test` runs the backend tests (real ffmpeg; AI and YouTube are faked) and the frontend type-check.
Deploying your own copy: **[docs/DEPLOY.md](docs/DEPLOY.md)**.

## Repo map

```
frontend/   Next.js app: app/page.tsx is the whole UI; components/ player, stage (clapper, marquee, curtain), ui
backend/    FastAPI: app/pipeline.py (analyze → script → visuals → voice → assemble), app/services/*, tests/
seed/       demo restaurant data; sample dish photos are AI-generated (Gemini) stand-ins for real photos
eval/       grounding eval: production scripts vs an ungrounded photo-only prompt
scripts/    model listing, AI-motion smoke test, secret generator
contract.md API reference        docs/planning/  the original plan (historical)
```

## Honest limits

- **Free hosting.** The API runs on Render's free plan: about 2–3 minutes per video, and the server sleeps after
  15 idle minutes (first visit then takes about a minute). Its disk resets on restart, so the data lives in a free
  Neon Postgres database: logo, name, photos, budget and history survive. Rendered video *files* don't (posted ones
  stay on YouTube), and your YouTube connection lives in your browser.
- **Fair use.** With no login, each visitor can have one video in progress and make 6 an hour; budget settings need
  an admin key, and AI-motion spend is capped at $10/month in code.
- **Shared studio.** Everyone who opens the link shares one restaurant (logo, name). "Your videos" lists the ones made
  in your browser, and YouTube is per visitor, but uploads aren't private: don't upload anything sensitive.
- **YouTube privacy.** Google may keep uploads from this unverified app private until it's reviewed. The app shows the
  status YouTube actually returns.
- **Cost estimate.** AI-motion pricing is an estimate ($0.64 per 8s); check real billing after a few videos.
- **edge-tts is an unofficial endpoint.** It falls back to gTTS, then captions-only.

## Credits

Fonts: Bebas Neue, Courier Prime, Archivo, Oswald, Inter (SIL OFL). Music is synthesized by `seed/build_assets.py`.
Sales data is synthetic.
