# SupportIQ

AI-assisted support ticket management system: tickets are received, classified automatically and routed to the right team.

Built as a portfolio project to demonstrate solid software engineering: clear architecture, testing, applied AI, and CI/CD.

## Current status

**Phase 1 — Setup / foundation.** Only the backend skeleton exists: a Flask application factory with a single health check endpoint. No database, no frontend, no AI yet.

- `GET /api/health` → `200 {"status": "ok"}`

## Stack

- **Backend:** Python 3.12, Flask (Application Factory + Blueprints)
- **Planned:** PostgreSQL + pgvector, React + TypeScript, Docker, GitHub Actions

## Getting started

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd backend
cp ../.env.example ../.env   # optional in development
uv sync                       # installs dependencies (Python 3.12 included)
uv run flask --app app run    # starts the dev server on http://127.0.0.1:5000
```

Check it:

```bash
curl http://127.0.0.1:5000/api/health
# {"status":"ok"}
```

## Tests

```bash
cd backend
uv run pytest
```

## Repository layout

```
backend/
  app/
    api/           # HTTP routes (Blueprints)
    config.py      # configuration from environment variables
    extensions.py  # extension registry (empty for now)
  tests/
```

Business logic will live in `app/services/` and SQL in `app/repositories/` starting with the ticket backend.
