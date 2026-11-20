# What's Cooking? — API Contract

Source of truth for the REST API between `frontend/` and `backend/`. TypeScript mirror: `frontend/lib/types.ts`.
Serializers: `backend/app/serializers.py`. Change this file deliberately and prefix the commit with `CONTRACT:`.

## Conventions

- Base URL: `NEXT_PUBLIC_API_URL` (e.g. `https://whats-cooking-api.onrender.com`). JSON everywhere except multipart uploads.
- Media files (`url`, `poster_url`, `photo_url`, `logo_url`) are absolute URLs under `/media/*`.
- Timestamps are ISO-8601 UTC with `Z`.
- **Errors** (every non-2xx):
  ```json
  {"error": {"code": "snake_case", "message": "Human readable.", "retryable": false}}
  ```
  Common codes: `validation_error` (422), `not_found` (404), `demo_mode` (403), `bad_owner_token` (401),
  `file_too_large` (413), `bad_mime` / `bad_image` (415), `bad_csv` (400), `photo_required` (400),
  `youtube_not_connected` (409), `budget_cap_reached` (402), `rate_limited` (429, retryable), `admin_required` / `settings_locked` (403), `workspace_required` (400),
  `internal_error` (500, retryable).

## Studios (one per browser)

Every request carries `X-Workspace: <32 hex>`, a random id the browser makes once and keeps in `localStorage`.
The server gives each id its own restaurant (name, logo, colors, dishes, sales, insights, jobs, videos), copied
from the seeded demo template on first use; the template's dish photos are shared. Without the header, reads see
the template, and writes get 400 `workspace_required` unless they carry a valid owner or admin token.
The AI budget (`/usage`, `/settings`, ledger) is one pot shared by all studios.

## Sign-in (Google, optional)

`GET /auth/google/url?nonce=` → `{url}` (scopes openid/email/profile; shares the YouTube redirect URI, the signed
state says which flow). The callback redirects to `/?signin=ok#session=<encrypted token>&n=<nonce>`; the browser
keeps the session only if `n` matches its own nonce, then sends it as `X-Session` (90 days). `GET /auth/me` →
`{account: {id, email, name, picture} | null}`. Signed in, every request uses the account's studio (first sign-in
claims this browser's guest studio; same studio on every device). Signing out = the browser forgets the session
and starts a new guest studio. Errors redirect to `/?signin=error&reason=…`.

## Auth

| Request | Actor |
|---|---|
| `X-Owner-Token` equals `OWNER_TOKEN` | **owner**: everything |
| `X-Owner-Token` present but wrong | 401 `bad_owner_token` |
| No token, `DEMO_MODE=1` | **demo**: read-only + free-mode generation. AI motion forced off, publishing/settings/brand/sales import → 403 `demo_mode`. Job creation rate-limited per IP |
| No token, `DEMO_MODE=0`, `OWNER_TOKEN` set | 401 |
| No token, no `OWNER_TOKEN` configured | owner (local dev) |

The frontend stores the owner token in `localStorage` after a one-time unlock.

**Budget settings** (`PATCH /settings`) need `X-Admin-Token` equal to `ADMIN_TOKEN` (403 `admin_required`; 403
`settings_locked` if the server has none). The web app never sends it. Spend is also capped in code at $10/month.

**Fair use** (no login on the public app): job creation (`POST /jobs`, `/retry`, `/edit`) allows one video in progress
and `JOBS_PER_HOUR_PER_IP` (6) per visitor IP, and refuses when `MAX_QUEUED_JOBS` (4) are already queued/running →
429 `rate_limited` with a human message. A valid `X-Owner-Token` skips these.

**YouTube is per visitor:** the OAuth callback hands the visitor's browser an encrypted connection (URL fragment
`#yt=…&n=<nonce>`, Fernet with `APP_SECRET`). The browser starts the flow with a random `nonce` and keeps the
connection only if the returned `n` matches, so nobody can plant their own channel in someone else's browser. The browser keeps it in `localStorage` and sends it as `X-YouTube-Auth`; the server
stores none. `/restaurants/me` reports `youtube_connected` / `youtube_channel_title` for *that* visitor, and
`POST /videos/{id}/publish` uploads to *their* channel.

## Endpoints

| Method & path | Who | Request | Response |
|---|---|---|---|
| GET `/health` | any | — | `{ok, mock, demo, actor:"owner"\|"demo", veo_model, gemini_model, gemini_configured, youtube_configured}` |
| GET `/restaurants/me` | any | — | `Restaurant` |
| PATCH `/restaurants/me` | owner | partial `{name?, color_primary?, color_accent?, voice_tone?, tts_voice?, logo_asset_id?}` | `Restaurant` |
| POST `/menu/import` | owner | multipart `file` (CSV `name,price,description,category`) | `{imported, skipped}` (upserts by normalized name) |
| GET `/menu` | any | — | `MenuItem[]` |
| POST `/uploads` | any (logo: owner) | multipart `file`, `kind` = `photo`\|`logo` | `{asset_id, url, width, height}`. Rejects > 10 MB (413) or non JPG/PNG/WEBP (415). Photos are EXIF-rotated and stored as JPEG |
| POST `/menu/{id}/photo` | owner | `{asset_id}` | `MenuItem` |
| POST `/dishes` | owner | `{name, price?: "11.50", description?, photo_asset_id}` | `MenuItem` (upsert by name; the quick-take dashboard uses this, then `POST /jobs` with `mode:"menu"`) |
| POST `/sales/import` | owner | multipart `file` (CSV) | `{rows, dropped, date_from, date_to, days, unmatched_items:[str]}`. **Replaces** previous sales and recomputes insights |
| GET `/sales/summary` | any | — | `{rows, date_from, date_to, days?, unmatched_items}` |
| GET `/insights` | any | — | `{batch_id, cards: InsightCard[]}` (computed on first call if sales exist) |
| POST `/insights/refresh` | owner | — | same as GET |
| GET `/insights/{id}` | any | — | `InsightCard` |
| POST `/jobs` | any (fair-use limits) | `{mode:"photo"\|"insight"\|"menu", photo_asset_id?, menu_item_id?, insight_id?, style:"bold"\|"warm"\|"minimal", length_s:8\|15\|30 (default 8), veo:bool, storyboard?: Storyboard, format?: "classic"\|"money_shot"\|"chef_pov" (default classic)}` (`storyboard` = Director mode: mode `menu`, 8 s; re-validated, 422 `not_grounded` if it doesn't match the menu; the script stage is skipped) | **202** `{job_id}`. **402 `budget_cap_reached`** if `veo:true` would exceed the daily limit or monthly cap (message says how much is left) |
| POST `/director/plan` | any (60/h per visitor) | `{menu_item_id, message?: str ≤400, storyboard?: Storyboard, history?: [{role:"user"\|"assistant", text}] ≤24, format?}` | `{storyboard: Storyboard, reply, suggestions:[str×3], source:"gemini"\|"unchanged"\|"template"}`. No `message` = first plan. Plans pass the same grounding validator as scripts; a request that would break it keeps the current storyboard (`unchanged`) and `reply` says why |
| POST `/director/preview` | any (10/h per visitor, 40/day total) | `{menu_item_id, storyboard}` | `{url}`: a 9:16 still of the planned shot (image model, a few cents). 503 `ai_unavailable` without Gemini; 502 `preview_failed` (retryable) |
| GET `/jobs` | any | `?status=active` → queued/running/needs_dish only | `Job[]` (newest first, max 30) |
| GET `/jobs/{id}` | any | — | `Job` |
| POST `/jobs/{id}/confirm-dish` | any | `{menu_item_id: int \| null, continue_anyway?: bool}` | `{ok:true}`. Resumes a `needs_dish` job. `null` = "Not on menu" (script omits price) |
| POST `/jobs/{id}/retry` | any | — | **202** `{job_id}` (new job, same inputs) |
| GET `/videos` | any | — | `Video[]` newest first (videos whose file was lost in a host restart are left out) |
| GET `/videos/{id}` | any | — | `Video` |
| POST `/videos/{id}/publish` | owner | `{title, description, tags:[str], privacy:"private"\|"unlisted"\|"public"}` | **202** `{publish_status:"publishing"}`. Poll `/videos/{id}` (`publish_progress` 0–100) |
| GET `/youtube/auth/url` | any | `?nonce=` (16–64 chars `[A-Za-z0-9_-]`, made and kept by the browser) | `{url}` Google consent URL (frontend navigates to it). Any visitor can connect their own channel |
| GET `/youtube/auth/callback` | Google | `code, state` | 302 → `{FRONTEND_ORIGIN}/?youtube=connected#yt=<encrypted connection>&n=<nonce>` (or `/?youtube=error&reason=…`) |
| POST `/youtube/disconnect` | any | — | `{ok:true}`. Nothing is stored server-side; the browser forgets its connection |
| GET `/youtube/uploads` | visitor | `X-YouTube-Auth` | `{channel_title, videos:[{id, title, url, published_at, thumbnail, privacy}]}`: the visitor's videos made with the app (description tag `#WhatsCookingApp`), read live from their channel. 409 `youtube_not_connected` |
| GET `/usage` | any | — | `Usage` |
| GET `/settings` | any | — | `Settings` |
| PATCH `/settings` | admin (`X-Admin-Token`) | `{daily_veo_clip_limit? 0–20, monthly_cap_cents? 0–1000, free_mode?}` | `Settings` |

`POST /jobs` rules: `photo` needs `photo_asset_id` (optional `menu_item_id` skips matching); `insight` needs
`insight_id` (dish, photo and angle come from the insight; pass `photo_asset_id` if the dish has no photo);
`menu` needs `menu_item_id` (same photo rule). Demo viewers always get `veo:false` server-side.

## Shapes

```ts
Restaurant { id, name, slug, logo_asset_id, logo_url, color_primary:"#RRGGBB", color_accent, voice_tone:"friendly"|"upbeat"|"elegant",
             tts_voice, menu_count, has_sales, youtube_configured, youtube_connected (this visitor), youtube_channel_title, voices:[{id,label}],
             demo_name, demo_logo (this studio still uses the demo's name / logo) }

MenuItem { id, name, price_cents|null, price:"$14.99"|null, description|null, category|null, photo_asset_id|null, photo_url|null }

InsightCard { id, angle:"top_seller"|"rising"|"slow_mover",
              menu_item:{id, name, price, photo_url},
              metric:{qty_7d, qty_prev_7d?, wow_pct?, qty_14d?}, metric_label:"+32% WoW · 83 sold",
              reason, reason_source:"gemini"|"rule" }

Stage { name:"analyze"|"script"|"visuals"|"voice"|"assemble", status:"pending"|"running"|"done"|"failed"|"skipped",
        started_at|null, ended_at|null, note|null }

Job { id, status:"queued"|"running"|"needs_dish"|"done"|"failed", mode, angle|null, style, length_s, veo_requested,
      stages:Stage[5],
      analyze: null | {is_food, dish_guess, menu_item_id, confidence, visual_notes, quality, warning?,
                       reason?:"not_food"|"low_confidence"|"analyze_failed", candidates: MenuItem[] (only while needs_dish)},
      script: null | Script, menu_item: MenuItem|null, photo_url,
      veo_used, fallback_reason: null|"free_mode"|"daily_limit"|"monthly_cap"|"demo_mode"|"veo_timeout"|"veo_blocked"|"veo_error"|"veo_rate_limit"|"veo_unavailable",
      flags:{demo?, not_on_menu?, continue_anyway?, captions_only?},
      video: null | {id, url, poster_url}, cost_cents, error|null, error_stage|null, created_at, finished_at|null }

Script { hook (≤8 words), beats:[{caption (≤2 lines × ≤22 chars), seconds, facts?:["name"|"price"|"description"]}],
         voiceover (≤38 words @15s, ≤75 @30s), veo_prompt, title (≤70), description, hashtags (≤5),
         facts_used:[{field:"name"|"price"|"description", value}], source:"gemini"|"gemini_repaired"|"template" }

Video { id, job_id, url, poster_url, dish, menu_item_id, duration_s, width, height, bytes, mode:"veo"|"free", cost_cents,
        title, description, hashtags, youtube_id|null, youtube_url|null, youtube_privacy|null,
        publish_status:"draft"|"publishing"|"published"|"failed", publish_error|null, publish_progress, created_at }

Usage { today:{clips, limit}, month:{est_cents, cap_cents}, cost_per_sec_cents, free_mode, ai_videos_left, ai_videos_total,
        veo:{allowed, reason|null, message|null, est_cents} }   // "veo" = AI motion (field names kept from the Veo era): what would happen if this viewer asked for it now

Storyboard { hook, beats:[{caption, seconds}], voiceover, shot (one plain sentence for the owner), veo_prompt, title, description, hashtags, facts_used }

Settings { restaurant_id, daily_veo_clip_limit, monthly_cap_cents, free_mode, veo_cost_per_sec_cents }
```

## Formats

| format | narrator | ending | sound |
|---|---|---|---|
| `classic` | yes | animated logo slate (last 2.3 s) | narrator over ducked music, AI-clip audio low |
| `money_shot` | no (`voiceover:""`, voice stage `skipped`) | full 8 s of motion, corner logo, name line, loops | the AI clip's own audio at full level; music only without AI motion |
| `chef_pov` | no | same as money_shot | same as money_shot |

`flags.format` on the job holds the format; retry keeps it.

## Job lifecycle

```
POST /jobs → queued → running: analyze → [needs_dish ⇄ POST confirm-dish] → script → visuals → voice → assemble → done
                                         any hard failure → failed (error, error_stage) → POST /jobs/{id}/retry
```
- Poll `GET /jobs/{id}` every 1.5 s until `done | failed | needs_dish`.
- `script` is filled as soon as the Script stage finishes (before the video exists).
- Visuals and voice **degrade instead of failing**: AI-motion problems → Ken Burns + `fallback_reason`;
  TTS problems → captions-only + `flags.captions_only`.

## Mock / demo switches (no frontend changes needed)

- `MOCK_PIPELINE=1`: stages walk on a timer (analyze 1.5 s, script 3 s, visuals 6 s / 12 s with AI motion, voice 1.5 s,
  assemble 2 s) and attach `seed/mock_short.mp4`. `MOCK_FAIL_RATE=0.1` fails a random stage. `MOCK_NEEDS_DISH=1`
  pauses photo jobs for the dish picker. `/insights` serves `seed/mock_insights.json`.
