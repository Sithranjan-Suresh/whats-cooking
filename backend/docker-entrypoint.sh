#!/bin/sh
set -e
cd /app
mkdir -p "$DATA_DIR"
# Seed the demo restaurant once per volume (idempotent, ~30s the first time).
if [ ! -f "$DATA_DIR/.seeded" ]; then
  echo "Seeding demo restaurant…"
  python seed/seed.py && touch "$DATA_DIR/.seeded"
fi
# ONE worker on purpose: the job queue and the Veo budget lock live in-process.
cd backend
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips="*"
