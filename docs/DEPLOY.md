# Deploying your own copy

The live app runs on **Vercel** (website, free) + **Render** (API, free plan) + **Neon** (Postgres, free), with a
**Gemini API key** and one **Google OAuth client** (used for both Google sign-in and YouTube). About 45 minutes.

## 1. Gemini API key

1. **aistudio.google.com/apikey** → **Create API key**.
2. Turn on **billing** for that key's project (AI Studio → **Set up billing**). Without billing, text models work
   but no video model (Gemini Omni) is listed.
3. Recommended: **console.cloud.google.com → Billing → Budgets & alerts** → a budget with email alerts.
4. Check what your key can use: `GEMINI_API_KEY=... make models`. Set `VEO_MODEL` to a `gemini-omni-*` model.

## 2. Google OAuth client (sign-in + YouTube)

1. **console.cloud.google.com** → new project → **APIs & Services → Library** → enable **YouTube Data API v3**.
2. **Google Auth Platform → Get started**: app name, support email, Audience **External**.
3. **Data Access** → add scopes `openid`, `.../auth/userinfo.email`, `.../auth/userinfo.profile` (sign-in) and
   `.../auth/youtube.upload`, `.../auth/youtube.readonly` (posting).
4. **Clients → Create client → Web application** → Authorized redirect URI
   `https://<your-api>.onrender.com/youtube/auth/callback` (sign-in uses the same URI). Copy the Client ID and secret.
5. **Branding**: app name, support email, **Application home page** `https://<your-site>`, **Privacy policy**
   `https://<your-site>/privacy`, **Terms** `https://<your-site>/terms`, **Authorized domains** your site's domain,
   developer contact. Leave the logo empty (a logo triggers verification). **Save**.
6. **Let anyone connect:** **Audience → Publish app → Confirm**. Sign-in alone needs no review. Until the app is
   verified, connecting YouTube shows "Google hasn't verified this app" (**Advanced → Go to What's Cooking?**), and
   up to 100 people can connect.

## 3. Database (Neon, free)

Render's free disk resets on every restart, so everything lives in Postgres (including rendered videos, up to
`MEDIA_DB_CAP_MB`): **neon.tech** → **Create project** (region near the API, e.g. AWS US West 2 for Render Oregon)
→ **Connect** → pooled string (host has `-pooler`) → `DATABASE_URL`; direct string (pooling off) →
`DATABASE_URL_UNPOOLED`. Or from the repo: `neon init` + `neon deploy` (see `neon.ts`) pull both into `.env.local`.
Tables are created and upgraded on boot; the demo restaurant loads once.

## 4. API on Render

`render.yaml` describes the service. Either **New → Blueprint → this repo**, or a **Web Service** with **Runtime:
Docker**, **Dockerfile path** `./backend/Dockerfile`, **Docker context** `.`, plan **Free**, health check `/health`.
Set the env vars (`make secrets` prints random values for `APP_SECRET` and `ADMIN_TOKEN`):

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | step 1 |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | step 2 |
| `OAUTH_REDIRECT_URI` | `https://<your-api>.onrender.com/youtube/auth/callback` |
| `PUBLIC_BASE_URL` | `https://<your-api>.onrender.com` (https = production mode: the API refuses to start without `APP_SECRET`, and only listed origins get CORS) |
| `FRONTEND_ORIGIN` | your site URL(s), comma-separated. **The first one** is where sign-in and YouTube send people back |
| `APP_SECRET` | encrypts sessions and YouTube connections. Keep it stable: changing it signs everyone out and disconnects YouTube |
| `ADMIN_TOKEN` | unlocks budget settings (`/settings`); keep it private |
| `DATABASE_URL` / `DATABASE_URL_UNPOOLED` | step 3 |
| `FFMPEG_THREADS` | `2` (the default; ffmpeg's own default can run a 512 MB host out of memory) |

`render.yaml` also sets the low-CPU render settings (`RENDER_PRESET=ultrafast`, `KB_OVERSAMPLE=1`, timeouts).
**Changing an env var needs a new deploy** (Render → Manual Deploy), not just a restart.

First boot loads the demo restaurant (about 30 s). Check `https://<your-api>.onrender.com/health`.

**Keep it awake (optional):** a cron-job.org job hitting `/health` every 10 minutes during your hours avoids the
one-minute wake-up. Free instance hours are shared across your free Render services (750 h/month).

## 5. Website on Vercel

Import the repo with **Root Directory** `frontend`, framework **Next.js**, env
`NEXT_PUBLIC_API_URL=https://<your-api>.onrender.com`. Or from the CLI: `cd frontend && vercel deploy --prod`.
If visitors are asked to log in to Vercel, turn off **Deployment Protection** for production.

**Your address:** Vercel → Project → **Settings → Domains** → add `<name>.vercel.app` (free, if nobody has it) or a
domain you own. Then put it first in `FRONTEND_ORIGIN` (and redeploy the API), update the Google **Branding** links
(step 2.5) and `metadataBase` in `frontend/app/layout.tsx`. To move off an old address, set it to **redirect** (308)
to the new one in the same Domains screen.

**Shipping banner:** deploy with `vercel deploy --prod --build-env NEXT_PUBLIC_SHIPPING=1` to show "Shipping an
update" while the API redeploys, then deploy again without it.

## Budget

The AI-video budget is a **lifetime total** (never resets): every AI video is reserved before the call and recorded
in the ledger; `budget.HARD_CAP_CENTS` ($10) is the ceiling whatever the settings say. Settings, via
`PATCH /settings` with header `X-Admin-Token: $ADMIN_TOKEN`:

| Field | Meaning |
|---|---|
| `monthly_cap_cents` | the **total** cap (name kept for compatibility), 0–1000 |
| `spent_outside_cents` | spend not in the ledger (e.g. from real billing before the ledger existed); counts against the cap |
| `daily_veo_clip_limit` | AI videos per day, 0–20 (a speed limit, not money) |
| `free_mode` | `true` = no AI motion at all |

`veo_cost_per_sec_cents` (default 8, so ≈ $0.64 per 8 s video) is the estimate the ledger uses. Compare with real
billing now and then, and correct `spent_outside_cents`. Previews, mascots and Director chats aren't in the ledger;
they're limited by `DIRECTOR_PREVIEWS_PER_DAY`, `MASCOT_BATCHES_PER_DAY`, `DIRECTOR_PLANS_PER_DAY` and per-visitor
hourly limits (see `.env.example`).

```bash
curl -X PATCH https://<your-api>.onrender.com/settings -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d '{"spent_outside_cents": 534}'
```
