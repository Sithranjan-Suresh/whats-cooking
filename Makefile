PY := backend/.venv/bin/python
.PHONY: setup back front seed eval test build secrets models docker

setup:            ## install backend + frontend deps
	python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

back:             ## API on :8000 (reload)
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

front:            ## web on :3000
	cd frontend && npm run dev

seed:             ## build seed assets + load Kumar's into the DB
	$(PY) seed/build_assets.py && $(PY) seed/seed.py

eval:             ## grounded vs baseline eval → eval/results.md
	$(PY) eval/run_eval.py

test:             ## backend tests + frontend typecheck
	cd backend && .venv/bin/pytest -q
	cd frontend && npx tsc --noEmit

build:            ## production frontend build
	cd frontend && npm run build

secrets:          ## print APP_SECRET + OWNER_TOKEN
	$(PY) scripts/gen_secrets.py

models:           ## list Gemini text/video models for your key
	$(PY) scripts/check_models.py

docker:           ## build + run the API image locally
	docker build -f backend/Dockerfile -t whats-cooking-api .
	docker run --rm -p 8000:8000 --env-file .env -v wc-data:/data whats-cooking-api
