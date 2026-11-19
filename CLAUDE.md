# CLAUDE.md — What's Cooking?

Restaurant dish photo or sales CSV → grounded script → AI motion (Gemini Omni) or Ken Burns visuals → TTS → ffmpeg Short → YouTube.
Solo project. Live: https://whats-cooking-jade.vercel.app (Vercel) + Render free (API). Original plan: `docs/planning/` (historical).

## Layout
- `backend/` FastAPI + SQLModel (Postgres via `DATABASE_URL`, e.g. Neon; else SQLite at `$DATA_DIR/app.db`; uploaded asset bytes also kept in `assetblob` and restored on boot) + in-process asyncio job queue + ffmpeg.
  - `app/pipeline.py` stage machine (analyze → script → visuals → voice → assemble), mock + demo-cache runners
  - `app/services/` gemini (Gemini 3.5 Flash), scripts (grounding validator + template fallback), veo (AI motion: Gemini Omni via Interactions API; legacy veo-* ids), budget (AI-motion guard), tts, render, insights, youtube
  - `app/viewer.py` per-visitor YouTube connection (encrypted blob in the browser, sent as `X-YouTube-Auth`; never stored server-side)
  - `app/routers/` core (health, brand, menu, uploads, usage, settings), insights, jobs, videos (+ YouTube OAuth)
- `frontend/` Next.js 15 App Router + Tailwind 3 + SWR. One page (`app/page.tsx`): logo → dish (sales CSV pick or photo) → Action! → Post to YouTube, plus "Your videos" history. Hollywood theme in `lib/theme.tsx` + `app/globals.css`.
- `seed/` Kumar's demo data (`build_assets.py` generates sales/music/placeholders; `seed.py` loads the DB).
- `eval/` grounding eval (`build_cases.py`, `run_eval.py` → `results.md`).
- `scripts/` model listing, AI-motion smoke test, secret generator. Deploy guide: `docs/DEPLOY.md`.

## Rules
- `contract.md` is the API source of truth; `frontend/lib/types.ts` mirrors it. Change both together, commit prefix `CONTRACT:`.
- Every error response uses `{"error":{"code","message","retryable"}}` (raise `AppError`).
- Never let the core loop depend on a paid or slow call: AI motion and TTS must degrade, never fail the job.
- Test audio/video changes against the Docker image too (Render's ffmpeg 7.1 is stricter than older versions).
- Scripts may only state name/price/description from the menu row. Keep `scripts.validate_script` strict; fix prompts, not the validator or eval cases.
- AI-motion calls only through `budget.reserve_veo` → `commit`/`release`. Run ONE uvicorn worker (lock + queue are in-process).
- One studio per browser: `X-Workspace` → `db.current_restaurant()` (cloned from the template on first use; `main.WorkspaceMiddleware`). The budget is global (`budget._global_settings`, ledger summed across studios).
- `budget.HARD_CAP_CENTS` ($10) caps spend whatever the settings say; `PATCH /settings` needs `ADMIN_TOKEN`. Job creation goes through `jobs._admit` (per-IP + queue limits).
- ffmpeg runs one at a time (`media.ffmpeg` semaphore, `FFMPEG_THREADS`): Render free has 512 MB.
- Don't commit `.env`, `backend/data/`, or real customer sales data.

## Commands
```
make setup | make seed | make back | make front | make test | make eval | make models | make secrets
```
Backend tests: `cd backend && .venv/bin/pytest -q` (real ffmpeg; Gemini/TTS/AI motion faked or absent). Against Postgres: `TEST_DATABASE_URL=postgresql://… pytest -q`.
Frontend: `cd frontend && npx tsc --noEmit && npm run build`.
