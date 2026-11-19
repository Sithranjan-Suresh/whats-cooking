# What's Cooking? — Demo Design (Phase 4)

> Working name: **What's Cooking?** (rename freely). Rebuild of LLMSoftware x UTD Team 6 "AI Video Marketing" (Special Recognition). The hackathon version used videos made by hand in Google AI Studio; this version generates them for real.
> Product name: **What's Cooking?** (renamed from the earlier working name). Rebuild of LLMSoftware x UTD Team 6 "AI Video Marketing" (Special Recognition). The hackathon version used videos made by hand in Google AI Studio; this version generates them for real.

---

## 1. Feature Map

**Thesis:** A restaurant turns what it already has (dish photos and sales data) into a published YouTube Short in about a minute, with no editing, at a known and capped cost.

**Core loop:** Pick a dish (from a photo *or* from sales insights) → **Generate** → watch the finished Short → **Publish** to YouTube.

### Pillars (4, each with its own page)

| # | Pillar (page) | Job (serves the thesis by…) | Mini moment | Thin slice (smallest version on real data) | Depth items | Reads / writes |
|---|---|---|---|---|---|---|
| 1 | **Studio** `/studio` (core loop) | …turning one dish into one finished Short | A progress tracker steps through Analyze → Script → Visuals → Voice → Assemble, then the vertical video autoplays | Photo upload → Gemini script → free Ken Burns visuals + TTS + burned captions → MP4 | Veo clip mode, 3 style presets, 15s/30s length, regenerate one beat | Reads MenuItem, BrandKit, Asset · Writes Job, Video |
| 2 | **Insights** `/insights` | …deciding *what* to promote from sales data, so the owner doesn't have to | "Chicken Biryani is up 32% this week. Promote it?" card → **Make video** opens Studio with the dish and the angle filled in | Upload sales CSV → ranked cards for Top seller, Rising, and Slow mover to push, each with a one-line reason from Gemini | Day/time patterns, margin-aware picks, views fed back from Library | Reads SalesRecord, MenuItem · Writes Insight |
| 3 | **Library** `/library` | …showing every video and publishing it in one click | **Publish** → YouTube link appears with a status badge | Grid of videos: play, download, publish (private) to the connected channel, open on YouTube | Edit title/description/hashtags before publishing, schedule, pull view counts back | Reads Video · Writes Video.youtube_id |
| 4 | **Brand & Budget** `/settings` | …keeping every video on-brand and every dollar capped | The budget meter shows "Today: 3/10 Veo clips · $1.92 this month of $15 cap", and a **Free mode** toggle | Brand kit (name, logo, 2 colors, voice tone) applied to the captions and end card. Veo usage meter + daily clip limit + free-mode switch | Multiple voices, music library, per-video cost receipts | Reads/Writes BrandKit, Settings, UsageLedger |

**Cross-links (pillars feeding each other):**
1. **Insights → Studio:** an insight card pre-fills the dish, its photo, and the sales angle ("best seller", "back by demand"), and that angle shapes the script's hook.
2. **Studio → Library:** every finished job lands in the Library ready to publish.
3. **Brand & Budget → Studio:** the brand kit styles every render, and the budget guard decides Veo vs. free mode per job.
4. *(Depth)* **Library → Insights:** YouTube view counts show next to each dish's sales trend.

**Shared backbone:** one data model (`Restaurant → MenuItem → Job → Video`), one left sidebar (Insights · Studio · Library · Brand & Budget), and one design system.

**Cut order if time runs short:** (1) Library → Insights views feedback, (2) Insights depth (patterns, margin), (3) Veo mode (free mode alone still completes the loop), (4) the Insights pillar entirely (Studio photo mode alone still demos). **Never cut:** the core loop (photo → Short → publish).

**Coherence test:** each pillar serves the thesis in one phrase. Studio = make it, Insights = choose it, Library = publish it, Brand & Budget = keep it on-brand and cheap. All four pass.

---

## 2. Demo Hook (first 15 seconds)
> "Most small restaurants know they should be posting short videos. Almost none do, because they have no time and no editor. Here's Kumar's biryani going from sales data to a published YouTube Short before this demo ends."

Visual: the Insights page is already open, and the top card pulses: **"Chicken Biryani: up 32% this week."**

## 3. Demo Flow
1. **Insights.** The sales CSV is already loaded. Three cards: Top seller, Rising, Slow mover. Click **Make video** on the Biryani card. *(Cross-link 1)*
2. **Studio.** The dish, photo and angle are pre-filled. Toggle **Veo: on**. Click **Generate**.
3. **Progress tracker.** Each stage lights up as it finishes, while the script appears in the side panel as it's written (hook, captions, voiceover).
4. **Reveal.** The 9:16 Short autoplays: steam rises off the biryani, captions in brand colors, voiceover, and the Kumar's end card. **← Wow #1**
5. **Publish.** Click Publish, the YouTube link appears, and you open it on a phone. **← Wow #2**
6. **Proof beat.** "Every caption is grounded in the real menu. Here's our eval: 20/20 dish names and prices correct, vs __/20 for an ungrounded prompt." **← Wow #3**
7. **Pillar tour (fast):**
   - Library shows all the videos.
   - Brand & Budget shows the "$0.64 this video, capped at $15/month" meter. Flip **Free mode**, and the same dish renders for $0. **← Wow #4**
8. **Close.** "It plugs into the Toast, Square and Clover data you already have."

## 4. Wow Moments
1. The Short autoplays with motion from a single still photo (core loop).
2. A real YouTube link appears and opens on a phone.
3. The proof numbers: grounded captions vs. the ungrounded baseline.
4. Free mode: the same video for $0, and the budget meter shows the hard cap.
5. *(Optional)* The insight card explains *why* to promote a dish in plain English.

## 5. Required Screens
- `/insights`: CSV upload and ranked insight cards
- `/studio`: input picker (Photo | From insight | From menu), options, Generate, progress tracker, script panel, player
- `/library`: video grid and publish dialog
- `/settings`: brand kit, YouTube connect, budget meter, free-mode toggle
- `/` → redirects to `/insights` (or `/studio` if no sales data has been loaded)

## 6. User Journey (from the viewer's side)
A viewer opens the deployed URL on a phone with **no login** (demo restaurant "Kumar's" is pre-seeded, with menu, sales CSV and brand kit already loaded). They land on Insights, see three cards and tap **Make video**. Studio opens pre-filled. They tap Generate and watch the stages tick. Within about 60–120 seconds (or instantly from cache in demo mode) the Short plays. They visit Library and see it next to earlier videos. Publishing is limited to the owner account, so viewers see a "Published ↗" link on seeded videos instead.

**Viewer path:** a public demo URL with a seeded restaurant, no login, and a "Demo mode" banner. Generation runs in free mode for viewers (no Veo spend), and Veo is reserved for the presenter.

## 7. Takeaways (the 3 things they remember)
1. **Sales data or one photo → a published Short in about a minute, no editing.** (the thesis)
2. **It picks what to promote and stays accurate:** captions grounded in the real menu, with a measured result.
3. **Cost is known and capped:** about $0.64 per Veo video, or $0 in free mode, under a hard monthly cap.

## 8. 90-Second Demo Script (word for word; rewrite around the real numbers at Checkpoint 3)
> **[0:00 · Insights open]** "Small restaurants know short-form video brings people in. They don't have the time or an editor, so they post nothing. What's Cooking? fixes that with what they already have."
> **[0:10 · tap the Biryani card]** "This is Kumar's real sales data. What's Cooking? noticed chicken biryani is up 32% this week and suggests promoting it. One tap."
> **[0:18 · Studio, Generate]** "It reads the dish photo and the menu, writes a hook, captions and a voiceover, then turns this single photo into motion."
> **[0:30 · stages ticking, script panel filling]** "Every caption comes from the real menu. No invented dishes, no wrong prices."
> **[0:40 · video autoplays]** *(let it play 6 seconds of silence from you)*
> **[0:48 · Publish]** "Publish." *(hold up phone)* "It's on their YouTube channel."
> **[0:55 · eval slide/panel]** "We tested it: on 20 real menu items, grounded captions got every dish and price right. An ungrounded prompt got __ of 20."
> **[1:05 · Library → Brand & Budget]** "Every video lives here. And cost is capped: this one cost 64 cents. Owners set a monthly cap, or flip free mode and the same video costs nothing."
> **[1:20 · close]** "Photo or sales data in, published Short out. Built to plug into Toast, Square and Clover. That's What's Cooking?."

## 9. Signature Moment
**Insights → published Short in one flow.** Sales data picks the dish, a single photo becomes motion video, and it posts to YouTube. LLMSoftware's own video product starts from a menu. Generic AI video tools (one-off prompt-to-video) don't know what's selling.
- **Placement:** 0:10–0:55 of the script, inside the first minute.
- **What the viewer sees:** an insight card → Studio pre-filled → video plays → YouTube link.
- **Real data:** the seeded Kumar's sales CSV (realistic, 8 weeks) and real dish photos.
- **Cached fallback:** `DEMO_CACHE=1` returns a pre-rendered Veo Short for the seeded biryani job after a simulated 8-second stage progression. Publishing uses a pre-uploaded video ID if the YouTube API fails.
- **Load cost:** the video is ≤ 8 MB at 720×1280, and the poster frame loads first.
- **If it isn't working live at Checkpoint 2:** demo the core loop from photo mode and use cached output for the Insights step.

## 10. Depth Plan (only after every thin slice works)
1. **Stretch eval:** 40–50 labeled cases, a second baseline (Gemini with menu text but no structured output), and a failure-case table.
2. **Real evidence:** show 3–5 restaurant owners or staff a generated Short and log their reactions. Find one sourced statistic on short-form video and restaurant discovery.
3. **Pillar depth, in cut order:**
   - Insights: day/time patterns
   - Studio: style presets and regenerating one beat
   - Library: scheduling and view counts
4. **Hardening:** Veo timeout → automatic free-mode fallback, and a retry path for failed YouTube uploads.
5. **Polish and rehearsal.**

## 11. Design Direction
- **Palette:** near-black green `#0F1A14` (background), panel `#18261D`, gold `#C49A4A` (primary), cream `#F3EBDD` (text), signal green `#5BD07F` (success), warm red `#E0604F` (error/over-budget). This matches LLMSoftware's brand on purpose.
- **Type:** Oswald (headings, numbers, counters) + Inter (body). JetBrains Mono for the cost and usage figures.
- **Hero moments:** (1) the Studio player, a phone-frame mockup centered with soft gold glow while the video plays; (2) the progress tracker, five stages with animated check marks and the script streaming in beside it.
- **Navigation:** left sidebar on desktop, bottom tab bar on mobile (4 tabs). One component kit: Card, StatTile, StageStepper, VideoTile, Badge, Toggle, Meter.
- **Load budget:** first contentful paint < 1.5s on a 4G phone, JS < 250 KB gzipped per route, videos lazy-loaded with a poster.

## 12. Technical Claim, Baseline and Eval Plan
- **Claim:** *What's Cooking?'s captions and voiceover are grounded in the restaurant's real menu. Measured by the share of videos whose dish name and price are exactly correct and contain no invented claims (allergens, awards, discounts), versus a baseline prompt with only the photo and no menu grounding.*
- **Eval set:** 20 labeled cases (`eval/cases.json`): 12 dish photos with their menu rows (name, price, description, category) and 8 sales scenarios (CSV slice and expected promotion pick).
- **Scoring (`eval/run_eval.py`):**
  - For photo cases: generate the script JSON both ways and score each on dish name exact/normalized match, price exact match, and no invented claims (an LLM-judge check plus a regex for "$", "%", "award", "allergen", "gluten").
  - For sales cases: the top pick matches the expected dish.
  - Report pass rates for grounded vs. baseline, plus the failures.
- **When:** first result at Checkpoint 2 (50%), final at Checkpoint 3 (75%).
- **Stretch claim (depth budget, not a commitment):** 40–50 cases, a second baseline, and a failure-case table.
- **Lighter proof per pillar:**
  - Insights: the pick matches the expected dish in 8/8 seeded scenarios.
  - Studio: render time in seconds and cost per video.
  - Library: the YouTube video ID returned.
  - Budget: the guard blocks the 11th Veo clip when the limit is 10 (a visible test).

## 13. Riskiest Assumptions
| Assumption | Why it matters | How to test | When |
|---|---|---|---|
| The Veo model name/version in the API is current and available on our tier | One tracker lists Veo 3.1 as deprecated (Oct 22, 2026); the model may have changed | Call `models.list` on the key and run one 8-second test clip | Before build, day 0 |
| Veo latency fits a live demo | Generation can take a minute or more | Time 5 clips. If p90 > 90s, demo with `DEMO_CACHE` | Checkpoint 1 |
| The spend cap actually stops runaway cost | Billing data lags about 10 minutes | Prepay credits with auto-reload off, an AI Studio cap set below budget, and the in-code daily limit | Before the first Veo call |
| The YouTube upload works without the audit | Unaudited apps are restricted, and uploads likely stay private | Upload one test video and check its privacy status | Checkpoint 1 |
| Free TTS (edge-tts) keeps working | It's an unofficial endpoint | Wrap behind `tts.py` with a gTTS fallback | Checkpoint 1 |
| Gemini free-tier rate limits are enough | Text requests during the demo | Expect fewer than 10 requests per video; cache scripts per job | Checkpoint 2 |
| Gemini stays factual about price and dish | The core claim depends on it | Eval set | Checkpoint 2 |
| ffmpeg is on the deploy host | Rendering depends on it | A Docker image with ffmpeg, deployed day 0 | Checkpoint 1 |
