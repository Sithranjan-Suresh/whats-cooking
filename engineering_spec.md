# What's Cooking? — Engineering Spec

Design only, no code. An engineer, or a Claude Code session, should be able to build from this without making major design decisions.

**Ownership:**
- `backend/**`, `eval/**`, `seed/**` → **Sith**
- `frontend/**` → **Anish**
- `CLAUDE.md`, `contract.md` → humans only. A change requires both of you to agree and a commit prefixed `CONTRACT:`.

---

## 1. Architecture

```
 Browser (Next.js on Vercel)
   /insights /studio /library /settings
        │  REST (JSON)  + poll GET /jobs/{id} every 1.5s
        ▼
 FastAPI (Docker on Render/Railway/Fly, ffmpeg installed)
   ├─ routers: restaurants, menu, sales, insights, uploads, jobs, videos, youtube, usage, settings
   ├─ services:
   │    gemini.py   (analyze_photo, write_script, insight_reasons)   → Gemini API (free tier, Flash)
   │    veo.py      (generate_clip)                                  → Gemini API Veo (paid, capped)
   │    budget.py   (reserve_veo / commit / release)                 → UsageLedger (SQLite)
   │    tts.py      (synthesize: edge-tts → gTTS fallback)
   │    render.py   (kenburns, captions .ass, assemble)              → ffmpeg subprocess
   │    youtube.py  (oauth, upload resumable)                        → YouTube Data API v3
   │    insights.py (rank top/rising/slow)                           → pure Python
   ├─ queue.py: asyncio.Queue + 2 workers, job stage machine
   ├─ db: SQLite via SQLModel  (data/app.db)
   └─ media: data/media/{assets,clips,audio,videos,posters}  served at /media/*
```

**Key principle:** Veo is an optional upgrade inside the Visuals stage. The pipeline always has a free path, so the core loop never depends on a paid or slow call.

## 2. Shared Backbone

### 2.1 Data Model (SQLModel tables)
```
Restaurant      id, name, slug, logo_asset_id?, color_primary, color_accent, voice_tone(friendly|upbeat|elegant),
                tts_voice, created_at
MenuItem        id, restaurant_id, name, name_norm, price_cents?, description?, category?, photo_asset_id?
Asset           id, restaurant_id, kind(photo|logo|music), path, mime, width, height, bytes, created_at
SalesRecord     id, restaurant_id, date, menu_item_id?, raw_item_name, quantity, revenue_cents?
Insight         id, restaurant_id, menu_item_id, angle(top_seller|rising|slow_mover), metric_json, reason,
                reason_source(gemini|rule), created_at, batch_id
Job             id, restaurant_id, mode(photo|insight|menu), menu_item_id?, photo_asset_id, insight_id?,
                angle?, style(bold|warm|minimal), length_s(15|30), veo_requested(bool),
                veo_used(bool), fallback_reason?, status(queued|running|done|failed),
                stages_json, analyze_json?, script_json?, cost_cents, error?, created_at, finished_at?
Video           id, job_id, restaurant_id, path, poster_path, duration_s, width, height, bytes,
                youtube_id?, youtube_url?, youtube_privacy?, publish_status(draft|publishing|published|failed),
                created_at
UsageLedger     id, restaurant_id, date, job_id, kind(veo_clip), seconds, est_cost_cents,
                state(reserved|committed|released), created_at
Settings        restaurant_id (pk), daily_veo_clip_limit(int, default 10), monthly_cap_cents(default 1500),
                free_mode(bool), veo_cost_per_sec_cents(config default 8)
YouTubeAuth     restaurant_id (pk), refresh_token (encrypted at rest w/ Fernet key), channel_id, channel_title
```
`stages_json` = `[{name:"analyze"|"script"|"visuals"|"voice"|"assemble", status:"pending"|"running"|"done"|"failed"|"skipped", started_at, ended_at, note}]`

### 2.2 Data Flows Between Pillars
- **Insights → Studio:** `Insight.id` → `/studio?insight=ID` → `POST /jobs {mode:"insight", insight_id}`. The backend resolves the menu item, photo and angle, and the angle goes into the script prompt.
- **Studio → Library:** a finished Job creates a Video row, and Library lists Videos.
- **Brand & Budget → Studio:** `Restaurant` brand fields feed `render.py` (caption colors, logo end card) and `gemini.write_script` (voice tone). `Settings` + `UsageLedger` feed `budget.reserve_veo`.
- **(P2) Library → Insights:** `videos.list` statistics → `Video.views` → shown on insight cards.

### 2.3 Navigation and Routing (frontend)
`app/(shell)/layout.tsx` holds the sidebar on desktop (≥ 768px) and a bottom tab bar on mobile. Routes: `/insights`, `/studio`, `/library`, `/settings`. `/` redirects to `/insights` if `GET /insights` returns cards, otherwise `/studio`.

### 2.4 Design Tokens (`tailwind.config.ts`)
- **Colors:** `bg #0F1A14`, `panel #18261D`, `line #2A3A2F`, `gold #C49A4A`, `cream #F3EBDD`, `muted #9DAA9F`, `ok #5BD07F`, `bad #E0604F`
- **Fonts:** `display: Oswald`, `sans: Inter`, `mono: JetBrains Mono` (via `next/font`)
- **Radius:** `xl 16px`. **Shadow:** `glow: 0 0 40px rgba(196,154,74,.25)`

## 3. API Design (`contract.md` is the source of truth; copy this into it)

**Auth:**
- The single-owner app uses an `OWNER_TOKEN` header (`X-Owner-Token`), stored in localStorage after a one-time `/settings` unlock.
- With no token and `DEMO_MODE=1` → read-only demo: Veo is forced off, publishing is blocked (403 `demo_mode`).
- CORS allows the frontend origin.

All errors: `{"error": {"code": "snake_case", "message": "human readable", "retryable": bool}}`

| Method & path | Request | Response |
|---|---|---|
| GET `/health` | — | `{ok:true, mock:bool, demo:bool, veo_model, gemini_model}` |
| GET `/restaurants/me` | — | `Restaurant` + `menu_count`, `has_sales`, `youtube_connected` |
| PATCH `/restaurants/me` | partial brand fields | `Restaurant` |
| POST `/menu/import` | multipart CSV `name,price,description,category` | `{imported:int, skipped:int}` |
| GET `/menu` | — | `MenuItem[]` (with `photo_url`) |
| POST `/uploads` | multipart `file`, `kind` | `{asset_id, url, width, height}` (rejects >10 MB or a bad mime type) |
| POST `/menu/{id}/photo` | `{asset_id}` | `MenuItem` |
| POST `/sales/import` | multipart CSV | `{rows:int, dropped:int, date_from, date_to, unmatched_items:[str]}` |
| GET `/insights` | — | `{batch_id, cards:[{id, angle, menu_item:{id,name,photo_url}, metric:{qty_7d, wow_pct?, qty_14d?}, reason, reason_source}]}` |
| POST `/insights/refresh` | — | same as above (recomputes, then calls Gemini for reasons) |
| POST `/jobs` | `{mode, photo_asset_id?, menu_item_id?, insight_id?, style:"bold", length_s:15, veo:bool}` | `{job_id}` (202) |
| GET `/jobs/{id}` | — | `{id, status, stages:[...], analyze?, script?, veo_used, fallback_reason?, video?:{id,url,poster_url}, cost_cents, error?}` |
| POST `/jobs/{id}/confirm-dish` | `{menu_item_id \| null}` | `{ok}` (resumes a job paused in `needs_dish`) |
| GET `/videos` | — | `Video[]` newest first |
| POST `/videos/{id}/publish` | `{title, description, tags:[str], privacy:"private"\|"unlisted"\|"public"}` | `{publish_status:"publishing"}` (202). Poll `/videos/{id}` |
| GET `/videos/{id}` | — | `Video` |
| GET `/youtube/auth/start` | — | 302 to Google consent (scope `youtube.upload` + `youtube.readonly`) |
| GET `/youtube/auth/callback` | `code, state` | 302 to `/settings?youtube=connected` |
| GET `/usage` | — | `{today:{clips, limit}, month:{est_cents, cap_cents}, cost_per_sec_cents, free_mode}` |
| PATCH `/settings` | `{daily_veo_clip_limit?, monthly_cap_cents?, free_mode?}` | `Settings` |

**Job status extension:** `status` can be `needs_dish` (paused for the dish picker in S2).

### Mock-to-Live Switch
- `MOCK_PIPELINE=1`:
  - The job runner skips real calls and walks the stages with realistic latency: analyze 1.5s, script 3s (streams `script` at the end), visuals 6s (or 12s if `veo:true`), voice 1.5s, assemble 2s.
  - It then attaches `seed/mock_short.mp4`.
  - `MOCK_FAIL_RATE=0.1` randomly fails a stage, so the frontend's failure UI gets exercised.
  - Mock insights come from `seed/mock_insights.json`.
- `DEMO_CACHE=1`: a job for the seeded biryani menu item with `veo:true` returns `seed/hero_veo_short.mp4` after the mock timeline (the live demo safety net).
- The frontend uses `NEXT_PUBLIC_API_URL` and needs no code changes between mock and live.

## 4. Frontend Architecture (Anish)
```
app/
  (shell)/layout.tsx            Sidebar | BottomTabs, DemoBanner, Toaster
  (shell)/insights/page.tsx     SalesUpload, InsightCard[] , EmptyState(sample CSV link)
  (shell)/studio/page.tsx       InputPicker(Photo|FromInsight|FromMenu), OptionsBar(style,length,VeoToggle+cost),
                                GenerateButton, StageStepper, ScriptPanel, PhonePlayer, DishPickerModal
  (shell)/library/page.tsx      VideoGrid → VideoTile, PublishDialog
  (shell)/settings/page.tsx     BrandForm(+CaptionPreview), YouTubeConnect, BudgetMeter, LimitsForm, FreeModeToggle
components/ui/                  Card, Button, Badge, Toggle, Meter, StatTile, Modal, Skeleton, ErrorCallout
lib/api.ts                      typed fetch wrapper (adds X-Owner-Token; parses error shape)
lib/types.ts                    mirrors contract.md
hooks/useJob(id)                polls /jobs/{id} every 1.5s until done|failed|needs_dish
hooks/useUsage()                SWR on /usage, revalidate after each job
```
- **State:** server state via SWR. Local UI state with `useState`. The Studio query params (`insight`, `item`) are the source of truth for pre-fill. No global store.
- **StageStepper:** 5 rows with a spinner, check or ✕ per stage and elapsed time. Shows the `fallback_reason` badge on Visuals.
- **PhonePlayer:** a 9:16 frame with `<video playsInline muted autoPlay loop poster>` and a tap to unmute. Downloads use the `download` attribute.
- **Every fetch has:** a skeleton while loading, an ErrorCallout with Retry when `retryable`, and an empty state.

## 5. Backend Architecture (Sith)

### 5.1 Job Pipeline (state machine in `queue.py`)
```
queued → analyze → [needs_dish?] → script → visuals → voice → assemble → done
                         any stage failure → failed (with stage + error) ; visuals/voice degrade instead of failing
```
- **Analyze (`gemini.analyze_photo`):** input is the photo plus the restaurant's menu list (name, price, description, max 150 items). Structured output:
  `{is_food:bool, dish_guess:str, menu_item_id:int|null, confidence:0-1, visual_notes:str, quality:"good"|"dark"|"blurry"}`.
  If `mode=insight|menu`, the menu item is already known and Analyze only fills `visual_notes`.
- **Script (`gemini.write_script`):** inputs are the menu row (verbatim fields), angle, voice tone, length, `visual_notes` and the restaurant name. Structured output:
  ```
  {hook:str(≤8 words), beats:[{caption:str(≤22 chars/line, ≤2 lines), seconds:float}],
   voiceover:str(≤ 38 words for 15s / 75 for 30s), veo_prompt:str, title:str(≤70), description:str, hashtags:[str≤5],
   facts_used:[{"field":"name|price|description","value":str}]}
  ```
  The system prompt includes these hard rules:
  - Only mention dish name, price and description from MENU_ROW.
  - Never invent discounts, awards, health or allergen claims, or prices.
  - If price is null, don't mention price.

  **Post-validation:** every `$` amount in captions/voiceover must equal the menu price, and the dish name must appear. On fail → one repair retry → otherwise `template_script(menu_row, angle)`.
- **Visuals:**
  - If `veo_requested && !free_mode && budget.reserve_veo(job, seconds=8)` succeeds:
    - `veo.generate_clip(photo, veo_prompt, aspect="9:16", duration=8, resolution="720p")`, with the model from env `VEO_MODEL`.
    - Polls the long-running operation every 5s for up to 180s.
    - On success: download the MP4 → `budget.commit`. On failure: `budget.release` → free path with `fallback_reason`.
  - **Free path:** `render.kenburns(photo, length_s)` builds 2–3 crops of the photo with a slow zoom/pan (ffmpeg `zoompan` at 30fps, 1080×1920 scaled → 720×1280 output).
  - Veo mode for a 15s video: the 8s Veo clip + a 7s Ken Burns tail on the same photo, crossfaded.
- **Voice (`tts.synthesize`):** edge-tts voice from `Restaurant.tts_voice` (default `en-US-AriaNeural`) → mp3. Fallback is gTTS. Also returns word timings (edge-tts gives WordBoundary events) for caption sync. Without timings, beats split the duration by their `seconds`.
- **Assemble (`render.assemble`):**
  - Build an `.ass` subtitle file from the beats: brand colors, Oswald bold, centered lower third, a pop-in on each beat.
  - Run one ffmpeg graph: visuals (concat/xfade) + subtitles burn-in + voiceover + music (−18 dB, ducked under voice via `sidechaincompress`) + a 1.5s end card (logo + name + price on the brand color).
  - Encode: H.264 `-preset veryfast -crf 23`, AAC 128k, `-movflags +faststart`.
  - Extract the poster frame at 1.0s.
- **Concurrency:** 2 workers. Each ffmpeg call runs in `asyncio.create_subprocess_exec` with a 90s timeout.

### 5.2 Budget Guard (`budget.py`), atomic in one SQLite transaction
```
reserve_veo(restaurant, job, seconds):
  if settings.free_mode → deny("free_mode")
  clips_today = count(ledger where date=today and state in (reserved, committed))
  if clips_today >= daily_veo_clip_limit → deny("daily_limit")
  month_cents = sum(est_cost_cents where month=this and state in (reserved, committed))
  est = seconds * veo_cost_per_sec_cents
  if month_cents + est > monthly_cap_cents → deny("monthly_cap")
  insert ledger(state=reserved) → allow
commit(job) → state=committed ; release(job) → state=released
```
This is layer 3. Layers 1–2 live outside the code and are documented in the README:
- **Layer 1:** prepaid Gemini API credits with auto-reload off.
- **Layer 2:** an AI Studio project monthly spend cap set about 20% below the real limit, because billing data can lag.

### 5.3 Insights (`insights.py`, pure Python)
- **Normalize:** lowercase, strip punctuation and size words ("lg", "small"). Match menu items exact → normalized → `rapidfuzz` ratio ≥ 85.
- **Windows:** last 7 days vs. the prior 7, anchored to the max date in the data, not today (so demo data stays stable).
- **Top seller:** max `qty_7d`.
- **Rising:** max `wow_pct` among items with `qty_7d ≥ 10` and `qty_prev ≥ 3`.
- **Slow mover:** min `qty_14d` among items with a photo, excluding the other picks.
- **Reasons:** one Gemini call returns three sentences given the metrics. On failure, a rule template like "Up 32% vs last week with 84 sold."
- **CSV column aliases:** `date|Date|order_date|business_date`, `item_name|Item|item|menu_item|Item Name`, `quantity|Qty|qty|count|Quantity Sold`, `revenue|Net Sales|net_sales|amount`. This covers common Toast/Square/Clover item-sales exports. Confirm against one real export each.

### 5.4 YouTube (`youtube.py`)
- OAuth 2.0 web flow (`google-auth-oauthlib`), scopes `youtube.upload` and `youtube.readonly`, `access_type=offline`, `prompt=consent`. The refresh token is encrypted with Fernet (`APP_SECRET`).
- Upload with `googleapiclient` `videos().insert(part="snippet,status", media_body=MediaFileUpload(resumable=True, chunksize=8MB))`:
  - Category 26 (Howto & Style) or 19 (Travel & Events)
  - Hashtags appended to the description, `#Shorts` included
- Read back `status.privacyStatus` and store it. Expect `private` while the app is unaudited, and show the info note.
- Quota: current default allocation is 100 `videos.insert` per day. Show an error on `quotaExceeded`.

### 5.5 Configuration (`.env`)
```
GEMINI_API_KEY=            # same key for Flash + Veo (paid tier, prepaid)
GEMINI_TEXT_MODEL=         # current Flash model id — verify with models.list on day 0
VEO_MODEL=                 # current Veo image-to-video model id — verify (Veo 3.1 listed deprecated Oct 2026)
VEO_COST_PER_SEC_CENTS=8   # set from current pricing page for the chosen model/resolution
GOOGLE_OAUTH_CLIENT_ID= / GOOGLE_OAUTH_CLIENT_SECRET= / OAUTH_REDIRECT_URI=
APP_SECRET=                # Fernet key
OWNER_TOKEN=
DEMO_MODE=1  MOCK_PIPELINE=0  DEMO_CACHE=1  MOCK_FAIL_RATE=0
FRONTEND_ORIGIN=
```

## 6. Eval Harness (`eval/`)
- `eval/cases.json`, 20 cases:
  - **12 `photo` cases:** `{photo, menu_row:{name,price,description}, expected:{name, price}}`
  - **8 `sales` cases:** `{csv_slice, expected_top_seller, expected_rising}`
- **Baseline (photo cases):** the same Gemini model with the photo only, prompted "write a short promo script for this dish". No menu row, no rules.
- **Grounded:** the production `write_script` path.
- **Scoring (`run_eval.py`):**
  - `name_ok`: normalized dish name present in the voiceover or captions
  - `price_ok`: every `$x.xx` equals the menu price (or no price is mentioned when it's null). An invented price fails.
  - `no_invented_claims`: a regex for `%|off|discount|award|best in|gluten|vegan|allergen|healthy` that isn't in the menu description, plus an LLM-judge yes/no
  - `pass = name_ok and price_ok and no_invented_claims`
  - Sales cases: the picks equal the expected ones
- **Output:** a table plus one line for the pitch, e.g. `grounded 20/20 · baseline 11/20 · sales picks 8/8`. Written to `eval/results.md`.
- **Stretch:** 40–50 cases, a second baseline (menu row given but no rules or validation), and a failure-case table.

## 7. Performance Budget and Fallbacks
| Pillar | Budget | Fallback |
|---|---|---|
| Studio (free mode) | ≤ 45s end to end | Template script, captions-only audio |
| Studio (Veo) | ≤ 150s p90 | Automatic free visuals. `DEMO_CACHE` hero video for the live demo |
| Insights | ≤ 3s compute, ≤ 8s with reasons | Rule-based reasons. `seed/mock_insights.json` |
| Library | First paint ≤ 1.5s, posters lazy-loaded | — |
| Publish | ≤ 60s for 10 MB | Retry ×3, then seeded `youtube_url` in demo mode |
| Frontend | JS ≤ 250 KB gzipped per route, FCP ≤ 1.5s on 4G | — |

**Seeded inputs (`seed/`):**
- `kumars_menu.csv` (≈ 20 items with prices)
- 8 dish photos
- `kumars_sales_8w.csv` (8 weeks, biryani rising about 30% WoW)
- logo
- royalty-free `music_upbeat.mp3`
- `mock_short.mp4`
- `hero_veo_short.mp4` (generated once for real, then cached)

`seed.py` loads all of this into the DB.

## 8. External Integrations
- **Gemini API (google-genai SDK):**
  - Flash on the free tier for text and vision. Free-tier content may be used to improve Google's products, so don't send private sales data from real customers on the free tier.
  - Veo on the paid tier, per-second pricing.
- **YouTube Data API v3:** free and quota-based. The `youtube.upload` scope is restricted, and public uploads need Google's verification/audit.
- **edge-tts** (unofficial, free), **gTTS** (fallback).
- **ffmpeg** (in the Docker image).
- **Future:** Toast, Square and Clover APIs replacing CSV import.

## 9. Deployment
- **Backend:**
  - Dockerfile `python:3.12-slim` + `apt-get install ffmpeg fonts-…` (bundle the Oswald/Inter TTF files in `backend/assets/fonts` for libass)
  - Deploy on Render/Railway/Fly with a **persistent volume** at `/app/data` (SQLite + media)
  - Health check `/health`
- **Frontend:** Vercel, with env `NEXT_PUBLIC_API_URL`.
- **"Submitted and running" means:**
  - The public URL loads the seeded Kumar's demo with no login.
  - A free-mode job completes live.
  - The `DEMO_CACHE` hero Veo job plays.
  - At least one video is published on the team's YouTube channel with its link shown.
  - `eval/results.md` is committed.
  - The README has setup steps, a cost-control section (all 3 layers), and a "How we used AI" section.
- **Repo layout:**
  ```
  /backend  /frontend  /eval  /seed  CLAUDE.md  contract.md  README.md  Makefile (make back | make front | make seed | make eval)
  ```

## 10. Build Order (feeds task-breakdown)
1. **Both:**
   - Sith: repo, `contract.md`, `CLAUDE.md`, backend stubs + `MOCK_PIPELINE`, seed data.
   - Anish: shell, design tokens, and all 4 pages against the mocks.
2. **Sith:** free-mode pipeline end to end (Analyze → Script → Ken Burns → TTS → Assemble). **← Checkpoint 1: the core loop works live.**
3. **Sith:** the eval set + `run_eval.py`. **Anish:** Studio stepper, player and script panel on live data.
4. **Sith:** insights + CSV import. **Anish:** the Insights page + Make-video pre-fill.
5. **Sith:** the budget guard + Veo + fallback, then YouTube OAuth + upload. **Anish:** the Settings page + Library publish.
6. **Checkpoint 2:** every pillar works on real data, the eval result is in, an outsider test passes, and the hero Veo video is cached.
7. Deploy, run the demo path on a phone, rehearse.
