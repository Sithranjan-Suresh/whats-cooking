# What's Cooking?

**Turn one dish photo, or your sales data, into a scroll-stopping 8-second YouTube Short, then post it in one tap.**

**Try it:** https://whatscookinghq.vercel.app

Built for small restaurants that know they should post short videos but have no time, no editor and no idea which
dish to feature. Started at the LLMSoftware × UT Dallas Hackathon (Nov 2026, Special Recognition); this version
generates the videos for real.

## Using it

1. **Your restaurant:** upload your logo and type its name (every video ends with them). Optional: **create a
   mascot**: describe a character, pick one of four, and it pops into your videos' endings.
2. **Pick the dish**, either:
   - **Upload a dish photo** and type its name, price and (optionally) what's in it, or
   - **Upload a sales CSV** (Toast / Square / Clover item-sales export). The app creates your dishes from it and
     recommends one to feature ("up 32% this week").
3. **Choose a style:**
   - 🔥 **Money shot** (default): an up-close, mid-action shot with real kitchen sound, no narrator, loops.
   - 👨‍🍳 **Chef POV**: the cook's hands finishing the order, kitchen sound, "pov:" caption, loops.
   - 🎙 **Classic**: narrated promo ending on your logo, dish and price.
4. **Quick take** (one tap) or **🎬 Director mode**: plan the video in a chat with an AI director (storyboard: hook,
   captions, narration, the shot), preview a frame, then render.
5. **Action!** In about 1–3 minutes you get the Short. **What's in this video** shows the captions; **Edit captions**
   re-renders for free (it reuses the AI clip).
6. **Post to YouTube:** connect your channel once, then post with your own title, description and hashtags.
   **On YouTube** lists what you've posted with the app.

**Sign in with Google** (optional) to keep your studio and YouTube connection on every device. Without signing in,
everything works and is kept in that browser.

Try the **sample CSV** (link on the CSV tab) to see the sales pick without your own data.

## How it works

```
Browser (Next.js on Vercel) ──REST──▶ FastAPI on Render (Docker, ffmpeg) ──▶ Neon Postgres
                                        ├─ Gemini 3.5 Flash    reads the photo; writes hook/captions/narration/title; AI director chat
                                        ├─ Gemini Omni         image → 8 s video ("AI motion") with its own kitchen sound
                                        ├─ Gemini image model  Director preview frames, mascot designs
                                        ├─ edge-tts            narrator voice for Classic (gTTS fallback, then captions-only)
                                        ├─ ffmpeg              captions, loudness-normalized sound, logo/mascot, loop or logo ending
                                        ├─ budget guard        reserves each AI video before calling the model; $10 lifetime cap
                                        └─ YouTube Data API    resumable upload to the user's own channel
```

- **Grounded scripts.** The video may only state the dish name, price and description you typed. Code checks every
  script, Director plan and caption edit: each `$` amount must equal your price, the dish name must appear, and claims
  like "gluten-free", "award", "% off" are rejected unless they're in your description. A failing AI draft gets one
  repair attempt, then a safe template (`backend/app/services/scripts.py`).
- **Styles are data, not forks** (`backend/app/services/formats.py`): each style shapes the script prompt, the
  AI-motion prompt, captions, narrator, sound mix and ending. Based on what works in short-form food video: payoff in
  the first second, food sound over narration, native captions, loops.
- **Picks from sales data are plain Python**, not AI: last 7 days vs the 7 before. Gemini only writes the reason.
- **Nothing depends on a paid or slow call.** If AI motion fails, times out or the budget is used up, the video still
  renders with free photo motion. If the voice fails, it ships with captions and sound.
- **Cost control.** AI video spend is capped at **$10 in total, ever** (`budget.HARD_CAP_CENTS`), enforced in code
  before every AI-motion call and shared by everyone; it counts spend recorded before the ledger existed too. The page
  shows "AI videos left" and switches to free motion at zero. Previews, mascots and Director chats have their own
  per-visitor and daily caps.
- **Studios.** Each browser gets its own studio (a copy of the demo restaurant). Signing in with Google ties it to
  the account: the first sign-in keeps the guest studio, and every device then sees the same one.
- **YouTube.** Signed in, your connection is saved encrypted to your account; as a guest it's kept encrypted in your
  browser only (90 days). Disconnect revokes it at Google. Posted descriptions carry `#WhatsCookingApp`, which is how
  **On YouTube** lists only app-made videos.
- **Storage.** Everything lives in Postgres (Neon), including rendered videos (capped at 300 MB; AI clips, then posted
  videos, are cleared first), so restarts of the free host lose nothing.
- **Security.** Audited against a 25-item launch checklist: see **[docs/SECURITY.md](docs/SECURITY.md)**.

## Run it locally

Requirements: Python 3.12+, Node 20+, ffmpeg.

```bash
make setup                 # backend venv + frontend deps
cp .env.example .env       # optional: add GEMINI_API_KEY and Google OAuth values
make secrets               # paste APP_SECRET (and ADMIN_TOKEN) into .env
make seed                  # demo restaurant (Kumar's): menu, sample photos, 8 weeks of sales
make back                  # API → http://localhost:8000
make front                 # web → http://localhost:3000
```

With no keys at all it still works end to end: template scripts, free photo motion, no sign-in, no YouTube.
`make test` runs the backend tests (real ffmpeg; AI and YouTube are faked; ~100 tests) and the frontend type-check.
Against Postgres: `TEST_DATABASE_URL=postgresql://… make test`. Deploying your own copy: **[docs/DEPLOY.md](docs/DEPLOY.md)**.

## Repo map

```
frontend/   Next.js app: app/page.tsx is the main UI; components/ director, player, stage (clapper, marquee), ui
backend/    FastAPI: app/pipeline.py (analyze → script → visuals → voice → assemble), app/services/*, app/routers/*, tests/
seed/       demo restaurant data; sample dish photos are AI-generated (Gemini) stand-ins for real photos
eval/       grounding eval: production scripts vs an ungrounded photo-only prompt
scripts/    model listing, AI-motion smoke test, secret generator
docs/       DEPLOY.md · SECURITY.md · AUDIT.md (launch audit + roadmap) · planning/ (the original plan, historical)
contract.md API reference (source of truth; frontend/lib/types.ts mirrors it)
```

## Honest limits

- **Free hosting.** The API runs on Render's free plan (0.1 CPU, 512 MB): about 1–3 minutes per video, one at a
  time, and the server sleeps after 15 idle minutes (the first visit then takes about a minute).
- **Fair use is per IP.** One video in progress and 6 an hour per visitor; rotating proxies can get around that, but
  the queue cap and the $10 lifetime cap always hold.
- **Guest studios** belong to whoever has the browser's random id; sign in to tie one to an account. Don't upload
  anything confidential.
- **YouTube privacy.** Google may keep uploads from this unverified app private until it's reviewed. The app shows
  the status YouTube actually returns.
- **Cost estimate.** The cap counts AI videos at an estimated $0.64 each; previews, mascots and text calls add a
  little on top. Check real billing now and then and update `spent_outside_cents` (see docs/DEPLOY.md).
- **edge-tts is an unofficial endpoint.** It falls back to gTTS, then captions-only.

## Credits

Fonts: Bebas Neue, Courier Prime, Archivo, Oswald, Inter (SIL OFL). Music is synthesized by `seed/build_assets.py`.
Sales data is synthetic.
