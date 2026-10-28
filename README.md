# JUSTICE AI

A public-interest legal information platform for India: understand your rights, organise your matter, and prepare to work with a qualified advocate. JUSTICE AI is **not** a lawyer, advocate or court.

Current state: **Phase 3 (legal research)**. Accounts, settings, private case workspaces, plan limits, the admin console, and a verified-source legal library (official document ingestion, independent review, search, status warnings, citation verifier) work end to end. The AI roles and Document Studio are not built yet and are labelled as such in the app. No real legal sources are loaded yet: researchers add them from official sites through the admin console. See [`docs/PHASE_REPORTS.md`](docs/PHASE_REPORTS.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Layout

```
backend/    FastAPI + SQLAlchemy 2 + Alembic (Python 3.12+)
frontend/   Next.js 16 App Router + TypeScript
docs/       Architecture, phase reports, defects & risks
```

## Local setup

Requirements: Python 3.12+, Node 22+, PostgreSQL 16.

```bash
# 1. Database
createuser -P justice            # choose a password
createdb -O justice justice
createdb -O justice justice_test

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env          # edit DATABASE_URL
set -a && source .env && set +a
alembic upgrade head
python -m app.cli seed           # jurisdictions, plans, feature flags
uvicorn app.main:app --port 8000

# 3. Frontend (new terminal)
cd frontend
npm ci
npm run dev                      # http://localhost:3000, proxies /api to BACKEND_URL
```

Make yourself an administrator after registering in the UI:

```bash
cd backend && python -m app.cli grant-role you@example.com sysadmin
```

In development no email is sent: verification links appear at **/dev/outbox** (linked from the banner). The dev outbox is refused at startup when `JUSTICE_ENV=production`.

## Tests

```bash
# Backend: runs Alembic migrations down/up against TEST_DATABASE_URL (default: local justice_test)
cd backend && python -m pytest -q

# Browser journeys (Playwright + Chromium) against running servers.
# Use a throwaway database: the Phase 3 journeys load fictional legal fixtures.
createdb -O justice justice_e2e
export DATABASE_URL=postgresql+psycopg://justice:...@localhost:5432/justice_e2e
(cd backend && alembic upgrade head && python -m app.cli seed && uvicorn app.main:app --port 8000 &)
cd frontend && npm run build && npm start &
node e2e/run.mjs && node e2e/phase3.mjs       # screenshots in e2e/screenshots/

# Grounding coverage of the legal evaluation set against the current library
cd backend && python -m app.research.evaluate ../docs/eval/legal_eval_v1.jsonl
```

## Environment variables

See [`.env.example`](.env.example). No secrets are committed; production must set `JUSTICE_ENV=production`, `COOKIE_SECURE=true`, a real `DATABASE_URL`, and an email backend.

## Adding legal sources

1. A legal researcher downloads the official file by hand from the official site (respecting its terms of use).
2. Admin console → Legal sources → Add a source (official https URL required) → Upload official document.
3. A different person with the content reviewer role checks the section split and metadata against the original and verifies it. Only then does it appear in the Legal Library and search.

## Safety rules for contributors

- Never add legal content, citations, contact numbers or lawyer data that has not been verified against an official source and recorded with its source URL and verification date.
- Never add buttons or widgets that simulate functionality. Unbuilt modules show their status page.
- No endpoint may expose a user's case contents to staff.
