#!/bin/sh
set -e
cd /app
mkdir -p "$DATA_DIR"
# Create the DB schema first (synchronously) so the background seeder and the server never race on it.
python -c "import sys; sys.path.insert(0, 'backend'); from app.db import init_db; init_db()"
# Load the demo restaurant only into an empty database, in the background so the port opens right away
# (hosts like Render fail a deploy whose port isn't listening within a few minutes). With a persistent
# DATABASE_URL this runs once, ever; with SQLite on an ephemeral disk it runs after every restart.
(sleep 3 && python seed/seed.py --if-empty) &
# ONE worker on purpose: the job queue and the AI-motion budget lock live in-process.
cd backend
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1 --proxy-headers --forwarded-allow-ips="*"
