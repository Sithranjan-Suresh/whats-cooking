# Deploying your own copy

The live demo runs on **Vercel** (frontend, free) + **Render** (API, free plan), with a **Gemini API key** and a
**Google OAuth client** for YouTube. About 30 minutes end to end.

## 1. Gemini API key

1. **aistudio.google.com/apikey** → **Create API key**.
2. Turn on **billing** for that key's project (AI Studio → **Set up billing**). Without billing, text models work
   but no video model (Gemini Omni) is listed.
3. Optional: **console.cloud.google.com → Billing → Budgets & alerts** → a monthly budget with email alerts.
4. Check what your key can use: `GEMINI_API_KEY=... make models`. Set `VEO_MODEL` to a `gemini-omni-*` model.

## 2. YouTube (Google Cloud OAuth client)

1. **console.cloud.google.com** → new project → **APIs & Services → Library** → enable **YouTube Data API v3**.
2. **Google Auth Platform** (OAuth consent screen) → **Get started**: app name, support email, Audience **External**.
3. **Data Access** → add scopes `youtube.upload` and `youtube.readonly`.
4. **Clients** → **Create client** → **Web application** → Authorized redirect URI:
   `https://<your-api>.onrender.com/youtube/auth/callback`. Copy the Client ID and secret.
5. **Let anyone connect:** **Audience** → **Publishing status: Testing** → **Publish app** → **Confirm**.
   While the app is unverified, Google shows "Google hasn't verified this app": people click **Advanced → Go to
   What's Cooking? (unsafe)** → **Continue**. Up to 100 people can connect before Google requires verification.
   (Alternative: stay in Testing and add each person under **Audience → Test users**.)

## 3. API on Render

`render.yaml` describes the service. Either **New → Blueprint → this repo**, or create a **Web Service** from the repo
with **Runtime: Docker**, **Dockerfile path** `./backend/Dockerfile`, **Docker context** `.`, plan **Free**,
health check `/health`. Fill in the secret env vars (`make secrets` prints an `APP_SECRET`):

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | from step 1 |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | from step 2 |
| `OAUTH_REDIRECT_URI` | `https://<your-api>.onrender.com/youtube/auth/callback` |
| `PUBLIC_BASE_URL` | `https://<your-api>.onrender.com` |
| `FRONTEND_ORIGIN` | your Vercel URL(s), comma-separated |
| `APP_SECRET` | keep it stable: changing it disconnects everyone's YouTube |

First boot loads the demo restaurant automatically (about 30 seconds). Check `https://<your-api>.onrender.com/health`.

**Keep it awake (optional):** free Render services sleep after 15 idle minutes. A free cron-job.org job hitting
`/health` every 10 minutes during your working hours avoids the one-minute wake-up. Free instance hours are shared
across all your free Render services (750 h/month), so don't run it 24/7 if you host other free services.

## 4. Frontend on Vercel

Import the repo with **Root Directory** `frontend`, framework **Next.js**, env `NEXT_PUBLIC_API_URL=https://<your-api>.onrender.com`.
Or from the CLI: `cd frontend && vercel deploy --prod`. If the project asks for a Vercel login on visit, turn off
**Deployment Protection** for production.

## Budget

Settings live in the API (`PATCH /settings`): `daily_veo_clip_limit` (default 10), `monthly_cap_cents`
(default 1000 = $10), `veo_cost_per_sec_cents` (default 8, the estimate used for the cap). The page shows
"AI videos left" and switches to free photo motion when the budget is used up.
