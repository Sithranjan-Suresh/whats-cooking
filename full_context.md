# ReelMenu — Full Context

> Read this first. It explains the whole project with no prior context. Companion files: `demo_design.md` (the demo), `product_spec.md` (what to build), `engineering_spec.md` (how to build it).

## Vision
**One sentence:** ReelMenu turns a restaurant's dish photos and sales data into published YouTube Shorts in about a minute, with no editing and a capped cost.

**Paragraph:** Short-form video is now how many diners discover where to eat, but small restaurants rarely post because they have no time, no editor and no idea what to feature. ReelMenu does all three jobs. It reads the sales data to decide which dish to promote, writes a hook, captions and voiceover grounded in the real menu, turns a single dish photo into a vertical video (AI motion with Google Veo, or a free Ken Burns render), and publishes it to the restaurant's YouTube channel. The owner sets a monthly budget and the system never exceeds it.

**Thesis:** What a restaurant already has (photos and sales data) → a published Short in about a minute, with no editing, at a known and capped cost.

## Origin
- Built first at the **LLMSoftware x UT Dallas Hackathon** (Nov 14, 2026), Challenge: AI Video Marketing, as Team 6 (Sithranjan Suresh and Anish Javvadi). It received a **Special Recognition**: "Turning a menu and sales data into ready-to-post video content is exactly the kind of innovation restaurants need."
- The hackathon version faked the videos (made by hand in Google AI Studio). **This rebuild generates them for real**, from scratch.
- LLMSoftware sells an AI operating system for restaurants (AI receptionist, camera alerts, ERP, social and ads). ReelMenu is designed to work as a module they could plug in.

## Problem
- **Who:** independent and small-chain restaurant owners and managers (e.g., Kumar's, an Indian restaurant).
- **Pain:** they know they should post short videos, but doing it takes filming, editing, writing captions and choosing what to feature. It doesn't get done.
- **What they do today:** post nothing, post a static photo occasionally, or pay a freelancer or agency per video.
- **Why now:** image-to-video models (Veo) turn one still photo into convincing motion for well under a dollar, and POS data (Toast, Square, Clover) is easy to export.
- **Evidence level:** *assumed + industry intuition.* LLMSoftware chose this as a challenge track and praised the solution, which is a domain signal. **Still to do:** show the output to 3–5 owners and find one sourced statistic (depth plan).

## Target Users
| User | Today | Pain |
|---|---|---|
| Owner/manager of a 1–5 location restaurant | Posts rarely or never; maybe boosts an old photo | No time, no editing skill, doesn't know what to feature |
| Restaurant marketing person at a small chain | Edits in CapCut by hand | Hours per video, no data on what to promote |
| Platforms like LLMSoftware | Already offer AI video from a menu | Want sales-driven picks, cost control and auto-publishing |

## User Journey (end to end)
1. **Set up:** create the restaurant, set the brand kit (name, logo, colors, voice tone), import the menu CSV, connect YouTube (OAuth), and set the monthly budget and daily Veo clip limit.
2. **Insights:** upload a sales CSV and get ranked "promote this" cards with plain-English reasons.
3. **Studio:** tap **Make video** on a card (or upload any dish photo) → choose length, style and Veo on/off → Generate.
4. **Watch:** the stages tick through Analyze → Script → Visuals → Voice → Assemble, then the Short plays.
5. **Library:** review, download or publish. A YouTube link comes back.
6. **Budget:** the usage meter updates. When the cap is reached, jobs automatically fall back to free mode.

## Feature Map
- **Core loop:** pick a dish (photo or insight) → Generate → watch → Publish.
- **Studio** (core): one dish → one finished Short. Thin slice: photo → Gemini script → Ken Burns visuals + TTS + burned captions → MP4.
- **Insights:** sales CSV → what to promote and why. Thin slice: three ranked cards (Top seller, Rising, Slow mover) with Gemini-written reasons → **Make video**.
- **Library:** every video, one-click publish. Thin slice: grid, playback, download, YouTube publish (private), open link.
- **Brand & Budget:** stays on-brand and capped. Thin slice: brand kit applied to captions and end card, Veo usage meter, daily clip limit, free-mode toggle.
- **Cross-links:** Insights → Studio (pre-fill and angle), Studio → Library, Brand & Budget → Studio (styling and Veo guard). *(Depth: Library views → Insights.)*

## Core Features at Submission (P0)
- Photo-mode generation, end to end, producing an MP4 Short with captions, a voiceover and a brand end card
- Sales-CSV insights with three promotion picks and **Make video** pre-fill
- Optional Veo image-to-video clip with automatic free-mode fallback
- YouTube OAuth connect and upload
- Brand kit, budget meter, daily Veo limit, free-mode toggle
- Seeded demo restaurant (Kumar's) with no-login demo mode and a cached hero render

## Key Differentiators
Compared with the closest alternatives (LLMSoftware's own menu-to-video feature, generic prompt-to-video tools like Veo/Flow, templated editors like CapCut, social schedulers, and agencies or freelancers):
1. **Sales data decides what to promote**, not the owner or a template.
2. **Grounded in the menu:** captions can't invent dishes, prices or claims. This is measured (see the technical claim).
3. **Cost is known and hard-capped per restaurant**, with a free mode that costs $0.
4. **Ends published**, not just as a downloadable file.

## Technical Overview
- **Frontend:** Next.js (App Router, TypeScript, Tailwind), owned by Anish.
- **Backend:** Python FastAPI, SQLite (SQLModel), an in-process async job queue, ffmpeg, owned by Sith.
- **AI:**
  - Gemini Flash (free tier) for image understanding, insight reasons and script JSON (structured output)
  - Veo image-to-video on the paid, prepaid and capped tier (720p, 8s, Lite/Fast variant)
  - edge-tts for voiceover, with gTTS as fallback
- **Publishing:** YouTube Data API v3 (`videos.insert`, OAuth `youtube.upload` scope). This is free, but uploads from an unaudited app are likely restricted to private.
- **Cost control (3 layers):**
  1. Prepaid credits with auto-reload off
  2. AI Studio project monthly spend cap
  3. An in-code `UsageLedger` guard (daily clip limit plus a monthly soft cap that falls back to free mode)
- **Technical claim:** grounded scripts get dish name and price exactly right with no invented claims in ≥ 19/20 cases, vs. an ungrounded photo-only prompt baseline. (Numbers are filled in at Checkpoint 2.)
- **Key technical bets:**
  - Structured-output JSON from Gemini for the whole script
  - ASS subtitles burned by ffmpeg for brand-styled captions
  - Veo kept optional so the core loop never depends on a paid or slow call

## Demo Flow
See `demo_design.md` §3 and §8. Insights card → Studio (Veo on) → stages → Short plays → Publish → YouTube on a phone → eval proof → Library → Budget meter and free mode → close.

## Success Metrics
- **Technical:**
  - End-to-end render (free mode) < 45s, Veo mode < 150s p90
  - 0 crashes on the demo path
  - Eval: grounded ≥ 19/20 and baseline measurably lower
  - The budget guard blocks a clip over the limit 100% of the time
- **Product:** someone who has never seen it completes the core loop on the public URL with no help in < 2 minutes. LLMSoftware asks for a follow-up call.
- **Cost:** ≤ $0.70 per Veo video, $0 in free mode, and total monthly spend never above the cap.

## Future Expansion
1. **Direct POS connectors** (Toast, Square, Clover APIs) instead of CSV, so insights refresh automatically every week.
2. **Multi-platform publishing:** Instagram Reels and TikTok, plus a weekly autopilot ("post the top riser every Friday").
3. **A performance loop:** pull views back, learn which hooks and styles drive views per cuisine, and feed that into the next script.
