# ReelMenu — Product Spec

## 1. Requirements at Submission
1. A first-time viewer opens the public URL on a phone with no login and lands on a seeded demo restaurant (Kumar's).
2. From a single dish photo, the system produces a 9:16 MP4 Short with motion, burned-in brand-styled captions, a voiceover, background music and a brand end card.
3. From an uploaded sales CSV, the system shows ≥ 3 ranked promotion picks with plain-English reasons. Each pick opens Studio pre-filled.
4. Captions and voiceover only state dish names, prices and descriptions present in the menu data. No invented discounts, awards or allergen claims.
5. Veo is optional per job. When it's off, over the limit or failing, the job completes in free mode and says so.
6. The owner can connect YouTube and publish any finished video. The returned YouTube URL is stored and shown.
7. Veo spend can't exceed the in-code daily clip limit or monthly soft cap, and the usage meter is accurate to the job.
8. Every AI and external call has a visible failure state. No blank screens and no endless spinners.
9. The eval script runs and prints grounded vs. baseline pass rates.

## 2. User Stories and Acceptance Criteria

### Core loop / Studio
**S1. As an owner, I want to upload a dish photo and get a finished Short so that I can post video without editing.**
- Accepts JPG/PNG/WEBP up to 10 MB. Larger or other types → inline error "Use a JPG or PNG under 10 MB."
- After Generate, the progress tracker shows 5 stages (Analyze, Script, Visuals, Voice, Assemble) with live status: pending, running, done or failed.
- The finished video is 720×1280 (or 1080×1920), 15s by default (30s option), H.264 + AAC, ≤ 10 MB at 15s.
- It autoplays muted with a tap to unmute, and has a Download button.
- Free mode completes in < 45s on the deploy host.

**S2. As an owner, I want the system to recognize the dish and match it to my menu so that the captions are correct.**
- The Analyze stage returns the best menu match with a confidence score.
- If confidence < 0.6, a picker shows the top 3 menu matches plus "Not on menu" before continuing.
- If the user picks "Not on menu," the script avoids price and uses only visual description.

**S3. As an owner, I want to see the script before the video is done so that I trust what it will say.**
- The script panel fills in as soon as the Script stage finishes: hook, 3–4 caption beats, voiceover text, title, description, hashtags.
- Each beat shows which menu fields it used (e.g., a "from menu: price" chip).

**S4. As an owner, I want to turn on AI motion (Veo) for a better video so that the dish looks alive.**
- The Veo toggle shows an estimated cost ("≈ $0.64").
- If the budget guard denies it, the toggle is disabled with the reason ("Daily limit 10/10 reached" or "Monthly cap reached").
- If Veo fails or times out (> 180s), the job falls back to free visuals automatically and shows a "Free mode (Veo unavailable)" badge.

**S5. As an owner, I want to pick a style and length so that videos don't all look the same.**
- Styles: Bold (big captions, fast cuts), Warm (soft, slower), Minimal (small captions). Length: 15s or 30s.
- The style changes the caption template and pacing, and the prompt tone (P1. P0 ships Bold only).

### Insights
**I1. As an owner, I want to upload my sales export and see what to promote so that I don't have to guess.**
- Accepts CSV with columns `date,item_name,quantity,revenue` (aliases allowed, see engineering spec). Shows the row count and date range after upload.
- Item names are matched to menu items (exact, then normalized, then fuzzy ≥ 0.85). Unmatched items are listed.
- Produces cards: **Top seller** (highest quantity over the last 7 days), **Rising** (largest week-over-week growth with ≥ 10 units this week), **Slow mover** (lowest over the last 14 days among items with a photo).
- Each card shows the metric ("+32% WoW · 84 sold"), a one-sentence reason written by Gemini, and **Make video**.

**I2. As an owner, I want "Make video" to set everything up so that it's one tap.**
- Opens `/studio?insight=<id>` with the dish, its photo and the angle (`top_seller | rising | slow_mover`) pre-filled. The script's hook reflects the angle.
- If the dish has no photo, Studio prompts for an upload with the dish already selected.

### Library
**L1. As an owner, I want to see all my videos so that I can reuse them.**
- Grid with newest first. Each tile shows a poster, dish, date, mode (Veo/Free), cost and status (Draft, Published, Failed).

**L2. As an owner, I want to publish to YouTube in one click so that it actually gets posted.**
- Requires YouTube to be connected. If not, the button says "Connect YouTube" and links to Settings.
- The publish dialog is pre-filled with title, description and hashtags from the script, all editable. Privacy defaults to Private, with Unlisted and Public options.
- On success, the tile shows "Published ↗" with the YouTube URL and the actual privacy status YouTube returned.
- If the API reports the video as restricted or private (unaudited app), show an info note: "YouTube keeps uploads from unverified apps private until review."

### Brand & Budget
**B1. As an owner, I want to set my brand once so that every video looks like mine.**
- Fields: restaurant name, logo (PNG), primary and accent colors, voice tone (Friendly, Upbeat, Elegant), TTS voice.
- Changes apply to the next render and to the live caption preview on the page.

**B2. As an owner, I want a hard budget so that AI costs never surprise me.**
- Shows today's Veo clips used/limit, month-to-date estimated spend/cap, and cost per Veo second (from config).
- The owner can edit the daily clip limit (0–50) and monthly soft cap ($0–$100).
- **Free mode** toggle: when on, Veo is never called.
- The guard prevents any Veo call that would exceed the limit or cap (a test exists).

**B3. As a viewer in demo mode, I want to try it without spending the owner's money.**
- With `DEMO_MODE=1` and no owner session: Veo is disabled, publishing is disabled (seeded published videos show their links), and a demo banner is visible.

## 3. Edge Cases
- Photo isn't food, or is very dark or blurry → Analyze returns `is_food=false` or low quality → "This doesn't look like a dish photo. Try another?" with the option to continue anyway.
- Menu item has no price → the script omits the price and the price eval is skipped for that case.
- Sales CSV has unknown columns, empty rows, mixed date formats, negative quantities (refunds) or fewer than 14 days of data → map aliases, drop invalid rows with a count shown, and if there's under 14 days show only Top seller.
- Two jobs started at once → both queue. The Veo guard is checked atomically at the moment each clip is reserved.
- The user leaves Studio mid-job → the job continues, and Library shows its progress.
- TTS fails → retry once, then the fallback engine, then render captions-only with music and flag it.
- Music file missing → render without music.
- YouTube token expired → refresh automatically. If refresh fails, prompt to reconnect.
- Upload interrupted → the resumable upload retries 3 times with backoff, then the tile shows "Publish failed · Retry".
- Gemini returns non-JSON or misses fields → retry once with a "repair" prompt, then fall back to a template script built from menu fields.
- Very long dish names → captions wrap to ≤ 2 lines at ≤ 22 characters per line, and the font shrinks if needed.

## 4. Failure States for AI and External APIs
| Feature | Empty input | Slow | Malformed output | Refusal / low confidence | Rate limit / quota |
|---|---|---|---|---|---|
| Gemini Analyze (photo → dish) | Block Generate until a photo is set | 20s timeout → retry once → "Couldn't read the photo" + pick dish manually | JSON parse fail → repair retry → manual dish picker | conf < 0.6 → top-3 picker. `is_food=false` → warning | 429 → wait 5s, retry ×2 → manual picker |
| Gemini Script | n/a (after Analyze) | 25s timeout → retry → template script | Schema validation fail → repair retry → template script | Safety block → template script | 429 → template script, flagged in UI |
| Gemini Insight reasons | No sales rows → empty state with sample CSV download | 20s → fall back to rule-based reason text ("Up 32% vs last week") | Same rule-based fallback | Same | Same |
| Veo image-to-video | No photo → Veo toggle disabled | Poll up to 180s → free-mode fallback | Missing/corrupt MP4 → free-mode fallback | Safety filter / no video → free-mode fallback + note | Budget guard deny → free mode with reason. API 429 → free mode |
| TTS | Empty voiceover → captions-only | 15s → fallback engine | Zero-length audio → fallback engine | n/a | Fallback engine → captions-only |
| ffmpeg assemble | n/a | 90s timeout → fail stage with "Render failed · Retry" | Non-zero exit → log stderr tail, retry once with safe preset | n/a | n/a |
| YouTube upload | Not connected → Connect CTA | Resumable upload with progress % | Missing video ID → failed + retry | Restricted/private → info note | quotaExceeded → "Daily YouTube upload limit reached, try tomorrow" |

## 5. Feature Priority
**P0 (blocks the demo):** the core loop plus the thin slice of every pillar.
- S1, S2 (picker can be simple), S3, S4 (with fallback), B1 (name, logo, colors only), B2, B3, I1, I2, L1, L2, seeded demo restaurant, `DEMO_CACHE` hero render, eval script.

**P1 (pillar depth and cross-links):**
- S5 styles beyond Bold, 30s length, regenerating a single beat
- Publish-dialog editing polish
- Unmatched-item mapping UI in Insights
- Rule-based + Gemini reason blend
- Per-video cost receipt

**P2 (extras):**
- YouTube view counts → Insights (Library → Insights link)
- Scheduling
- Multiple music tracks
- Day/time sales patterns
- Instagram/TikTok

**Cut order:** (1) P2 items, (2) Insights depth (unmatched mapping UI, patterns), (3) Veo mode (free mode keeps the loop working), (4) the Insights pillar (Studio photo mode still demos). **The core loop is never cut.**
