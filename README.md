# SupportIQ

AI-assisted support ticket management system: tickets are received, classified automatically and routed to the right team.

Built as a portfolio project to demonstrate solid software engineering: clear architecture, testing, applied AI, and CI/CD.

## Current status

**Phase 2 complete · Phase 3 · Milestone 1 complete: Semantic Foundation.**
The domain model exists (users,
categories, tickets and audit-trail events) and the API exposes full ticket
management, each ticket's history and a dashboard summary through the
Routes → Services → Repositories stack. Milestone 1 of Phase 3 adds the
semantic layer: per-ticket embeddings stored with pgvector, a free-tier
Gemini provider behind a small abstraction, and CLI backfill/similarity
search — still **no AI classification and no search endpoint**.

- `GET /api/health` → `200 {"status": "ok"}` (lightweight, no database query)
- Ticket endpoints: create, list (paginated + filters), get, partial update
  with status machine, audit events and a consistent JSON error envelope
- Ticket history: `GET /api/tickets/<ticket_number>/events` — the full audit
  trail of a ticket, oldest event first
- Dashboard summary: `GET /api/dashboard/summary` — status/priority counters
  and unassigned count, computed with SQL aggregates
- Semantic embeddings: `ticket.embedding vector(768)` + `embedding_model`
  via pgvector (one migration), never blocking ticket writes
- Embedding CLI: `flask embeddings backfill [--limit N]` (idempotent,
  pending-only) and `flask embeddings similar` (exact cosine ranking,
  CLI only — see [Semantic embeddings](#semantic-embeddings-phase-3--milestone-1))
- PostgreSQL 17 + pgvector + Flask-SQLAlchemy + Flask-Migrate wired up
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
- **Database:** PostgreSQL 17 + pgvector (Docker Compose)
- **Embeddings:** Gemini `gemini-embedding-001` free tier (plain httpx, no SDK), plus an in-process fake provider for tests
- **Tooling:** [uv](https://docs.astral.sh/uv/) for dependency management, pytest
- **Planned:** React + TypeScript, GitHub Actions, deployment

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

The suite also contains `postgres`-marked tests that exercise pgvector's
real operators; they **skip** unless `TEST_DATABASE_URL` points at a
separate database (see [Semantic embeddings](#semantic-embeddings-phase-3--milestone-1)
→ Tests and PostgreSQL). The suite can never call a real embedding
provider: tests are forced onto the fake provider, and any outbound HTTP
attempt fails the test.

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
| `EMBEDDING_PROVIDER` | `gemini` (default, real calls) \| `fake` (in-process, tests/demos) |
| `EMBEDDING_MODEL` | Embedding model name, default `gemini-embedding-001` |
| `EMBEDDING_API_KEY` | Free Gemini key (never commit it). Empty/missing = embeddings disabled, tickets stay valid with `NULL` |
| `TEST_DATABASE_URL` | Optional: separate database for the `postgres`-marked tests (they skip if unset) |

## Semantic embeddings (Phase 3 · Milestone 1)

Each ticket stores a semantic vector of its text so later milestones can
find similar tickets and, later still, suggest categories. This milestone
is the **semantic foundation only**: embedding generation, storage and a
CLI search — no AI classification, no HTTP endpoint, no frontend.

- **What is embedded:** `Title: {title}\nDescription: {description}`
  (trimmed). Nothing else — never category (the future label), status,
  priority, assignee or requester.
- **Where:** in the **same PostgreSQL**, via the official
  `pgvector/pgvector:pg17` image: `ticket.embedding vector(768)` and
  `ticket.embedding_model varchar(64)` (migration `c94d2e81fa63`).
  No separate vector database or extra service — part of the project's
  **USD 0** cost rule.
- **Provider:** Gemini `gemini-embedding-001` (free tier) behind a small
  `EmbeddingProvider` interface, with a deterministic in-process
  `FakeEmbeddingProvider` for tests and demos. Plain `httpx`, no SDK.
  The API key comes only from `EMBEDDING_API_KEY` and is never committed,
  logged or printed.
- **Degraded by design:** ticket writes never depend on the provider. The
  ticket transaction commits first; embedding runs afterwards in a second
  short commit. If the provider fails, the ticket stays valid with
  `embedding = NULL` and `flask embeddings backfill` repairs it later.
  Editing `title`/`description` nulls the vector **in the same PATCH
  transaction** (a stale vector is never kept) and re-embeds after the
  commit; editing status, priority, assignee or category does not touch it.
- **Search:** exact cosine nearest neighbour (`<=>`), ordered by distance
  ascending, `similarity = 1 - distance`. Deliberately no ANN index
  (HNSW/IVFFlat) until the table grows, no similarity threshold and no
  automatic duplicate decisions — a ranking with scores only. Vectors
  produced by a different `embedding_model` are excluded from results.

### CLI

```bash
cd backend

# Embed tickets whose embedding is NULL: pending-only, idempotent,
# one commit per ticket, a failure never aborts the rest, exit code 1
# if any ticket failed. Small batches only (free-tier friendly).
uv run flask --app app embeddings backfill
uv run flask --app app embeddings backfill --limit 10

# Rank stored tickets by semantic similarity (limit 1..20, default 5)
uv run flask --app app embeddings similar \
  --title "Laptop will not boot" \
  --description "Blue screen after Windows update" \
  --limit 5
```

Sample output:

```
Most similar tickets (2):
  1.0000  SUP-000001  [IN_PROGRESS]  Laptop will not boot
  0.7724  SUP-000002  [RESOLVED]  Email quota exceeded
```

There is deliberately **no HTTP endpoint** for search yet, and the demo
tickets are fictional (no real people, companies or institutions).

### Tests and PostgreSQL

The default suite runs on in-memory SQLite: it creates and round-trips
the `vector(768)` column fine, but SQLite **cannot execute pgvector
operators** such as `<=>` — only the real extension can. The
`postgres`-marked tests in `tests/test_semantic_search.py` cover exactly
what SQLite cannot (extension present, real vector storage, cosine
ranking and similarity math) and **skip with a clear message** unless you
point them at a separate database:

```bash
cd backend
# Uncomment TEST_DATABASE_URL in .env (from .env.example), then:
uv run pytest -q
```

(That database is created automatically and is separate from your main
development data, which is never touched.)

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
    services/      # business rules (ticket_service, dashboard_service, embedding_service)
    embeddings/    # EmbeddingProvider contract, Gemini/fake providers, text builder
    repositories/  # SQL only (ticket, user, category)
    commands.py    # Flask CLI (flask seed, flask embeddings)
    config.py      # configuration from environment variables
    errors.py      # ApiError hierarchy → JSON error envelope
    extensions.py  # db (Flask-SQLAlchemy) and migrate (Flask-Migrate)
    models/        # domain model (User, Category, Ticket, TicketEvent)
  tests/           # pytest, in-memory SQLite (+ optional postgres-marked tests)
  migrations/      # Alembic revisions (Flask-Migrate)
docker-compose.yml # PostgreSQL 17 + pgvector service
```

Architecture: **Routes → Services → Repositories → PostgreSQL**. Routes stay
thin (parse input, call the service, serialize), services own validation,
business rules and the transaction boundary, repositories contain SQL only.
Embeddings follow the same rule: only the service layer decides when to
call the provider, and only after the ticket transaction has committed.
