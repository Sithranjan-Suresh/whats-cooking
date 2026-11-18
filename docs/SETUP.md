# Setup guide: the parts only a human can do

Everything else is built. These steps need your accounts, money or photos. Do them in this order; each one unlocks more.

| # | What | Unlocks | Time | Cost |
|---|---|---|---|---|
| 1 | Real dish photos + logo | Real-looking demo, meaningful eval | 15 min | $0 |
| 2 | Gemini API key (prepaid, capped) | AI scripts, photo matching, Veo, eval numbers | 15 min | prepay ~$10 |
| 3 | Google Cloud OAuth client for YouTube | Publishing | 20 min | $0 |
| 4 | Deploy backend (Render) | Public API | 15 min | ~$7/mo + disk |
| 5 | Deploy frontend (Vercel) | Public URL | 5 min | $0 |
| 6 | After deploy: hero video, publish once, eval, rehearse | Demo-ready | 30 min | ~$0.64 |

---

## 1. Real dish photos + logo

The seed currently uses **generated placeholder illustrations** (they say "PLACEHOLDER" across the top).

**What to collect** (JPG or PNG, ideally ≥ 1080 px on the short side, well lit, plate centered, no people or faces, photos you have the rights to):

| File name (exactly) | Dish |
|---|---|
| `chicken-biryani.jpg` | Chicken Biryani (**the hero dish**: pick the best photo you have) |
| `butter-chicken.jpg` | Butter Chicken |
| `palak-paneer.jpg` | Palak Paneer |
| `malai-kofta.jpg` | Malai Kofta |
| `tandoori-chicken.jpg` | Tandoori Chicken |
| `vegetable-samosa.jpg` | Vegetable Samosa |
| `garlic-naan.jpg` | Garlic Naan |
| `mango-lassi.jpg` | Mango Lassi |

Eval-only extras (4 more menu items, so the eval has 12 photo cases): `lamb-rogan-josh.jpg`, `chana-masala.jpg`,
`gulab-jamun.jpg`, `chefs-thali.jpg`.

Logo: `logo.png`, square, transparent background, ≥ 512 px.

Sources, if you don't have your own: the photos you used at the hackathon, your own phone photos of real dishes,
or free-license stock (Unsplash/Pexels license allows this use; note the photographer in the README).

**How to get them to me (pick one):**
- **Easiest:** drag all the files into this chat. I'll put them in `seed/photos/`, `eval/photos/` and `seed/logo.png`.
- **GitHub web:** open the repo on github.com → switch to branch `claude/tender-planck-2voogi` → open `seed/photos` →
  **Add file → Upload files** → drop the 8 dish photos → **Commit changes**. Do the same for `eval/photos` (4 files) and
  `seed/logo.png` (replace). Then tell me "photos are pushed".

## 2. Gemini API key (prepaid and capped *before* any Veo call)

1. Go to **https://aistudio.google.com** → sign in → **Get API key** → **Create API key** → choose or create a Google Cloud project
   (name it `whats-cooking`). Copy the key somewhere private. **Never paste it in chat.**
2. Turn on billing for Veo (Veo is paid-only): in AI Studio → **Billing** (or **Settings → Plan**) → set up billing for that project.
   - Choose **prepaid credits** if offered, add a small amount (e.g. $10), and **turn auto-reload OFF**. (Layer 1.)
3. Set a **project spend cap**: AI Studio → the project → **Spend** / **Usage & billing** → set a monthly cap about 20% *below* what you're
   willing to spend (e.g. $12 if your real limit is $15). Billing data lags ~10 min; the in-app guard is layer 3. (Layer 2.)
4. Take a screenshot of the auto-reload-off and spend-cap screens (for the README cost section, task 4).

**How to give it to me (so I can run the eval, the model check and the hero video in this session):**
- Tell me "ready for the Gemini key". I'll open a **secure credential form** in this session (it says
  `generativelanguage.googleapis.com`). Paste the key **into that form**, not into chat. The key never reaches me; the session's
  network proxy adds it to requests to Google. I then run `make models`, one `scripts/veo_smoke.py` clip (≈ $0.64), `make eval`
  and `make hero`.
- For the deployed server, you'll paste the same key into Render's env vars yourself (step 4).

## 3. YouTube publishing (Google Cloud OAuth client)

Use the same Google Cloud project as step 2 (**console.cloud.google.com**, project picker top-left).

1. **Enable the API:** APIs & Services → **Library** → search "YouTube Data API v3" → **Enable**.
2. **OAuth consent screen** (APIs & Services → **OAuth consent screen**, may be called "Google Auth Platform → Branding/Audience"):
   - User type: **External** → Create.
   - App name: `What's Cooking?` · support email: yours · developer contact: yours. (Logo optional; adding one can trigger review.)
   - **Scopes** (Data Access): add `.../auth/youtube.upload` and `.../auth/youtube.readonly`.
   - **Audience → Test users:** add the Google account that owns the YouTube channel you'll publish to. Leave the app in **Testing**.
3. **Credentials** → **Create credentials → OAuth client ID** → Application type **Web application** → name `whats-cooking-api`.
   - **Authorized redirect URIs:** add both
     - `http://localhost:8000/youtube/auth/callback`
     - `https://<your-render-service>.onrender.com/youtube/auth/callback` (add this after step 4, when you know the URL)
   - Create → copy the **Client ID** and **Client secret** (private, never in chat).
4. Make sure the channel exists: sign in to youtube.com with the test-user account → create a channel if you have none.

These go into Render's env vars (step 4): `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
`OAUTH_REDIRECT_URI=https://<your-render-service>.onrender.com/youtube/auth/callback`.

Expect uploads to come back **private**. That's YouTube's rule for unverified apps, and the app shows it. To make public
uploads possible later, submit the app for Google's verification/audit.

## 4. Deploy the backend (Render)

1. Sign up at **https://render.com** with GitHub, and allow it access to `whats-cooking`.
2. **New → Blueprint** → pick the repo → branch `claude/tender-planck-2voogi` (or `main` after you merge) → Render reads `render.yaml`.
3. Fill in the env vars marked "sync: false":
   - `GEMINI_API_KEY` (step 2), `GEMINI_TEXT_MODEL` and `VEO_MODEL` (I'll tell you the exact IDs after `make models`;
     until then use `gemini-2.5-flash` / `veo-3.1-fast-generate-preview`), `VEO_COST_PER_SEC_CENTS` (from the Veo pricing page for 720p).
   - `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `OAUTH_REDIRECT_URI` (step 3).
   - `APP_SECRET` and `OWNER_TOKEN`: run `make secrets` locally (or ask me to generate them: I'll print them only to a
     file you can open, not the chat), then paste them. **Save `OWNER_TOKEN` in your password manager**: it's how you unlock owner mode.
   - `PUBLIC_BASE_URL=https://<service>.onrender.com`, `FRONTEND_ORIGIN=https://<your-app>.vercel.app` (fill after step 5, then redeploy).
4. Plan: **Starter** (the free plan sleeps and has no persistent disk; the demo needs both). The blueprint attaches a 2 GB disk at `/data`.
5. Deploy. The first boot seeds Kumar's (~30 s). Check `https://<service>.onrender.com/health` → `{"ok":true,...}`.
6. Go back to Google Cloud → your OAuth client → add the Render callback URL (step 3.3).

(Railway or Fly.io work too: Docker build from `backend/Dockerfile` with context = repo root, a volume at `/data`, and the same env vars.)

## 5. Deploy the frontend (Vercel)

1. **https://vercel.com** → sign up with GitHub → **Add New → Project** → import `whats-cooking`.
2. **Root Directory:** `frontend`. Framework: Next.js (auto).
3. **Environment variable:** `NEXT_PUBLIC_API_URL=https://<service>.onrender.com`.
4. Deploy → copy the URL → set it as `FRONTEND_ORIGIN` on Render → redeploy Render.
5. Open the Vercel URL on your phone. It should land on Insights with Kumar's three cards and a "Demo mode" banner.

## 6. After deploy (I can do most of this with you)

1. **Owner unlock:** Vercel URL → Brand & Budget → paste `OWNER_TOKEN` → "Owner mode".
2. **Connect YouTube:** Brand & Budget → Connect YouTube → choose the test-user account → allow both permissions.
3. **Hero video:** once the key is in this session (step 2), I run `make hero` (one Veo clip, ~$0.64) and commit `seed/hero_veo_short.*`.
   To get it onto the server, redeploy Render. (The seed folder ships in the image; `DEMO_CACHE=1` then replays it.)
4. **Publish once:** Library → the hero video → Publish (Unlisted) → open the link on your phone. Then tell me the URL and I'll add
   `seed/published.json` so demo viewers see a "Published ↗" link.
5. **Eval:** I run `make eval` with your real photos and commit `eval/results.md`; the numbers go into the demo script.
6. **Rehearse** `demo_design.md` §8 on your phone over cellular data.

---

## What I need from you (summary)

1. The 12 dish photos + logo (step 1): drag into chat, or upload to GitHub.
2. Say "ready for the Gemini key" → paste it into the secure form (step 2). Never in chat.
3. Do steps 3–5 in your browser (Google Cloud, Render, Vercel), then send me the two public URLs.
