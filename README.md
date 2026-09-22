# SupportIQ

AI-assisted support ticket management system: tickets are received, classified automatically and routed to the right team.

Built as a portfolio project to demonstrate solid software engineering: clear architecture, testing, applied AI, and CI/CD.

## Current status

**Phase 2 — Backend core (in progress).** The domain model exists: users,
categories, tickets and their audit-trail events, with migrations applied.
The API still only exposes the health check — CRUD comes next.

- `GET /api/health` → `200 {"status": "ok"}` (lightweight, no database query)
- PostgreSQL 17 + Flask-SQLAlchemy + Flask-Migrate wired up
- Domain model: `User`, `Category`, `Ticket`, `TicketEvent` (migration applied)

## Stack

- **Backend:** Python 3.12, Flask (Application Factory + Blueprints), Flask-SQLAlchemy, Flask-Migrate
- **Database:** PostgreSQL 17 (Docker Compose)
- **Tooling:** [uv](https://docs.astral.sh/uv/) for dependency management, pytest
- **Planned:** pgvector, React + TypeScript, GitHub Actions, deployment

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- [uv](https://docs.astral.sh/uv/)
- Python 3.12 (uv can install it automatically)

## Setup

```bash
# 1. Environment variables
cp .env.example .env

# 2. Install backend dependencies
cd backend
uv sync
```

`.env` ships with development defaults. Note that the database listens on
**127.0.0.1:15432** (not 5432) to avoid clashing with any other local
PostgreSQL instance or tunnel on your machine. Always connect via
`127.0.0.1` rather than `localhost`, which may resolve to IPv6 `::1`.

## Start PostgreSQL

From the repository root:

```bash
docker compose up -d --wait   # starts and waits for the healthcheck
docker compose ps             # should show "healthy"
```

Stop it with `docker compose down` (the volume `postgres_data` persists your data).
Use `docker compose down -v` only if you want to delete the data.

## Start the backend

```bash
cd backend
uv run flask --app app run    # http://127.0.0.1:5000
```

Check it:

```bash
curl http://127.0.0.1:5000/api/health
# {"status":"ok"}
```

`/api/health` is intentionally lightweight: it does **not** query PostgreSQL
on every request.

## Tests

Tests run against in-memory SQLite, so they work **without** Docker or
PostgreSQL running:

```bash
cd backend
uv run pytest
```

## Database migrations

Run these from `backend/` with PostgreSQL up:

```bash
uv run flask --app app db init       # once: create migrations/ (already done)
uv run flask --app app db migrate -m "describe your change"   # generate a revision
uv run flask --app app db upgrade     # apply pending revisions
uv run flask --app app db current     # show the applied revision
uv run flask --app app db history     # list revision history
uv run flask --app app db downgrade -1  # roll back one revision
```

## Configuration

All configuration comes from environment variables (see `.env.example`).
Never commit `.env` — it is gitignored.

| Variable | Purpose |
|---|---|
| `FLASK_ENV` | `development` \| `testing` \| `production` |
| `SECRET_KEY` | Session signing key. **Required in production.** |
| `DATABASE_URL` | PostgreSQL connection string, e.g. `postgresql+psycopg://user:pass@127.0.0.1:15432/db` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_PORT` | docker-compose settings (development) |

## Domain model

Four entities, designed for integrity, traceability and a future AI
classification phase:

| Entity | Purpose | Notes |
|---|---|---|
| `User` | People who request, receive or act on tickets | No auth yet; deactivated via `is_active` |
| `Category` | Functional categories (Access, Hardware, ...) | Data, not an enum — administrable and AI-friendly; deactivated via `is_active` |
| `Ticket` | The central entity | UUID PK + human `ticket_number` (`SUP-000001`); `category_id` is nullable on purpose (AI classification arrives later) |
| `TicketEvent` | Append-only audit trail | `actor_id` nullable (system/AI events); payload in a `metadata` JSONB column (Python attribute: `data`) |

Design decisions:

- **Enums** (`status`, `priority`, `event_type`) are stored as `VARCHAR + CHECK`
  — portable, readable, and still validated at the database.
- **`ticket_number`** comes from a PostgreSQL sequence (`ticket_number_seq`), so
  concurrent inserts never collide.
- **All foreign keys use `ON DELETE RESTRICT`** — historical records are
  preserved; entities are deactivated, not deleted. No cascades.
- **Timestamps** are timezone-aware (`TIMESTAMPTZ`) and set by the application.
- **Indexes** target real queries: status+recent listing, requester, assignee,
  category, and per-ticket event timelines.

## Repository layout

```
backend/
  app/
    api/           # HTTP routes (Blueprints)
    config.py      # configuration from environment variables
    extensions.py  # db (Flask-SQLAlchemy) and migrate (Flask-Migrate)
    models/        # domain model (User, Category, Ticket, TicketEvent)
  tests/
  migrations/      # Alembic revisions (Flask-Migrate)
docker-compose.yml # PostgreSQL 17 service
```

Architecture: **Routes → Services → Repositories → PostgreSQL**. Business
logic will live in `app/services/` and SQL in `app/repositories/` starting
with the ticket backend.
