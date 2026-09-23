# SupportIQ

AI-assisted support ticket management system: tickets are received, classified automatically and routed to the right team.

Built as a portfolio project to demonstrate solid software engineering: clear architecture, testing, applied AI, and CI/CD.

## Current status

**Phase 4 complete: React frontend · Phase 3 · Milestones 1–2 complete.**
The domain model exists (users,
categories, tickets and audit-trail events) and the API exposes full ticket
management, each ticket's history and a dashboard summary through the
Routes → Services → Repositories stack. Phase 3 added the intelligence
layer in milestones: M1 stored per-ticket embeddings with pgvector
behind a free-tier Gemini provider; M2 classifies new tickets with a
**similarity-weighted vote over historically human-categorized
tickets**, abstaining when the evidence is insufficient. No LLM is ever
asked for the category, and there is still **no search/classification
HTTP endpoint**. Phase 4 adds a four-page React UI (Dashboard, Tickets,
Create, Detail) with filters, pagination, inline editing and the event
history — see [Frontend (Phase 4)](#frontend-phase-4).

- `GET /api/health` → `200 {"status": "ok"}` (lightweight, no database query)
- Ticket endpoints: create, list (paginated + filters), get, partial update
  with status machine, audit events and a consistent JSON error envelope
- Ticket history: `GET /api/tickets/<ticket_number>/events` — the full audit
  trail of a ticket, oldest event first
- Dashboard summary: `GET /api/dashboard/summary` — status/priority counters
  and unassigned count, computed with SQL aggregates
- Reference data: `GET /api/users` and `GET /api/categories` — active
  records only, plain JSON arrays, name order (the UI's selects and id-to-name
  joins)
- Semantic embeddings: `ticket.embedding vector(768)` + `embedding_model`
  via pgvector (one migration), never blocking ticket writes
- Automatic classification on `POST /api/tickets` (after the embedding
  commit): top-K pgvector neighbours → similarity-weighted vote →
  category + confidence, or an explicit abstention — see
  [Automatic classification](#automatic-classification-phase-3--milestone-2)
- Provenance and audit: `category_source` (`MANUAL`/`AI`),
  `classification_confidence` and an `AI_CLASSIFIED` event with capped
  top-3 evidence (never vectors); human category edits reset provenance
  (the feedback-loop guard)
- Embedding CLI: `flask embeddings backfill [--limit N]` (idempotent,
  pending-only) and `flask embeddings similar` (exact cosine ranking,
  CLI only — see [Semantic embeddings](#semantic-embeddings-phase-3--milestone-1))
- Evaluation CLI: `flask classification evaluate` — leave-one-out over
  36 fictional tickets, honest metrics with no target to tune toward
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
| `GET` | `/api/users` | Active users, plain array `[{id, full_name, email}]`, name order |
| `GET` | `/api/categories` | Active categories, plain array `[{id, name, slug}]`, name order |

Rules worth knowing:

- **`POST`** accepts only `title`, `description`, `requester_id` (plus optional
  `priority`, `assignee_id`, `category_id`). Defaults: `OPEN` / `MEDIUM`.
  Writes a `TICKET_CREATED` event with the requester as actor. When no
  category is given, the classifier may assign one right after creation
  (response included); a provided category is never overwritten.
- **`PATCH`** enforces the status machine
  (`OPEN ↔ IN_PROGRESS`, `→ RESOLVED`, `RESOLVED → CLOSED`; `CLOSED` is locked)
  and writes one event per actual change (`STATUS_CHANGED`,
  `PRIORITY_CHANGED`, `ASSIGNED`, `CATEGORY_CHANGED`) with `from`/`to` data —
  all in a single transaction. Changing (or clearing) the category also
  marks it `category_source = MANUAL` and clears
  `classification_confidence` in that same transaction: the correction
  becomes human evidence again. No `actor_id` is accepted from the payload:
  events record `NULL` until authentication exists.
- Ticket responses expose `category` (`{id, name, slug}` or `null`),
  `category_source` and `classification_confidence`, so a future UI can
  render "Network · AI · 89%" without parsing the event timeline.
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
- **Frontend:** React 19 + TypeScript + Vite, React Router, CSS Modules, lucide-react
- **Tooling:** [uv](https://docs.astral.sh/uv/) for dependency management, pytest; npm + ESLint + Vitest for the frontend
- **Planned:** GitHub Actions, deployment

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)
- [uv](https://docs.astral.sh/uv/)
- Python 3.12 (uv can install it automatically)
- Node.js 20+ and npm (frontend)

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
| `CLASSIFICATION_ENABLED` | Explicit boolean, `true` or `false` only (anything else fails at startup). Development defaults to `false` and reads this variable; testing ignores it on purpose; base/production default to `true`. Never derived from `EMBEDDING_PROVIDER` |

The classifier's gates (similarity/margin/confidence thresholds) are
**code configuration** in `backend/app/config.py` — see
[Automatic classification](#automatic-classification-phase-3--milestone-2).
The switch itself, `CLASSIFICATION_ENABLED`, is an explicit boolean
environment variable: only `true`/`false` are accepted (a typo fails at
startup), **development defaults to `false` and reads it**, testing
ignores it on purpose so a stray shell variable can never flip the
suite, and base/production default to `true`. It is never derived from
`EMBEDDING_PROVIDER`: enabling the classifier implies nothing about
which provider embeds, and vice versa.

## Semantic embeddings (Phase 3 · Milestone 1)

Each ticket stores a semantic vector of its text so the classifier can
retrieve similar historical tickets. This milestone is the **semantic
foundation only**: embedding generation, storage and a CLI search — the
HTTP surface and classification itself arrive in the next milestone.

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

## Automatic classification (Phase 3 · Milestone 2)

SupportIQ classifies new support tickets by retrieving semantically
similar historical tickets with pgvector and applying a
similarity-weighted voting strategy over their **manually validated**
categories. The classifier can **abstain** when the historical evidence
is insufficient, instead of forcing a low-confidence prediction.

No LLM is asked *"what category is this?"*: the decision is pgvector
retrieval plus arithmetic over evidence the system already stores. The
whole milestone adds **no dependency, no service and no paid API** —
it runs on the existing PostgreSQL and demonstrates fully at **USD 0**.

### Strategy: similarity-weighted vote

For the top-K eligible neighbours with cosine similarities
`sᵢ = 1 - distance`:

```
weight of neighbour i = max(sᵢ, 0)            # non-positive = no evidence
S(category)            = Σ weights of its neighbours
winner                 = argmax S(category)    # ties: best single weight, then id
share   = S(winner) / Σ S(all)                 # dominance over the alternatives
margin  = (S(first) - S(second)) / Σ S(all)    # head-to-head decisiveness
confidence = share × top_similarity            # quality of the best match
```

Why this over the alternatives: plain *nearest neighbour* lets one
misleading near-neighbour decide everything; *majority vote over top-K*
treats a 0.95 match and a 0.55 match as equal voices. Weighting by
similarity uses the information pgvector already computes and leaves the
vote explainable ("Network: 0.94 + 0.91 + 0.84").

### What `confidence` means (and does not mean)

`confidence = share × top_similarity` is a **heuristic score in (0..1]**:
how dominant the winning category is among the retrieved evidence,
scaled by the strength of the best match. It is **not a statistically
calibrated probability** — `0.9` does not mean "90% chance of being
right". Calibration would need labelled outcomes; until human
corrections accumulate, the score orders decisions, nothing more. It is
documented exactly like that in code, API docs and reports.

### Abstention: refusing to guess

Before anything is assigned, three gates must pass (each failure has its
own reason, so evaluation output says *why* tickets were skipped):

| Gate | Question | Config key | Initial hypothesis |
|---|---|---|---|
| Relevance | Is the best match similar enough? | `CLASSIFICATION_MIN_SIMILARITY` | `0.55` |
| Decisiveness | Does the winner beat the runner-up clearly? | `CLASSIFICATION_MIN_MARGIN` | `0.20` |
| Overall | Is the combined score worth acting on? | `CLASSIFICATION_MIN_CONFIDENCE` | `0.50` |

Abstaining writes **no event and no state change** — only a log line with
the reason (`NO_EVIDENCE`, `LOW_SIMILARITY`, `AMBIGUOUS`,
`LOW_CONFIDENCE`). These thresholds are **initial hypotheses, not
targets**: they are validated by running
`flask classification evaluate` and observing coverage vs. accuracy
honestly — there is deliberately no accuracy or abstention percentage
the numbers are tuned toward.

### Which tickets count as evidence

A historical ticket may vote only if **all** of these hold (one shared
query in `TicketRepository.find_classification_neighbors`):

- it has an embedding produced by the current `embedding_model`
- `category_id IS NOT NULL` (uncategorized tickets cannot vote)
- its category is **active** (inactive categories receive no new tickets)
- `category_source = MANUAL` — **AI-assigned categories never count**
- it is **not the ticket being classified**

Deliberately *not* filtered: status (a closed ticket's category is as
valid as an open one) and assignee (irrelevant to category truth).

### Feedback-loop guard and provenance

`tickets.category_source` (`MANUAL` default / `AI`) is both the audit
field and the guard: the classifier only ever learns from categories a
human set, so its own mistakes can never reinforce themselves. A human
who changes (or clears) the category via `PATCH` flips it back to
`MANUAL`, clears `classification_confidence`, and the existing
`CATEGORY_CHANGED` event records the correction — no extra feedback
system needed yet.

### Flow and failure modes

```
POST /tickets
  ├─ commit: ticket + TICKET_CREATED
  ├─ embed (provider, best-effort) → commit vector          [M1]
  └─ classify (only if no category given, embedding present, enabled):
       read the persisted embedding → top-K neighbours (SQL, read-only)
       → pure vote + gates → on success: ONE short commit
         (category + source=AI + confidence + AI_CLASSIFIED event)
```

- Classification makes **zero embedding-provider calls** — it reuses the
  vector the ticket already has.
- No historical evidence, empty database, pgvector error, loader crash or
  any unexpected exception → the step rolls back and logs; the ticket is
  still created (`201`). **Creating a ticket never fails because of
  classification.**
- Embedding failed (provider down) → no query vector → classification is
  skipped; `flask embeddings backfill` repairs the vector later.

### Audit event

Assignments write one `AI_CLASSIFIED` event (`actor = null`, system) with
fixed-size metadata — top-3 evidence to reconstruct the vote by hand,
never vectors:

```json
{
  "category_id": "...", "category_slug": "network",
  "confidence": 0.7733, "share": 0.8226, "margin": 0.6453,
  "top_similarity": 0.94, "k": 5, "neighbors_used": 4,
  "evidence": [
    {"ticket_number": "SUP-0001", "category_slug": "network", "similarity": 0.94},
    {"ticket_number": "SUP-0014", "category_slug": "network", "similarity": 0.91},
    {"ticket_number": "SUP-0040", "category_slug": "access",  "similarity": 0.58}
  ]
}
```

### Persisted fields and API surface

- `tickets.category_source VARCHAR(6) NOT NULL DEFAULT 'MANUAL'` +
  `tickets.classification_confidence FLOAT NULL` (range-checked 0..1) —
  migration `b3f7e2c91a04`, reversible.
- Ticket JSON adds `category` (`{id, name, slug}`), `category_source` and
  `classification_confidence`.
- **No new endpoints.** A future `POST /tickets/<ticket_number>/classify`
  (explicit re-run for the UI) is documented but deliberately not built
  in this milestone.

### Evaluation: leave-one-out over a fictional dataset

`flask classification evaluate` seeds 36 **100% invented** tickets
(6 categories × 6, no real people, employers or institutions — nothing
from UBA, SIU, Mapuche or any real organization) and, for each one,
classifies it from the other 35 with the exact production evidence
rules and vote, comparing against the known category. It is read-only:
no events, no category writes.

```bash
cd backend
uv run flask --app app classification evaluate
uv run flask --app app classification evaluate --k 10 --min-confidence 0.6
```

Reported honestly, with no target line and no pass/fail verdict:
`coverage`, `abstention rate`, `accuracy among classified`,
`overall accuracy (abstain = miss)`, `forced accuracy (gates off)`,
`confidence (correct vs wrong)`, abstention reasons and a confusion
matrix — K and thresholds accept flags so different reasonable settings
can be compared and the real numbers documented afterwards.

> **The embedding provider is always printed in the header.** With
> `FakeEmbeddingProvider` the report states loudly that it validates the
> evaluation **mechanics only** — fake vectors carry no semantic meaning,
> so those accuracies say nothing about classification quality. Real
> semantic numbers come from re-running with the free-tier Gemini
> provider (~36 embedding calls, still **USD 0**, optional).

### Tests

The SQLite suite covers the pure vote and every gate (hand-computable
numbers), the API flows (never breaks creation, rollback on failure,
abstention writes nothing, human correction, no-op provenance, only
creation classifies) and the dataset/metrics/CLI contract. The
`postgres`-marked tests in `tests/test_classification_pg.py` cover what
SQLite cannot execute: the real eligibility matrix (self, uncategorized,
inactive, `AI`, stale-model exclusion — the feedback-loop guard), an
end-to-end POST classified over real cosine distance, the authentic
"AI twin is not evidence" scenario, and a read-only smoke of the
evaluation CLI. No test ever calls Gemini.

## Frontend (Phase 4)

React + TypeScript SPA that talks to the existing API through Vite's dev
proxy.

- **Stack:** React 19, TypeScript, Vite 8, React Router 7, CSS Modules
  (+ `tokens.css` design variables), lucide-react icons, ESLint, Vitest.
  No UI framework, no state library, no HTTP client beyond native `fetch`.
- **Pages / routes:**
  - `/` Dashboard — headline counters + priority/status CSS bars
    (`GET /api/dashboard/summary`)
  - `/tickets` — table with `status`/`priority`/`category_id` filters and
    the page number kept in the URL; real backend pagination (20 per page)
  - `/tickets/new` — create form (no category field: the classifier gets
    the first word; priority defaults to MEDIUM)
  - `/tickets/:ticket_number` — detail with the classification block,
    inline editing of status/priority/category/assignee (`PATCH`, the
    backend stays the authority) and the full event history

### Start backend + frontend

```bash
# terminal 1 — backend (from repo root)
docker compose up -d --wait
cd backend && uv run flask --app app run --port 5001

# terminal 2 — frontend
cd frontend
npm install
npm run dev            # http://localhost:5173
```

The Vite dev server proxies `/api` to `http://127.0.0.1:5001`
(override with `VITE_PROXY_TARGET`), so development needs **no CORS** —
and none is configured. The `--port 5001` above matches that proxy
default; running the backend on another port just needs the matching
`VITE_PROXY_TARGET`.

### Frontend commands

```bash
cd frontend
npm run build    # tsc -b + vite build (type check + bundle)
npm run lint     # eslint
npm run test     # vitest (pure logic: formatters, transition matrix)
```

### Fake vs. semantic demo (honesty rules)

- Normal development/demo: `EMBEDDING_PROVIDER=fake` and
  `CLASSIFICATION_ENABLED` unset → tickets stay **Uncategorized** and the
  UI shows the real abstention copy. Nothing about the classification is
  faked client-side.
- A **real** semantic demo needs the free-tier Gemini provider on fresh
  vectors: `EMBEDDING_PROVIDER=gemini` + `CLASSIFICATION_ENABLED=true` +
  `flask embeddings backfill` (only embeds rows where `embedding IS NULL`,
  so a database previously embedded by `fake` must be reset first).
  The UI renders whatever the API returns — no classification results,
  confidences or AI events are hardcoded.
- The UI never shows "probability": a classified ticket renders
  `Confidence score: XX%` (the heuristic — see
  [Automatic classification](#automatic-classification-phase-3--milestone-2)).

## Domain model

Four entities, designed for integrity, traceability and a future AI
classification phase:

| Entity | Purpose | Notes |
|---|---|---|
| `User` | People who request, receive or act on tickets | No auth yet; deactivated via `is_active` |
| `Category` | Functional categories (Access, Hardware, ...) | Data, not an enum — administrable and AI-friendly; deactivated via `is_active` |
| `Ticket` | The central entity | UUID PK + human `ticket_number` (`SUP-000001`); `category_id` nullable on purpose; `category_source` (`MANUAL`/`AI`, the classifier's feedback-loop guard) and `classification_confidence` (nullable heuristic score, 0..1) record how the current category got there |
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
    services/      # business rules (ticket, dashboard, embedding, classification, evaluation)
    embeddings/    # EmbeddingProvider contract, Gemini/fake providers, text builder
    evaluation/    # fictional 36-ticket dataset for classifier evaluation
    repositories/  # SQL only (ticket, user, category)
    commands.py    # Flask CLI (flask seed, flask embeddings, flask classification)
    config.py      # configuration from environment variables + classifier gates
    errors.py      # ApiError hierarchy → JSON error envelope
    extensions.py  # db (Flask-SQLAlchemy) and migrate (Flask-Migrate)
    models/        # domain model (User, Category, Ticket, TicketEvent)
  tests/           # pytest, in-memory SQLite (+ optional postgres-marked tests)
  migrations/      # Alembic revisions (Flask-Migrate)
frontend/          # React + TypeScript UI (Vite dev server, /api dev proxy)
docker-compose.yml # PostgreSQL 17 + pgvector service
```

Architecture: **Routes → Services → Repositories → PostgreSQL**. Routes stay
thin (parse input, call the service, serialize), services own validation,
business rules and the transaction boundary, repositories contain SQL only.
Embeddings follow the same rule: only the service layer decides when to
call the provider, and only after the ticket transaction has committed.
