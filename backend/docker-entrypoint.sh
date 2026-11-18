#!/bin/sh
set -e
cd /app
mkdir -p "$DATA_DIR"
# Seed the demo restaurant once per volume, in the background so the port opens right away
# (hosts like Render fail a deploy whose port isn't listening within a few minutes).
if [ ! -f "$DATA_DIR/.seeded" ]; then
  echo "Seeding demo restaurant in the background…"
  (sleep 3 && python seed/seed.py && touch "$DATA_DIR/.seeded") &
fi
# ONE worker on purpose: the job queue and the Veo budget lock live in-process.
cd backend
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips="*"
