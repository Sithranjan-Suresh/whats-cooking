# CLAUDE.md — What's Cooking?

Restaurant dish photo or sales CSV → grounded script → Veo or Ken Burns visuals → TTS → ffmpeg Short → YouTube.
Solo project. Specs: `full_context.md`, `product_spec.md`, `engineering_spec.md`, `demo_design.md`. Build checklist: `tasks.md`.

## Layout
- `backend/` FastAPI + SQLModel (SQLite at `$DATA_DIR/app.db`) + in-process asyncio job queue + ffmpeg.
  - `app/pipeline.py` stage machine (analyze → script → visuals → voice → assemble), mock + demo-cache runners
  - `app/services/` gemini, scripts (grounding validator + template fallback), veo, budget (Veo guard), tts, render, insights, youtube
  - `app/routers/` core (health, brand, menu, uploads, usage, settings), insights, jobs, videos (+ YouTube OAuth)
- `frontend/` Next.js 15 App Router + Tailwind 3 + SWR. Pages in `app/(shell)/{insights,studio,library,settings}`.
- `seed/` Kumar's demo data (`build_assets.py` generates sales/music/placeholders; `seed.py` loads the DB).
- `eval/` grounding eval (`build_cases.py`, `run_eval.py` → `results.md`).
- `scripts/` model check, Veo smoke test, hero render, secret generator.

## Rules
- `contract.md` is the API source of truth; `frontend/lib/types.ts` mirrors it. Change both together, commit prefix `CONTRACT:`.
- Every error response uses `{"error":{"code","message","retryable"}}` (raise `AppError`).
- Never let the core loop depend on a paid or slow call: Veo and TTS must degrade, never fail the job.
- Scripts may only state name/price/description from the menu row. Keep `scripts.validate_script` strict; fix prompts, not the validator or eval cases.
- Veo calls only through `budget.reserve_veo` → `commit`/`release`. Run ONE uvicorn worker (lock + queue are in-process).
- Don't commit `.env`, `backend/data/`, or real customer sales data.

## Commands
```
make setup | make seed | make back | make front | make test | make eval | make models | make hero | make secrets
```
Backend tests: `cd backend && .venv/bin/pytest -q` (real ffmpeg; Gemini/TTS/Veo faked or absent).
Frontend: `cd frontend && npx tsc --noEmit && npm run build`.
