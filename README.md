# SupportIQ

AI-assisted support ticket management system: tickets are received, classified automatically and routed to the right team.

Built as a portfolio project to demonstrate solid software engineering: clear architecture, testing, applied AI, and CI/CD.

## Current status

**Phase 2 complete: Backend Core.** The domain model exists (users,
categories, tickets and audit-trail events) and the API exposes full ticket
management, each ticket's history and a dashboard summary through the
Routes → Services → Repositories stack.

- `GET /api/health` → `200 {"status": "ok"}` (lightweight, no database query)
- Ticket endpoints: create, list (paginated + filters), get, partial update
  with status machine, audit events and a consistent JSON error envelope
- Ticket history: `GET /api/tickets/<ticket_number>/events` — the full audit
  trail of a ticket, oldest event first
- Dashboard summary: `GET /api/dashboard/summary` — status/priority counters
  and unassigned count, computed with SQL aggregates
- PostgreSQL 17 + Flask-SQLAlchemy + Flask-Migrate wired up
- Domain model: `User`, `Category`, `Ticket`, `TicketEvent` (migration applied)
- Idempotent development seed: `flask seed`

## API

All endpoints live under `/api`. Errors always return
`{"error": {"code": "...", "message": "..."}}`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/tickets` | Create a ticket → `201` |
| `GET` | `/api/tickets` | List tickets: `page`/`per_page` + filters `status`, `priority`, `category_id`, `assignee_id`, `requester_id` |
| `GET` | `/api/tickets/<ticket_number>` | Fetch one ticket by its public id (`SUP-000001`) |
| `PATCH` | `/api/tickets/<ticket_number>` | Partial update: `title`, `description`, `status`, `priority`, `assignee_id`, `category_id` |
| `GET` | `/api/tickets/<ticket_number>/events` | Full ticket history, oldest event first (no pagination) |
| `GET` | `/api/dashboard/summary` | Headline counters: tickets by status, by priority, unassigned |

Rules worth knowing:

- **`POST`** accepts only `title`, `description`, `requester_id` (plus optional
  `priority`, `assignee_id`, `category_id`). Defaults: `OPEN` / `MEDIUM`.
  Writes a `TICKET_CREATED` event with the requester as actor.
- **`PATCH`** enforces the status machine
  (`OPEN ↔ IN_PROGRESS`, `→ RESOLVED`, `RESOLVED → CLOSED`; `CLOSED` is locked)
  and writes one event per actual change (`STATUS_CHANGED`,
  `PRIORITY_CHANGED`, `ASSIGNED`, `CATEGORY_CHANGED`) with `from`/`to` data —
  all in a single transaction. No `actor_id` is accepted from the payload:
  events record `NULL` until authentication exists.
- **`GET .../events`** returns `{"items": [...]}` where every event exposes
  `id`, `type`, `actor` (the acting user or `null` before authentication
  exists), `data` (the stored JSON payload) and `created_at`. Events are
  ordered `created_at ASC, id ASC` — the `id` tie-break keeps the order
  deterministic for events created in the same operation. An unknown or
  malformed ticket number returns `404 TICKET_NOT_FOUND`.
- **`GET /api/dashboard/summary`** returns
  `tickets {total, open, in_progress, resolved, closed}`,
  `priority {urgent, high, medium, low}` and `unassigned`. Every number is a
  SQL aggregate (`GROUP BY` / `COUNT`), statuses and priorities absent from
  the table are zero-filled, and `unassigned` counts tickets with no assignee
  regardless of status. Keys are lowercase; enum values elsewhere stay
  uppercase.
- **Status codes:** `400` malformed JSON / bad types / unknown or read-only
  fields / invalid enums or pagination, `404` ticket not found, `409` invalid
  status transition, `422` missing/blank fields or nonexistent/inactive
  references.

### Seed development data

```bash
cd backend
uv run flask --app app seed
# Seed complete: 6 categories, 3 users created.
uv run flask --app app seed   # idempotent: creates nothing the second time
```

Inserts the six categories (Access, Hardware, Software, Network, Billing,
Other) and three development users the ticket endpoints need. Running it
twice never duplicates rows.

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
    api/           # HTTP routes (Blueprints): health, tickets, dashboard, serializers
    services/      # business rules (ticket_service, dashboard_service)
    repositories/  # SQL only (ticket, user, category)
    commands.py    # Flask CLI (flask seed)
    config.py      # configuration from environment variables
    errors.py      # ApiError hierarchy → JSON error envelope
    extensions.py  # db (Flask-SQLAlchemy) and migrate (Flask-Migrate)
    models/        # domain model (User, Category, Ticket, TicketEvent)
  tests/           # pytest, in-memory SQLite (no Docker required)
  migrations/      # Alembic revisions (Flask-Migrate)
docker-compose.yml # PostgreSQL 17 service
```

Architecture: **Routes → Services → Repositories → PostgreSQL**. Routes stay
thin (parse input, call the service, serialize), services own validation,
business rules and the transaction boundary, repositories contain SQL only.
