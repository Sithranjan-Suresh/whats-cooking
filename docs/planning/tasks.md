# What's Cooking? — Implementation Task List (Phase 8)

Single global checklist. Completing every task = production-ready submission.
**Team:** solo build. One person (with Claude) does everything, so tasks are ordered for a single linear pass.
**Priority:** P0 = demo-blocking · P1 = depth/polish · P2 = extras.
**Checkpoints:** CP1 = free-mode core loop works live · CP2 = every pillar on real data, eval result in, outsider test, hero Veo cached · CP3 = deployed, phone-tested, rehearsed.
**Rule:** all P0s before any P1s; deployment starts early (Section 3).

## Build status (2026-11-18)

**Done ([x]):** everything that can be built and verified without your accounts. Backend (43 tests passing), frontend (4 pages, phone + desktop, browser-tested), seed data, eval harness, Docker image (built and run locally), Render blueprint, docs.

**Waiting on you (unchecked):** see `docs/SETUP.md` for exact steps.
- Real dish photos + logo → 8 (and the 4 eval-only photos in 97)
- Gemini API key (prepaid, capped) → 1–4, 103, 121–123, 125, 140, 161
- Google Cloud OAuth client + YouTube channel → 5, 133, 135
- Render + Vercel deploy → 25, 27, 34, 94–96, 139, 142, 171–177
- Human-only → 141 outsider test, 162 owner feedback, 166 billing screenshots, 178–186 rehearsal/submit/follow-up

**Not built (P2, by the cut order):** 163 view counts → Insights, 164 scheduling/multi-music/day-time patterns/IG/TikTok.

**Changed from the plan:**
- 153: "regenerate one beat" shipped as **edit any caption + re-render**. Edits go through the grounding validator.
- 62: added `GET /jobs?status=active`.
- 107: sales import **replaces** previous data.

---

## Section 0 — Day-0 Risk Retirement (do before building; these can invalidate the plan)

- [ ] **1. [P0] Verify Gemini text model ID.** Call `models.list` with the API key; pick the current Flash model that supports image input + structured JSON output; record the exact ID as `GEMINI_TEXT_MODEL` in `.env.example` and a scratch note.
- [ ] **2. [P0] Verify Veo image-to-video model ID and pricing.** From `models.list` and the pricing page, pick the Lite/Fast Veo variant that supports image input, 9:16, 720p, 8s. Record `VEO_MODEL` and compute `VEO_COST_PER_SEC_CENTS` (target ≤ $0.70 per 8s clip). Note if Veo 3.1 is deprecated (engineering spec flags Oct 22, 2026) and pick the replacement.
- [ ] **3. [P0] Run one real 8-second Veo test clip** from a single dish photo. Record wall-clock latency, output format/resolution/aspect, and whether audio is included. Repeat up to 5 times if budget allows to estimate p90 latency (decides whether live Veo demo is viable or `DEMO_CACHE` is the primary path).
- [ ] **4. [P0] Set up the 3-layer cost cap before the first paid call beyond task 3:** (1) prepay Gemini API credits with auto-reload OFF, (2) set the AI Studio project monthly spend cap ~20% below the real limit, (3) screenshot both settings for the README. Document the ~10-minute billing lag.
- [ ] **5. [P0] Test YouTube upload without audit.** Create Google Cloud project, enable YouTube Data API v3, create OAuth web client (scopes `youtube.upload`, `youtube.readonly`), add yourselves as test users, upload one throwaway video, read back `status.privacyStatus`. Record the result (expected: `private`) — this drives the info-note UX.
- [x] **6. [P0] Smoke-test edge-tts and gTTS** from a Python shell: synthesize one sentence each, confirm WordBoundary timings from edge-tts, confirm gTTS fallback works with no timings.
- [x] **7. [P0] Smoke-test ffmpeg locally:** confirm `zoompan`, `xfade`, `subtitles` (libass), `sidechaincompress` filters exist (`ffmpeg -filters`). Confirm Oswald/Inter TTFs render through libass.
- [ ] **8. [P0] Obtain/confirm assets:** Kumar's menu data (~20 items), 8 real dish photos (JPG, ≥1080px on the short side), logo PNG (transparent), royalty-free `music_upbeat.mp3` (license noted in README).

---

## Section 1 — Repo, Contract & Scaffolding (Checkpoint 0)

- [x] **9. [P0] Create repo skeleton:** `/backend /frontend /eval /seed` + `CLAUDE.md`, `contract.md`, `README.md`, `Makefile`, `.gitignore` (ignore `data/`, `.env`, `node_modules`, `__pycache__`, `.next`), `.env.example` with every variable from engineering spec §5.5.
- [x] **10. [P0] Write `CLAUDE.md`:** project summary, "`contract.md` is the API source of truth; change it deliberately and prefix the commit with `CONTRACT:`", run commands, mock-vs-live switches.
- [x] **11. [P0] Write `contract.md`:** paste the full API table from engineering spec §3, the error shape `{"error":{"code","message","retryable"}}`, the `needs_dish` job status, `stages_json` shape, `GET /health` shape, auth rules (`X-Owner-Token`, `DEMO_MODE`), and example JSON for every endpoint response. Commit it with the prefix `CONTRACT:`.
- [x] **12. [P0] Write `Makefile`:** `make back` (uvicorn reload), `make front` (next dev), `make seed` (run `seed.py`), `make eval` (run `eval/run_eval.py`), `make test` (pytest).
- [x] **13. [P0] Backend project setup:** `backend/pyproject.toml` or `requirements.txt` (fastapi, uvicorn, sqlmodel, pydantic, google-genai, edge-tts, gTTS, rapidfuzz, python-multipart, pillow, google-auth-oauthlib, google-api-python-client, cryptography, pytest, httpx). Create `backend/app/` with `main.py`, `config.py` (reads `.env` via pydantic-settings), `db.py`, `models.py`, `errors.py`, `routers/`, `services/`.
- [x] **14. [P0] Config module:** typed settings for every env var (`GEMINI_API_KEY`, `GEMINI_TEXT_MODEL`, `VEO_MODEL`, `VEO_COST_PER_SEC_CENTS`, OAuth vars, `APP_SECRET`, `OWNER_TOKEN`, `DEMO_MODE`, `MOCK_PIPELINE`, `DEMO_CACHE`, `MOCK_FAIL_RATE`, `FRONTEND_ORIGIN`, `DATA_DIR`).
- [x] **15. [P0] Global error handling:** custom `AppError(code, message, retryable, status)` + exception handlers so every error returns the contract shape; handler for validation errors and unhandled exceptions (log + generic `internal_error`).
- [x] **16. [P0] CORS + media serving:** CORS allowing `FRONTEND_ORIGIN` (and localhost:3000 in dev); mount `data/media` at `/media/*`; ensure subdirs `assets, clips, audio, videos, posters` are created on startup.
- [x] **17. [P0] Auth dependency:** `X-Owner-Token` check vs `OWNER_TOKEN`; `get_actor()` returns `owner` or `demo`; if no valid token and `DEMO_MODE=1` → `demo` (read-only, Veo forced off, publish → 403 `demo_mode`); if no token and demo off → 401.
- [x] **18. [P0] `GET /health`:** returns `{ok, mock, demo, veo_model, gemini_model}`.

## Section 2 — Database Schema & Models

- [x] **19. [P0] SQLModel tables:** `Restaurant, MenuItem, Asset, SalesRecord, Insight, Job, Video, UsageLedger, Settings, YouTubeAuth` exactly per engineering spec §2.1 (all fields, types, nullable markers, FKs). JSON columns (`stages_json, analyze_json, script_json, metric_json`) stored as text with helper (de)serializers.
- [x] **20. [P0] DB bootstrap:** SQLite at `data/app.db`, `create_all()` on startup, WAL mode, `busy_timeout`, session dependency. Add indexes: `SalesRecord(restaurant_id,date)`, `UsageLedger(restaurant_id,date,state)`, `Video(restaurant_id,created_at)`, `MenuItem(restaurant_id,name_norm)`.
- [x] **21. [P0] Name normalization util** (`normalize_name`): lowercase, strip punctuation, strip size words ("lg", "large", "small", "regular"), collapse whitespace. Unit-test with 10 examples.
- [x] **22. [P0] Single-restaurant resolution:** helper `current_restaurant()` returning the one seeded restaurant (app is single-owner); used by every router.
- [x] **23. [P0] Fernet helper:** `encrypt/decrypt` using `APP_SECRET`; unit test round-trip.

## Section 3 — Early Deployment (don't leave to last hour)

- [x] **24. [P0] Backend Dockerfile:** `python:3.12-slim`, `apt-get install ffmpeg` + fontconfig, copy `backend/assets/fonts` (Oswald, Inter TTFs) and run `fc-cache`, install deps, `CMD uvicorn`, expose port, healthcheck on `/health`.
- [ ] **25. [P0] Deploy backend (stub) to Render/Railway/Fly** with a persistent volume mounted at `/app/data`; set all env vars; confirm `/health` returns `ok:true` on the public URL.
- [x] **26. [P0] Verify ffmpeg + libass fonts inside the deployed container:** temporary debug endpoint or shell command rendering one subtitle line to a PNG; delete the endpoint after.
- [ ] **27. [P0] Create Next.js app** (App Router, TypeScript, Tailwind) in `/frontend`; deploy empty shell to Vercel; set `NEXT_PUBLIC_API_URL`; confirm it loads on a phone and can fetch `/health` (CORS verified).

## Section 4 — Mock Pipeline & Seed Data (lets the frontend be built against stable mocks)

- [x] **28. [P0] Seed files:** `seed/kumars_menu.csv` (~20 items, columns `name,price,description,category`, ≥1 item with null price for edge case), 8 dish photos incl. biryani, `kumars_sales_8w.csv` (8 weeks; biryani ≈ +30% WoW with ≥10 units this week; a clear top seller; a clear slow mover with a photo), logo, `music_upbeat.mp3`.
- [x] **29. [P0] Produce `seed/mock_short.mp4`** (720×1280, ≤ 8 MB, any representative render) and `seed/mock_insights.json` matching the `/insights` contract.
- [x] **30. [P0] `seed.py`:** idempotent; creates Kumar's restaurant (brand colors gold/dark green, voice tone upbeat, tts voice), imports menu, copies photos to `data/media/assets` creating `Asset` rows and linking `photo_asset_id`, imports sales, creates `Settings` defaults (daily limit 10, cap 1500¢, free_mode false, cost 8¢/s), seeds 2–3 historical `Video` rows (one with `youtube_url` and `publish_status=published`).
- [x] **31. [P0] Stub every contract endpoint** in routers returning contract-shaped data (from seed/mock). Includes all rows of the §3 API table.
- [x] **32. [P0] `MOCK_PIPELINE=1` job runner:** `POST /jobs` returns 202 `{job_id}`; background task walks stages analyze 1.5s → script 3s (writes `script_json`) → visuals 6s (12s if `veo`) → voice 1.5s → assemble 2s; attaches `seed/mock_short.mp4` as a Video. Include `MOCK_FAIL_RATE` random stage failure.
- [x] **33. [P0] Mock `needs_dish` path:** when mock job is created with `mode=photo` and no menu item and env flag `MOCK_NEEDS_DISH=1`, pause at analyze with `needs_dish` and resume via `/jobs/{id}/confirm-dish`.
- [ ] **34. [P0] Redeploy backend with mock mode on** so the frontend can be built against the live URL.

## Section 5 — Frontend Foundation (do after the mock backend is up; Sections 6–7 follow)

- [x] **35. [P0] Tailwind design tokens** per §2.4: colors (`bg, panel, line, gold, cream, muted, ok, bad`), fonts via `next/font` (Oswald → `display`, Inter → `sans`, JetBrains Mono → `mono`), `rounded-xl` 16px, `shadow-glow`. Set page background/text defaults.
- [x] **36. [P0] UI kit** in `components/ui/`: `Card, Button (primary gold / ghost / danger), Badge, Toggle, Meter, StatTile, Modal, Skeleton, ErrorCallout (with Retry)`. Each with disabled/loading states.
- [x] **37. [P0] `lib/types.ts`** mirroring `contract.md` (Restaurant, MenuItem, Insight card, Job, Stage, Script, Video, Usage, Settings, ApiError).
- [x] **38. [P0] `lib/api.ts`:** typed fetch wrapper using `NEXT_PUBLIC_API_URL`, injects `X-Owner-Token` from localStorage, parses the error shape into a typed `ApiError` (code/message/retryable), handles network failure as retryable error.
- [x] **39. [P0] Shell layout `app/(shell)/layout.tsx`:** desktop sidebar (≥768px) with What's Cooking? wordmark + Insights/Studio/Library/Brand & Budget; mobile bottom tab bar (4 tabs); `DemoBanner` (visible when `/health.demo` and no owner token); toaster.
- [x] **40. [P0] `/` redirect:** server/client check `GET /insights`; cards → `/insights`, else `/studio`.
- [x] **41. [P0] `useJob(id)` hook:** polls `/jobs/{id}` every 1.5s until `done|failed|needs_dish`; exposes `{job, error, isPolling}`; cleans up on unmount; keeps polling continuity if user returns.
- [x] **42. [P0] `useUsage()` hook:** SWR on `/usage`, exposes `revalidate()` to call after each job.
- [x] **43. [P0] Global loading/error/empty conventions:** every data fetch uses Skeleton while loading, ErrorCallout with Retry when `retryable`, and a defined empty state. Add a small `Fetch<T>` wrapper component to enforce this.

## Section 6 — Frontend Pages Against Mocks

- [x] **44. [P0] Insights page** (`/insights`): `SalesUpload` (drag/drop CSV, shows rows/dropped/date range/unmatched list after upload), `InsightCard` ×3 (angle badge, item name+photo, metric string like "+32% WoW · 84 sold", reason, **Make video**), `EmptyState` with "Download sample CSV" link, skeletons, error state.
- [x] **45. [P0] Insights "Make video" navigation** → `/studio?insight=<id>`.
- [x] **46. [P0] Studio page layout** (`/studio`): `InputPicker` tabs (Photo | From insight | From menu), `OptionsBar`, `GenerateButton`, results area with `StageStepper` + `ScriptPanel` + `PhonePlayer`. Query params `insight` and `item` are the source of truth for pre-fill.
- [x] **47. [P0] Photo upload in Studio:** accepts JPG/PNG/WEBP ≤ 10 MB client-side validated; inline error "Use a JPG or PNG under 10 MB."; preview thumbnail; `POST /uploads`.
- [x] **48. [P0] Menu item picker** (for "From menu" and for photo mode manual select): searchable list from `GET /menu` with photo thumbnails.
- [x] **49. [P0] Pre-fill from insight:** resolve insight → dish, photo, angle chip shown ("Angle: Rising"); if dish has no photo, prompt for upload with dish already selected.
- [x] **50. [P0] `OptionsBar`:** style select (Bold enabled; Warm/Minimal disabled with "soon" tag in P0), length (15s enabled; 30s P1), `VeoToggle` with live cost estimate ("≈ $0.64" = 8 × cost-per-sec from `/usage`), disabled with reason when daily limit/monthly cap/free mode/demo mode.
- [x] **51. [P0] `StageStepper`:** 5 rows (Analyze, Script, Visuals, Voice, Assemble) with spinner/check/✕/skip per stage, elapsed time per stage, note text, `fallback_reason` badge on Visuals ("Free mode (Veo unavailable)").
- [x] **52. [P0] `ScriptPanel`:** fills when script stage completes: hook, caption beats with "from menu: price/name/description" chips (from `facts_used`), voiceover text, title, description, hashtags. Skeleton before it arrives.
- [x] **53. [P0] `PhonePlayer`:** 9:16 frame, `<video playsInline muted autoPlay loop poster>`, tap-to-unmute overlay, gold glow, Download button using `download` attribute, lazy-load with poster.
- [x] **54. [P0] `DishPickerModal`** for `needs_dish`: shows top-3 menu matches with photos + "Not on menu"; calls `POST /jobs/{id}/confirm-dish`; resumes polling.
- [x] **55. [P0] Studio failure states:** failed job shows the stage, error message, **Retry** (re-POST /jobs with same inputs), not-food warning ("This doesn't look like a dish photo. Try another?" + "Continue anyway"), never a blank screen or endless spinner (cap polling UI at 5 min with a timeout message).
- [x] **56. [P0] "Leave and come back" behavior:** persist last `job_id` in localStorage/URL (`?job=`) so returning to Studio resumes the stepper; Library shows in-progress jobs (see task 61).
- [x] **57. [P0] Library page** (`/library`): `VideoGrid` newest first; `VideoTile` with lazy poster, dish name, date, mode badge (Veo/Free), cost, status badge (Draft/Published/Failed); click opens modal player; Download.
- [x] **58. [P0] `PublishDialog`:** pre-filled title/description/hashtags from script (editable), privacy select (Private default, Unlisted, Public), progress state, success state "Published ↗" with link + the privacy YouTube actually returned, info note for restricted/private, quotaExceeded message, Retry on failure; disabled with explanation in demo mode.
- [x] **59. [P0] "Connect YouTube" CTA** in Library when not connected → links to `/settings`.
- [x] **60. [P0] Library empty state** (no videos → CTA to Studio) and error/skeleton states.
- [x] **61. [P0] Library in-progress tiles:** jobs with status queued/running appear as tiles with live stage progress (needs a `/jobs` list or `/videos` to include in-progress; coordinate via `contract.md` change task 62).
- [x] **62. [P0] CONTRACT change (if needed):** add `GET /jobs?status=active` (or include in-progress items in `GET /videos`) for task 61; commit with the `CONTRACT:` prefix.
- [x] **63. [P0] Settings page** (`/settings`): `BrandForm` (name, logo upload PNG, primary/accent color pickers, voice tone Friendly/Upbeat/Elegant, TTS voice select) with live `CaptionPreview` (sample caption styled in brand colors/font); `PATCH /restaurants/me`.
- [x] **64. [P0] Settings: `BudgetMeter` + `LimitsForm` + `FreeModeToggle`:** today clips used/limit, month est $/cap, cost per Veo second, edit daily limit (0–50) and monthly cap ($0–$100), toggle free mode; `PATCH /settings`; meters turn `bad` red when at limit.
- [x] **65. [P0] Settings: `YouTubeConnect`:** shows channel title if connected, "Connect YouTube" button → `/youtube/auth/start`, handles `?youtube=connected` toast.
- [x] **66. [P0] Owner unlock flow:** one-time field in `/settings` to enter `OWNER_TOKEN`, stored in localStorage; changes banner state; "Lock" button clears it.
- [x] **67. [P0] Demo-mode UI rules:** with no owner token + demo: Veo toggle disabled with "Demo mode: Veo reserved for the presenter", publish buttons disabled, seeded published videos show links, banner visible.
- [x] **68. [P0] Mobile pass on all 4 pages** at 375px width: no horizontal scroll, tap targets ≥ 44px, bottom tab bar not overlapping content, player fits viewport.
- [x] **69. [P0] Wire pages to live mock backend** (Section 4's deployed URL); fix contract mismatches by raising `CONTRACT:` changes, not local hacks.

## Section 7 — Backend: Core Services (free-mode loop → CP1)

- [x] **70. [P0] Uploads router (`POST /uploads`):** accept multipart `file`+`kind`; reject >10 MB or mime not in JPG/PNG/WEBP (logo: PNG) with error codes `file_too_large`/`bad_mime`; read dims with Pillow, strip EXIF orientation properly (apply rotation), save to `data/media/assets/<uuid>.<ext>`, create `Asset`, return `{asset_id,url,width,height}`.
- [x] **71. [P0] Menu router:** `POST /menu/import` (CSV `name,price,description,category`; parse price strings like "$12.99" to cents; blank price → null; skip empty names; return `{imported, skipped}`), `GET /menu` (with `photo_url`), `POST /menu/{id}/photo` (links asset).
- [x] **72. [P0] Restaurants router:** `GET /restaurants/me` (+ `menu_count`, `has_sales`, `youtube_connected`), `PATCH /restaurants/me` (partial brand fields; validate hex colors, tone enum).
- [x] **73. [P0] `gemini.py` client wrapper:** one `google-genai` client, timeout handling, 429 backoff, structured-output (response schema) helper `generate_json(prompt, schema, image=None)` returning parsed object or raising typed `GeminiError(kind: timeout|rate_limit|malformed|blocked)`.
- [x] **74. [P0] `analyze_photo`:** inputs photo + menu list (name, price, description, cap 150); structured output `{is_food, dish_guess, menu_item_id, confidence, visual_notes, quality}`; 20s timeout → retry once → raise; JSON repair retry; 429 → wait 5s retry ×2.
- [x] **75. [P0] Analyze behavior rules:** `mode=insight|menu` → skip match, only produce `visual_notes`; confidence < 0.6 or `menu_item_id` null → job status `needs_dish` with top-3 candidates stored in `analyze_json`; `is_food=false` or low quality → store warning flag (frontend shows warning, user may continue).
- [x] **76. [P0] `POST /jobs/{id}/confirm-dish`:** accepts `menu_item_id|null`; null → set "not on menu" flag so script omits price; resume job from script stage; reject if job not in `needs_dish`.
- [x] **77. [P0] `write_script` prompt + schema:** system prompt with hard rules (only name/price/description from MENU_ROW; never invent discounts/awards/health/allergen claims/prices; omit price if null); inputs menu row verbatim, angle, voice tone, length, visual_notes, restaurant name; output schema per §5.1 (hook ≤8 words, beats with ≤22 chars/line ≤2 lines and `seconds`, voiceover ≤38/75 words, `veo_prompt`, title ≤70, description, hashtags ≤5, `facts_used`).
- [x] **78. [P0] Script angle → hook mapping:** `top_seller` ("everyone's ordering"), `rising` ("back by demand"), `slow_mover` ("underrated gem") — phrased without inventing facts; metrics can be referenced only if they're real (e.g., rising % from the insight).
- [x] **79. [P0] Script post-validation:** every `$` amount in captions/voiceover equals menu price; dish name present (normalized); beats' total seconds within ±1s of length; trim/validate hashtag count. On failure → one repair retry → `template_script(menu_row, angle)`.
- [x] **80. [P0] `template_script`:** deterministic fallback built from menu fields (hook "Try the {name}", beats with name/price/description snippets, voiceover assembled from fields, generic hashtags, `veo_prompt` = slow steam/camera push on the dish) — passes its own validator.
- [x] **81. [P0] `tts.py`:** `synthesize(text, voice, out_path)` → edge-tts mp3 + word timings (list of `{word,start,end}`); 15s timeout; retry once; fallback to gTTS (no timings); returns `{path, duration_s, timings|None, engine}`; zero-length audio → fallback; empty voiceover → return None (captions-only).
- [x] **82. [P0] `render.kenburns(photo, length_s)`:** produce 2–3 crops (e.g., center, upper-left, lower-right) of the photo, each with slow zoom/pan via ffmpeg `zoompan` at 30fps, rendered at 1080×1920 and scaled to 720×1280; crossfade (`xfade`) between segments; output intermediate mp4. Handle landscape photos (crop to 9:16 with face/center bias) and tiny photos (upscale).
- [x] **83. [P0] `render.build_ass`:** generate `.ass` from beats + timings: brand primary/accent colors, Oswald Bold, centered lower third, ≤2 lines/22 chars, auto-shrink font for long dish names, pop-in (scale+fade) per beat; fall back to even split by `seconds` when no word timings.
- [x] **84. [P0] `render.end_card`:** 1.5s card on brand primary color with logo + restaurant name + price (omit price if null); built as an ffmpeg lavfi/overlay segment.
- [x] **85. [P0] `render.assemble`:** single ffmpeg graph: visuals + subtitles burn-in + voiceover + music at −18 dB ducked via `sidechaincompress` + end card; encode H.264 `-preset veryfast -crf 23`, AAC 128k, `-movflags +faststart`; 90s timeout via `asyncio.create_subprocess_exec`; non-zero exit → log stderr tail → retry once with safe preset (`-preset ultrafast`, no sidechain); missing music → skip music input; captions-only when no voice. Verify output ≤ 10 MB at 15s, 720×1280.
- [x] **86. [P0] Poster extraction:** frame at t=1.0s to `data/media/posters/<video>.jpg`; compute duration/bytes with `ffprobe`.
- [x] **87. [P0] `queue.py`:** `asyncio.Queue` + 2 workers started on app startup; job stage state machine writing `stages_json` transitions (pending → running → done/failed/skipped with timestamps and notes); graceful handling of worker exceptions (mark job failed with stage + error); on app restart, mark orphaned `running` jobs as `failed (server_restarted)`.
- [x] **88. [P0] Stage runners wired into the machine** analyze → [needs_dish] → script → visuals (free path only for now) → voice → assemble → create `Video` row, set `Job.cost_cents`, `status=done`, `finished_at`.
- [x] **89. [P0] `POST /jobs`:** validate payload by mode (`photo` needs `photo_asset_id`; `insight` needs `insight_id` and resolves menu item + photo + angle; `menu` needs `menu_item_id` with a photo); in demo mode force `veo=false`; return 202 `{job_id}`; enqueue.
- [x] **90. [P0] `GET /jobs/{id}`:** full status shape (stages, analyze, script, veo_used, fallback_reason, video `{id,url,poster_url}`, cost_cents, error); 404 handling.
- [x] **91. [P0] Videos router:** `GET /videos`, `GET /videos/{id}` (include dish name, mode, cost, publish fields, poster URL).
- [x] **92. [P0] Real-run smoke test with 3 photos** (biryani + 2 others) through `MOCK_PIPELINE=0`: check render time < 45s on local machine, captions correct, audio audible, end card present, file ≤ 10 MB. Fix issues.
- [x] **93. [P0] Unit/integration tests (pytest):** normalize_name, script validator (rejects wrong price, accepts correct), template_script validity, CSV menu import edge cases, upload rejection cases, job state machine with fake gemini/tts/ffmpeg.
- [ ] **94. [P0] Deploy live-mode backend (free mode)**; run one end-to-end job on the deployed host; record render time. Check disk persistence across a redeploy.
- [ ] **95. [P0] Switch frontend to live backend** (no code change; just `NEXT_PUBLIC_API_URL`); run the core loop (photo → Short) on a phone.
- [ ] **96. [P0] ★ CHECKPOINT 1:** core loop works live end to end in free mode on the deployed URL, 0 crashes across 5 consecutive runs. If not, stop and fix before anything else.

## Section 8 — Eval Harness (the technical claim)

- [ ] **97. [P0] Build `eval/cases.json`:** 12 photo cases (`photo`, `menu_row{name,price,description}`, `expected{name,price}`) covering varied dishes, ≥1 null-price case, ≥1 long name; 8 sales cases (`csv_slice`, `expected_top_seller`, `expected_rising`).
- [x] **98. [P0] Baseline generator:** same Gemini model, photo only, prompt "write a short promo script for this dish" — no menu row, no rules; returns voiceover + captions text.
- [x] **99. [P0] Grounded generator:** call the production `write_script` path (including validation + repair) with each case's menu row.
- [x] **100. [P0] Scoring functions:** `name_ok` (normalized name in voiceover/captions), `price_ok` (every `$x.xx` equals menu price; none mentioned when price null; invented price fails), `no_invented_claims` (regex `%|off|discount|award|best in|gluten|vegan|allergen|healthy` not in the menu description + LLM-judge yes/no), `pass = all three`.
- [x] **101. [P0] Sales scoring:** run `insights.py` ranking on each CSV slice, compare picks to expected.
- [x] **102. [P0] `run_eval.py` output:** per-case table (case, baseline pass/fail+reason, grounded pass/fail+reason), summary line `grounded X/20 · baseline Y/20 · sales picks Z/8`, written to `eval/results.md`; deterministic (temperature low, seeds noted); rate-limit-safe (sleep/backoff).
- [ ] **103. [P0] Run the eval and inspect failures;** if grounded < 19/20, fix prompt/validator (not the cases) and rerun; commit `eval/results.md`. Record the real baseline number for the demo script blank.
- [x] **104. [P0] Budget-guard visible test** (see Section 10) wired into `make test` so the "blocks 11th clip" claim is demonstrable.

## Section 9 — Insights Pillar

- [x] **105. [P0] CSV parser for sales:** column alias mapping (`date|Date|order_date|business_date`, `item_name|Item|item|menu_item|Item Name`, `quantity|Qty|qty|count|Quantity Sold`, `revenue|Net Sales|net_sales|amount`); mixed date formats; drop empty/invalid rows and negative quantities (refunds) with a `dropped` count; parse revenue to cents.
- [x] **106. [P0] Menu matching for sales rows:** exact → normalized → `rapidfuzz` ratio ≥ 85; set `menu_item_id`; collect `unmatched_items` list (distinct raw names).
- [x] **107. [P0] `POST /sales/import`:** replaces/appends sales (decide: replace for the single restaurant, documented in contract), returns `{rows, dropped, date_from, date_to, unmatched_items}`; invalidates existing insights.
- [x] **108. [P0] `insights.py` ranking (pure Python):** windows anchored to the max date in the data; Top seller = max `qty_7d`; Rising = max `wow_pct` among items with `qty_7d ≥ 10` and `qty_prev ≥ 3`; Slow mover = min `qty_14d` among items with a photo, excluding other picks; <14 days of data → Top seller only; always return distinct items.
- [x] **109. [P0] Insight reasons:** one Gemini call returns three one-sentence reasons given metrics (must only use provided numbers); on failure/timeout (20s) → rule-based templates ("Up 32% vs last week with 84 sold."); store `reason_source`.
- [x] **110. [P0] `GET /insights` and `POST /insights/refresh`:** return `{batch_id, cards:[...]}` per contract; persist `Insight` rows with `batch_id`; `GET` returns the latest batch, computing on first call; in mock mode serve `seed/mock_insights.json`.
- [x] **111. [P0] Insights unit tests:** seeded CSV yields biryani as Rising with ≈ +30%, expected Top seller and Slow mover; edge cases (<14 days, refunds, aliases, unmatched).
- [x] **112. [P0] Insight → Job path:** `POST /jobs {mode:"insight", insight_id}` resolves item/photo/angle (backend side of cross-link 1); angle flows into `write_script`; test with seeded insight.
- [x] **113. [P0] Connect Insights page to live data;** verify upload of the seeded CSV, an alias-header CSV, and a bad CSV (clear error).
- [x] **114. [P0] Verify Make video → Studio pre-fill → Generate** works end to end with live data (the signature moment).

## Section 10 — Budget Guard & Veo

- [x] **115. [P0] `budget.py`:** `reserve_veo(restaurant, job, seconds)`, `commit(job)`, `release(job)` per §5.2; all checks + insert in one SQLite transaction (`BEGIN IMMEDIATE`); deny reasons `free_mode|daily_limit|monthly_cap|demo_mode`; month computed from ledger date; est cents = seconds × `veo_cost_per_sec_cents`.
- [x] **116. [P0] Budget tests:** with limit 10 the 11th reserve is denied; monthly cap denies when `month + est > cap`; released rows don't count; two concurrent reservations at limit-1 → exactly one wins (threaded test); free_mode denies.
- [x] **117. [P0] `GET /usage` and `PATCH /settings`:** usage shape per contract; settings validation (limit 0–50, cap 0–10000¢, bool free_mode); demo mode may not PATCH (403).
- [x] **118. [P0] `veo.py` `generate_clip`:** submit image-to-video (photo + `veo_prompt`, aspect 9:16, 8s, 720p, `VEO_MODEL`); poll long-running op every 5s up to 180s; download MP4; validate non-empty/decodable via ffprobe; raise typed `VeoError(kind: timeout|blocked|api|corrupt|rate_limit)`.
- [x] **119. [P0] Visuals stage Veo branch:** if `veo_requested && !demo && budget.reserve_veo(...)` allow → run Veo → success → commit ledger + record `cost_cents`; any failure → release ledger → free Ken Burns path with `fallback_reason` (`veo_timeout|veo_blocked|veo_error|daily_limit|monthly_cap|free_mode|demo_mode`) and stage note.
- [x] **120. [P0] Veo + tail composition:** 8s Veo clip + 7s Ken Burns tail (same photo) crossfaded for 15s videos (and 8s + 22s tail for 30s); normalize Veo clip to 720×1280, 30fps; handle Veo audio by dropping it.
- [ ] **121. [P0] Veo prompt quality pass:** craft `veo_prompt` guidance in the script prompt (subtle steam, slow push-in, no text overlays, no people/hands to avoid safety blocks); test on 3 dishes and pick the best template.
- [ ] **122. [P0] Real paid Veo end-to-end test** through the pipeline (one job); confirm cost recorded equals reserved estimate; confirm usage meter increments.
- [ ] **123. [P0] Failure drills:** (a) force Veo timeout via env override → falls back, ledger released, badge shown; (b) kill network to Veo → falls back; (c) hit daily limit → falls back with reason.
- [x] **124. [P0] Wire Veo toggle + usage meter to live data;** verify the toggle disables with the correct reason in each denied state and the stepper shows the fallback badge.
- [ ] **125. [P0] `DEMO_CACHE` hero render:** generate the biryani Veo Short once for real; save to `seed/hero_veo_short.mp4` (+ poster); implement `DEMO_CACHE=1` so a Veo job for the seeded biryani item runs the mock timeline then returns the cached video and a plausible cost entry without a paid call (flag it internally, never claim live in the UI copy beyond normal behavior).
- [x] **126. [P0] Poll mock timeline for cached path:** realistic stage times (~8s total) with script content from the cached run so the script panel is real.

## Section 11 — YouTube Publishing

- [x] **127. [P0] OAuth start/callback:** `/youtube/auth/start` builds the consent URL (`access_type=offline`, `prompt=consent`, scopes upload+readonly, signed `state`); `/youtube/auth/callback` exchanges code, fetches channel id/title via `channels.list(mine=true)`, encrypts and stores refresh token, redirects to `/settings?youtube=connected`; on failure redirect with `?youtube=error`.
- [x] **128. [P0] Token refresh:** build credentials from the stored refresh token on demand; auto-refresh; if refresh fails mark disconnected and return `youtube_reconnect_required` (non-retryable).
- [x] **129. [P0] `youtube.upload`:** `videos().insert(part="snippet,status", media_body=MediaFileUpload(resumable=True, chunksize=8MB))`; category 26; description + hashtags with `#Shorts`; privacy from request; progress callback; retry ×3 with backoff on transient errors.
- [x] **130. [P0] `POST /videos/{id}/publish`:** 202 `{publish_status:"publishing"}`; background upload; on success store `youtube_id`, `youtube_url`, read back actual `status.privacyStatus` into `youtube_privacy`, `publish_status=published`; on failure `failed` with error code; map `quotaExceeded` → "Daily YouTube upload limit reached, try tomorrow"; block in demo mode (403 `demo_mode`); not-connected → 409 `youtube_not_connected`.
- [x] **131. [P0] Publish failure-path tests** with a mocked YouTube client: expired token, interrupted upload, quota exceeded, missing video ID.
- [x] **132. [P0] Fallback for demo:** if publish fails in demo-cache path, the seeded biryani Video has a pre-set `youtube_url` of a real pre-uploaded video; document how to publish it once on the team channel and paste the URL into `seed.py`.
- [ ] **133. [P0] Real publish test from the deployed backend** (not just local): connect the team YouTube channel, publish the hero video, open on a phone, note actual privacy; set the seeded `youtube_url`.
- [x] **134. [P0] Wire Library publish + Settings connect to live backend;** verify polling to `published`, link opens, restricted note shows when `youtube_privacy` is private/unlisted.
- [ ] **135. [P0] OAuth consent screen config** in Google Cloud (app name What's Cooking?, logo, privacy/TOS URLs placeholder pages, test users added); redirect URI = deployed backend callback URL.

## Section 12 — Brand Application

- [x] **136. [P0] Apply brand kit in render:** caption primary/accent colors, end-card background/logo/name, TTS voice from `Restaurant.tts_voice`, voice tone into the script prompt; test with two different brand kits and confirm visible differences.
- [x] **137. [P0] Logo handling:** transparent PNG scaled to fit end card; fallback to name-only end card if no logo.
- [x] **138. [P0] Caption preview in Settings** must visually match the render (same colors, bold Oswald, positioning); adjust until a side-by-side check looks equivalent.

## Section 13 — Checkpoint 2 Gate

- [ ] **139. [P0] End-to-end full demo path on the deployed URL:** Insights → Make video → Studio (Veo on, presenter token) → stages → Short → Publish → open YouTube on phone → Library → Settings meter → free mode flip → same dish in free mode.
- [ ] **140. [P0] Measure and record metrics:** free-mode render time (< 45s), Veo mode p90 (< 150s), cost per Veo video, 0 crashes across 10 runs on the demo path. Put in README.
- [ ] **141. [P0] Outsider test:** one person who has never seen it completes the core loop on the public URL on a phone in < 2 minutes with no help; log where they hesitated; fix top 3 friction points.
- [ ] **142. [P0] ★ CHECKPOINT 2:** every pillar works on real data, eval result committed, outsider test passed, hero Veo cached, YouTube link real. Cut per the cut order if anything is red.

## Section 14 — Polish & Hardening (P1, only after Checkpoint 2)

- [x] **143. [P1] Stage transitions & motion:** animated check marks, script lines streaming/fading in, button press states, skeleton shimmer, smooth page transitions; respect `prefers-reduced-motion`.
- [x] **144. [P1] Player polish:** poster-first loading, gold glow only while playing, unmute affordance animation, graceful video load error.
- [x] **145. [P1] Typography/spacing audit** on every page: Oswald for headings/numbers, JetBrains Mono for cost/usage figures, consistent 8px grid, contrast ≥ 4.5:1 for body text on `panel`.
- [x] **146. [P1] Toasts for all async outcomes** (upload done, job done, published, errors).
- [x] **147. [P1] Performance:** JS ≤ 250 KB gzipped per route (check `next build` output), lazy-load PublishDialog/Modal, `next/image` for posters, verify FCP ≤ 1.5s on throttled 4G in Lighthouse.
- [x] **148. [P1] Accessibility basics:** keyboard focus rings, `aria-live` on stepper, labelled form fields, alt text, video controls reachable.
- [x] **149. [P1] S5 styles:** Warm and Minimal ASS templates + pacing (durations, font size, positions) + prompt tone variants; enable in the UI (UI enabled in task 150).
- [x] **150. [P1] Enable Warm/Minimal in OptionsBar** once backend supports them.
- [x] **151. [P1] 30s length support:** script budgets (75 words, beat seconds), Veo 8s + 22s tail, music loop/trim; verify ≤ 20 MB or compress; enable in the UI.
- [x] **152. [P1] Enable 30s option** and show estimated render time.
- [x] **153. [P1] Regenerate a single beat:** endpoint to regenerate one caption beat (re-validate, re-render only assemble); plus a "Regenerate" button on a beat in `ScriptPanel`.
- [x] **154. [P1] Publish dialog edit polish:** character counters (title ≤ 70), hashtag chips editor, privacy explainer.
- [x] **155. [P1] Unmatched-item mapping UI support:** `PATCH` endpoint mapping a raw item name to a menu item; plus a small mapping UI in Insights listing unmatched items.
- [x] **156. [P1] Per-video cost receipt:** Gemini calls (token estimates), Veo seconds × rate, total; plus show in Library tile detail.
- [x] **157. [P1] Logging & observability:** structured logs per job (job id, stage, durations, fallback reasons), ffmpeg stderr tail on failure, request IDs in error responses.
- [x] **158. [P1] Cleanup & limits:** cap upload storage (delete orphaned assets/old clips > N days), simple rate limit on `POST /jobs` per IP in demo mode to protect the free Gemini tier.
- [x] **159. [P1] Gemini caching:** cache analyze/script by `(photo hash, menu row hash, angle, tone, length)` to reduce free-tier calls during rehearsals.
- [x] **160. [P1] Security pass:** no secrets in repo, `.env` ignored, CORS locked to frontend origin, upload type/size checks, path traversal check on media routes, refresh token encrypted, `OWNER_TOKEN` compared in constant time.
- [ ] **161. [P1] Stretch eval:** expand to 40–50 cases, add second baseline (menu text but no structured output/validation), add failure-case table to `eval/results.md`.
- [ ] **162. [P1] Real evidence:** show a generated Short to 3–5 restaurant owners/staff, log reactions in `docs/feedback.md`; find one sourced statistic on short-form video and restaurant discovery for the pitch.
- [ ] **163. [P2] YouTube view counts → Insights** (`videos.list` statistics → `Video.views`; show on insight cards) — the Library → Insights cross-link.
- [ ] **164. [P2] Scheduling, multiple music tracks, day/time sales patterns, Instagram/TikTok** — leave out unless everything above is done.

## Section 15 — Documentation

- [x] **165. [P0] README:** what it is, screenshots/GIF, architecture diagram (from §1), setup steps (backend, frontend, env vars, `make` targets), mock vs live switches, demo mode vs owner token.
- [ ] **166. [P0] README cost-control section:** all 3 layers (prepaid credits auto-reload off, AI Studio monthly cap ~20% below limit, in-code `UsageLedger` guard) + billing-lag note + screenshots.
- [x] **167. [P0] README "How we used AI" section:** Gemini (vision, structured script, insight reasons), Veo (image-to-video), Claude Code in building, edge-tts; what's grounded vs generated; the eval result.
- [x] **168. [P0] README honest-limits section:** unaudited YouTube app keeps uploads private; free-tier data caveat; edge-tts unofficial; CSV aliases tested against which exports; Veo model deprecation note.
- [x] **169. [P0] Commit `eval/results.md` and link it in the README;** include one-line pitch result.
- [x] **170. [P0] Music/photo licensing notes** in README.

## Section 16 — Final Deployment & Demo Readiness (CP3)

- [ ] **171. [P0] Production env review:** all variables set on host (including `DEMO_MODE=1`, `DEMO_CACHE=1`, `MOCK_PIPELINE=0`, `MOCK_FAIL_RATE=0`), `OWNER_TOKEN` stored in password manager, `APP_SECRET` generated and backed up, persistent volume verified, redeploy doesn't wipe data.
- [ ] **172. [P0] Run `seed.py` on production** and verify Kumar's loads: menu, photos, sales, brand kit, 2–3 seeded videos (one with real YouTube link), hero cache present.
- [ ] **173. [P0] Production frontend:** correct `NEXT_PUBLIC_API_URL`, no console errors, favicon + title "What's Cooking?", OG image/meta so a shared link looks right.
- [ ] **174. [P0] "Submitted and running" checklist** (each verified on the public URL from a phone, not your laptop): (a) loads Kumar's with no login, (b) a free-mode job completes live, (c) `DEMO_CACHE` hero Veo job plays, (d) ≥1 video published on the team's YouTube channel with the link shown, (e) `eval/results.md` committed, (f) README complete.
- [ ] **175. [P0] Cold-start/uptime check:** if the host sleeps on idle (free tiers), set up a keep-alive ping or upgrade the plan for the demo window; load `/health` 5 minutes before presenting.
- [ ] **176. [P0] Backup plan:** screen-record a perfect full demo run (with audio) and keep it locally and on the phone; save direct links to the hero video and published YouTube video; keep local `make back`/`make front` ready on a laptop.
- [ ] **177. [P0] Budget safety before demo day:** confirm ledger shows current daily limit headroom, credits balance is sufficient, AI Studio cap in place; set daily limit to a low number for the presenter session.

## Section 17 — Demo Rehearsal (CP3)

- [ ] **178. [P0] Fill the blanks in the demo script** (`demo_design.md` §8): real baseline score (`__/20`), actual cost (e.g., 64¢), actual WoW % and units from seeded data, real elapsed times. Update the file.
- [ ] **179. [P0] Prepare the eval proof visual:** one slide or in-app panel showing `grounded 20/20 · baseline Y/20` with one concrete baseline failure example (wrong/invented price or claim) vs. the grounded output.
- [ ] **180. [P0] Rehearse the 90-second script ≥ 5 times** with a timer; assign who clicks and who talks; mark exact stage timings; rehearse the "let it play 6 seconds of silence" beat and the phone-hold moment.
- [ ] **181. [P0] Rehearse failure recovery:** Veo slow → switch to cache narration; publish fails → show seeded link; Wi-Fi drops → play backup recording; know the one-line cover for each.
- [ ] **182. [P0] Prepare a Q&A sheet:** cost per video and caps, how grounding is enforced and measured, YouTube audit limits, how it plugs into Toast/Square/Clover, what happens if Veo fails, privacy of sales data (free-tier caveat), differentiator vs LLMSoftware's own menu-to-video feature.
- [ ] **183. [P0] Final phone run on cellular data** of the full demo path, twice, on the exact device/browser to be used; fix anything flaky.
- [ ] **184. [P0] ★ CHECKPOINT 3 / SUBMIT:** freeze code (tag `v1.0`), re-run the §174 checklist, submit the URL, repo, and demo video/backup per the event instructions.

## Section 18 — Post-Demo Follow-up (P1)

- [ ] **185. [P1] Send LLMSoftware a follow-up** with the live URL, eval result, a 30-second screen recording, and an offer to walk through plugging it in as a module (stated goal: "LLMSoftware asks for a follow-up call").
- [ ] **186. [P1] Capture lessons and next steps** (POS connectors, multi-platform autopilot, performance loop) in `docs/roadmap.md` from the Future Expansion section.
