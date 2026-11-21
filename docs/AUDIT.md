# What's Cooking? — Launch audit (Nov 19, 2026)

Scope: every page and route (`/`, `/privacy`, `/terms`, 404), every component in `frontend/`, every API route in
`backend/app/routers/`, the pipeline, budget, studios (workspaces), database (Neon) and integrations (Gemini, Gemini Omni,
edge-tts, YouTube). Tested on the live site (Vercel + Render + Neon) in Chromium at 1440px, 768px, iPhone 13 and 360px,
plus locally against a copy of the server (same Docker image, 512 MB limit) and the backend test suite on SQLite and Postgres.

## Update — Nov 21, 2026

Shipped since this audit (all live at https://whatscookinghq.vercel.app; details in commit history):
**Director mode** (storyboard chat + preview frame) · **styles** Money shot / Chef POV / Classic (research-based:
payoff in the first second, kitchen sound, native captions, loops) · **mascot creator** · **Google sign-in** with
studios and YouTube on every device · **edit captions** (free re-render) · **videos survive restarts** · **$10
lifetime AI cap** (was per month by mistake; counts earlier spend) · **25-item security checklist**
([SECURITY.md](SECURITY.md)) · new address **whatscookinghq.vercel.app** (old one redirects). Tests: 97, on SQLite and
Postgres, with render tests also run in the Render image.

Still open: #11 paid hosting, #12 Google verification, #21 Content-Security-Policy, #23 delete video/studio,
#25 studio cleanup, #27–#29 code/UX tidy-ups, plus a Results panel (views per style) and per-call Gemini cost
tracking.

**Status legend:** ✅ fixed and shipped in this pass · 🟡 open (recommended next) · 🔵 needs your decision (cost or
architecture).

---

## 1. What the app is, who it's for, the flows

- **Purpose:** a small restaurant turns one dish photo (or its POS sales export) into a narrated 8-second vertical Short and
  posts it to its own YouTube channel, without editing.
- **Audience:** owners/managers of small restaurants; non-technical, on a phone or laptop, little time.
- **Flows tested end to end on the live site:**
  1. Photo → name/price → Action! → progress → video → Download / Post (iPhone, 81 s, free motion).
  2. Sales CSV (sample) → pick ("Chicken Biryani, up 32% this week", 13 s) → Action! (desktop).
  3. Failure → Try again → new video (live, free motion).
  4. New visitor on a second browser gets their own studio (rename isolation).
  5. YouTube connect: button sends the browser nonce and lands on Google sign-in. *Posting itself not re-tested in
     this pass* (needs a human Google sign-in; it was verified earlier in the project).

---

## 2. Findings and roadmap

Effort: S = under an hour, M = a few hours, L = a day or more.

### P0 — Critical

| # | Problem | Where | Why it matters | Solution | Effort | Impact | Status |
|---|---|---|---|---|---|---|---|
| 1 | **Any studio could read and act on another studio's jobs and videos** by number: view scripts and video links, retry their jobs (spending the shared AI budget), edit/re-render, publish their video to your own channel. Verified live: a brand-new studio got `200` for `/jobs/1` with another studio's script. | `routers/jobs.py` (get, confirm-dish, retry, edit), `routers/videos.py` (get, publish), `routers/insights.py` (`/insights/{id}`) | Privacy breach between restaurants; budget abuse | `db.owned()` returns 404 unless the row belongs to the caller's studio; applied to every by-id route; test covers all six routes | S | High | ✅ live: same requests now `404` |
| 2 | **Guessable video file names** (`job_<id>_<unix time>.mp4`) under the public `/media` | `pipeline.py` | Anyone could enumerate other restaurants' videos | Random 16-hex token in the name (`job_6_8ea8b8011fa533f1.mp4`) | S | Med | ✅ |
| 3 | **Unlimited uploads into the database.** Photos/logos are stored in Neon (free tier 0.5 GB); one script could fill it and take the whole app down (Neon suspends at quota). | `routers/core.py` `/uploads`, `routers/insights.py` `/sales/import` | Availability for everyone | 40 uploads/hour per visitor; stored photos capped at 1600 px, quality 88 (≈⅓ the size) | S | High | ✅ |

### P1 — High impact

| # | Problem | Where | Why it matters | Solution | Effort | Impact | Status |
|---|---|---|---|---|---|---|---|
| 4 | **New visitors make videos branded "Kumar's" without noticing.** Step 1 showed ✓ with the demo's logo. | `page.tsx` StepLogo, `serializers.py` | The first video a real restaurant makes ends with someone else's name | API reports `demo_name` / `demo_logo`; step 1 says "You're using the demo restaurant. Add your own name and logo" and only turns ✓ once both are yours | S | High | ✅ |
| 5 | **Failed video had no way forward** (error text only) | `page.tsx` ResultPanel | Dead end on the most important screen | "Try again" button (POST `/jobs/{id}/retry`) | S | High | ✅ verified live |
| 6 | **YouTube was outside the flow:** connect lived in a bar under the page; up to 3 "Connect YouTube" buttons at once | `page.tsx` History / PostButton | The product promise is "straight to YouTube"; duplicate CTAs confuse | "3 · Post to YouTube" step card (one place to connect/disconnect); per-video connect buttons removed from history | S | Med | ✅ |
| 7 | **Progress said "Animating it with AI" for free photo motion**, ETA "1–1.5 min" | `page.tsx` STEP_LABEL | Honesty; wrong expectations | "Animating your photo" + "~30s" when AI motion isn't used; overall estimate per mode | S | Med | ✅ |
| 8 | **First-time visitors never see what the app makes** — empty phone frame | `components/stage.tsx` | Biggest conversion lever for a demo; Raj sees nothing until he waits 2 min | Real example Short (0.6 MB, made by the pipeline) loops muted in the empty player, labeled "Example · made from one photo" | S | High | ✅ (free-motion example; see #20) |
| 9 | **Privacy policy described the old app** ("storage cleared on restart", "everyone shares one workspace") | `app/privacy/page.tsx` | Google OAuth verification reads it; legally inaccurate | Rewritten: studios, Neon storage, hosts, what's kept where, deletion requests | S | Med | ✅ |
| 10 | **Rendered videos are lost on every server restart** (Render free disk is ephemeral); history hides them | `pipeline.py`, Render | Users lose videos they didn't post or download | Store videos and photos in object storage (Neon Object Storage, Cloudflare R2 or S3) instead of local disk / DB blobs | M–L | High | ✅ Nov 20: backed up in Postgres + restored on first request (Neon object storage isn't offered in this region; R2 later if needed) |
| 11 | **Slow and fragile hosting:** 0.1 CPU, 512 MB, one video at a time, ~1 min cold start, jobs live inside the web process | Render free | 1–3 min per video, queue blocks other users, a restart kills in-flight jobs | Paid instance (Render Starter ≈ $7/mo) now; later a separate worker + queue | S (paid) / L (queue) | High | 🔵 |
| 12 | **Google app is unverified:** warning screen, 100-user cap, uploads may be forced private | Google Cloud | Trust, and posts not visible publicly | Submit OAuth verification (privacy policy ✅, terms ✅, demo video, scopes justification) | M (mostly waiting) | High | 🔵 |
| 13 | **Studio is tied to one browser** (no login): phone and laptop differ; clearing data loses it; the id is a bearer secret | `lib/api.ts`, `db.current_restaurant` | Real restaurants need the same studio everywhere and real access control | Google sign-in (doubles as YouTube connect), keep guest mode, claim guest studio on sign-in | L | High | ✅ Nov 20–21: Google sign-in, guest studio claimed on first sign-in, YouTube saved to the account |

### P2 — Polish and enhancements

| # | Problem | Where | Solution | Effort | Status |
|---|---|---|---|---|---|
| 14 | Filter pills 28 px, footer links 17 px tall | `page.tsx` | 40 px targets | S | ✅ |
| 15 | No way to mute the clapper/fanfare sounds (toggle was removed in the redesign) | `page.tsx` Header | Speaker toggle, remembered per browser | S | ✅ |
| 16 | Tabs had no keyboard support / tabpanel; filter pills no `aria-pressed`; progress not announced | `page.tsx` | Arrow keys + roving focus + `tabpanel`; `aria-pressed`; `aria-live` progress | S | ✅ |
| 17 | Missing security headers (only HSTS) | `next.config.mjs` | X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy | S | ✅ verified live |
| 18 | No link preview image (sharing the link showed text only); meta description said "about a minute" | `app/layout.tsx` | 1200×630 `og.png` from a real frame; accurate description | S | ✅ |
| 19 | Default unstyled 404; name field could be cleared silently, no save feedback | `app/not-found.tsx`, StepLogo | Themed 404; blank name reverts; "✓ Saved" | S | ✅ |
| 20 | Example Short uses free photo motion, which undersells the AI motion | `public/example-short.mp4` | Re-make it with AI motion (costs one AI video, ≈$0.64 of the budget) | S | ✅ Nov 20: AI-motion Money shot example |
| 21 | No Content-Security-Policy | `next.config.mjs` | CSP allowing self, the API origin (connect/media), Google sign-in; test carefully | M | 🟡 |
| 22 | You can't see or edit the narration/captions before posting; Post dialog can't edit description/hashtags | ResultPanel, PostDialog | Show the script under the video; "Edit captions" uses the existing `/jobs/{id}/edit` (already validated by the grounding checker) | M | ✅ Nov 20: 'What's in this video' + Edit captions (free re-render) + editable description/hashtags |
| 23 | No delete (video or studio) | API + UI | `DELETE /videos/{id}`, "Delete my studio" | M | 🟡 |
| 24 | Disconnect YouTube only forgets it in the browser; the Google grant stays until revoked | `routers/videos.py` | Revoke the refresh token at Google on disconnect | S | ✅ Nov 21: disconnect revokes at Google |
| 25 | Abandoned studios and their photo blobs are never cleaned up | DB | Nightly cleanup of studios idle > 30 days with no videos | S | 🟡 |
| 26 | Per-IP limits are a speed bump only: rotating proxies bypass them (verified: this test machine's IP changes per request). Queue cap (4) and the $10 hard cap still hold. | `jobs._admit` | Fine for a demo; with login, limit per account | — | 🟡 note |
| 27 | `page.tsx` is ~1000 lines with 10 components | frontend | Split into `components/steps/*`, `components/history/*` | M | 🟡 |
| 28 | API keeps features the UI no longer uses (demo mode + owner token, menu import, sales map, confirm-dish, mock pipeline) | backend | Keep (tested, useful for dev) or prune in one cleanup PR | M | 🟡 |
| 29 | Mobile: the example video sits after step 3 | `page.tsx` | Optional "See an example" chip near the top on phones | S | 🟡 |
| 30 | CORS always allows localhost:3000 in production | `main.py` | Only add localhost when not in production | S | ✅ Nov 21: production CORS lists only the site |

### P3 — Future features (product)

Ranked by value to a restaurant owner:

1. **Weekly autopilot:** connect Square/Toast once; every Monday the app picks the dish (rising / top seller / slow mover),
   renders a Short and asks "Post it?" in one tap (email or SMS). Turns a tool into a habit.
2. **One video, every platform:** the same 9:16 file to YouTube Shorts, Instagram Reels and TikTok (each has a posting API).
3. **Variations:** render 3 hooks/styles at once; pick the best (or A/B by posting two and comparing views).
4. **Results loop:** pull views/likes per Short from YouTube Analytics into "Your videos"; tie spikes to dish sales from the CSV.
5. **Brand kit:** colors, font and an outro line ("Order on DoorDash") used in captions and the end card.
6. **Narration languages and voices** (Spanish, Hindi, Tamil, …) for the restaurant's community.
7. **Menu-wide batch:** "make a week of content" from 7 dishes in one go, scheduled posting.
8. **Daily special from a chalkboard photo:** read the board with Gemini and make the Short.
9. **QR to the Short** for table tents ("See it being made").

**Simplify/remove:** the hidden owner-token/demo mode and unused endpoints (P2 #28) once login lands; the 15/30-second
lengths in the API that the UI never offers.

---

## 3. UI/UX strategy

The Hollywood theme (velvet, marquee bulbs, clapperboard) is distinctive and consistent; keep it. The work is clarity
and trust, not a new look:

1. **Show, then ask.** Lead with a real example in the player (done), then the three steps. Later: a 1-line value prop
   under the title ("One photo in, a narrated Short out").
2. **One linear flow: 1 Restaurant → 2 Dish → 3 Post.** Each step shows ✓ only when it's truly the user's (done).
   One primary action per screen state: Action! → (while rendering) progress → (done) Post.
3. **Honest system status.** Progress labels and ETAs match what actually runs (done); every failure has a next step (done).
4. **Phone first.** Big targets (done), no sideways scroll at 360 px (verified), example reachable on phones (P2 #29).
5. **Design system:** tokens in `globals.css` (`--gold`, `--cream`, `--panel`…), `Button`/`Field`/`Modal`/`ErrorCallout`
   in `components/ui`. New UI should only use these; split `page.tsx` (P2 #27) so steps are reusable.

---

## 4. What changed in this pass

Commit `1501f34` (on `main`, deployed to Vercel and Render):

- **Security:** studio-scoped by-id routes (`db.owned`), random video/poster names, upload limits + smaller stored
  photos, security headers.
- **UX:** demo-branding prompt (`demo_name`/`demo_logo`), step 3 "Post to YouTube", Try again on failure, honest labels
  and ETAs, example Short in the empty player, sound toggle, "Saved" feedback, bigger tap targets, keyboard tabs,
  screen-reader progress, themed 404, link-preview image, accurate description.
- **Content:** Privacy Policy rewritten for studios + Neon.
- **Code:** removed the per-browser job list (`getMyJobs`/`addMyJob`), redundant now that videos are per studio.
- **Contract:** `contract.md` and `frontend/lib/types.ts` updated (`demo_name`, `demo_logo`, by-id routes 404 across studios).

---

## 5. Test report

**Automated:** 62 backend tests pass on SQLite and on Postgres (new: cross-studio 404s on 6 routes, unguessable names,
upload limit, studio isolation, demo template protection, shared budget). Frontend: `tsc` clean, `next build` clean.

**Live site after deploy (verified):**
- Cross-studio: `/jobs/1`, `/videos/1`, `/jobs/4`, `POST /jobs/1/retry` from a new studio → all `404` (were `200`).
- New studio reports `demo_name: true, demo_logo: true`; page shows the demo prompt.
- Headers present: X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy.
- `/`, `/privacy`, `/terms` 200; `/nope` 404 (themed); `og:image` set; example video served (0.6 MB).
- Desktop, iPhone 13, 360 px: no horizontal overflow, no console errors, demo prompt + step 3 visible, example plays
  (on phones once scrolled into view, as mobile browsers pause off-screen video).
- Failure → Try again → finished video (job 6, file `job_6_8ea8b8011fa533f1.mp4`).
- Earlier in this pass, before the fixes: photo flow 81 s and CSV pick 13 s on the live server.

**Not verified / limitations:**
- Posting to YouTube end to end (needs a person to sign in with Google); last verified earlier in the project.
- AI-motion render after these changes (free motion was used to avoid spending the budget). The AI path code didn't change.
- Real per-person limits: this test machine's IP changes on every request, so "one video in progress" could only be
  observed when two requests happened to share an IP (it did block that one).
- Screen-reader behavior was checked structurally (roles, names, live region), not with an actual screen reader.
- Load testing: not done; the free server handles one video at a time by design.

**Side effects of testing:** a few throwaway studios and free test videos were created on the live database (no
branding or budget changes). The shared demo template was not modified.
