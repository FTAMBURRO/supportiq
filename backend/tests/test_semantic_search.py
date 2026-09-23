"""Real PostgreSQL + pgvector behaviour (marked ``postgres``).

Declared honestly: SQLite (the default suite) creates and round-trips
the ``vector(768)`` column but CANNOT execute pgvector operators such
as ``<=>`` — those exist only in the real extension. This file covers
what SQLite cannot: extension presence, real vector storage, cosine
search, ranking and similarity math. It skips itself with a clear
message unless ``TEST_DATABASE_URL`` points at a PostgreSQL with
pgvector (see ``conftest.pg_app``).

The fake provider is used throughout: the pipeline is under test, not
the model. Semantic *quality* (e.g. Network above Billing) is verified
manually with the real Gemini free tier — never asserted as a fragile
exact-result test.
"""

import math

import pytest
from sqlalchemy import text

from app.models import Ticket
from app.repositories.ticket_repository import TicketRepository

pytestmark = pytest.mark.postgres


def _seed(pg_db):
    """Minimal reference rows (the schema is rebuilt per test)."""
    from app.models import Category, User

    requester = User(
        email="pg.requester@supportiq.test", full_name="PG Requester"
    )
    category = Category(name="Network", slug="network")
    pg_db.session.add_all([requester, category])
    pg_db.session.commit()
    return requester, category


def _vector(ones: dict[int, float] | None = None):
    """A 768-dim vector with 1.0 (or the given value) at those indexes."""
    vector = [0.0] * 768
    for index, value in (ones or {}).items():
        vector[index] = value
    return vector


def test_vector_extension_is_active(pg_db):
    version = pg_db.session.execute(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar_one()
    assert version  # e.g. "0.8.6"


def test_vector768_roundtrip_through_the_api(pg_db, pg_client, pg_app):
    requester, _ = _seed(pg_db)
    response = pg_client.post(
        "/api/tickets",
        json={
            "title": "Cannot connect to office Wi-Fi",
            "description": "My laptop stopped connecting to the wireless network.",
            "requester_id": str(requester.id),
        },
    )
    assert response.status_code == 201

    dims, model = pg_db.session.execute(
        text(
            "SELECT vector_dims(embedding), embedding_model "
            "FROM tickets WHERE ticket_number = :number"
        ),
        {"number": response.get_json()["ticket_number"]},
    ).one()
    assert dims == 768
    assert model == pg_app.config["EMBEDDING_MODEL"]


def test_cosine_search_ranks_best_first_with_correct_similarity(pg_db):
    requester, _ = _seed(pg_db)
    exact = _vector({0: 1.0})
    near = _vector({0: 1.0, 1: 0.1})  # cos = 1/sqrt(1.01)
    orthogonal = _vector({1: 1.0})  # cos = 0

    for title, vector in (
        ("exact", exact),
        ("near", near),
        ("orthogonal", orthogonal),
    ):
        pg_db.session.add(
            Ticket(
                title=title,
                description=f"{title} (pg fixture)",
                requester=requester,
                embedding=vector,
                embedding_model="fixture-model",
            )
        )
    pg_db.session.commit()

    results = TicketRepository().find_similar(
        exact, model="fixture-model", limit=5
    )

    assert [ticket.title for ticket, _ in results] == [
        "exact",
        "near",
        "orthogonal",
    ]
    similarities = [similarity for _, similarity in results]
    assert similarities[0] == pytest.approx(1.0, abs=1e-5)
    assert similarities[1] == pytest.approx(1 / math.sqrt(1.01), abs=1e-4)
    assert similarities[2] == pytest.approx(0.0, abs=1e-5)
    assert similarities == sorted(similarities, reverse=True)


def test_search_skips_other_models_and_nulls_and_honours_limit(pg_db):
    requester, _ = _seed(pg_db)
    exact = _vector({0: 1.0})
    near = _vector({0: 1.0, 1: 0.1})
    rows = (
        ("current-a", exact, "current-model"),
        ("current-b", near, "current-model"),
        ("old-model", exact, "previous-model"),  # different embedding space
        ("no-embedding", None, "current-model"),  # pending backfill
    )
    for title, vector, model in rows:
        pg_db.session.add(
            Ticket(
                title=title,
                description=f"{title} (pg fixture)",
                requester=requester,
                embedding=vector,
                embedding_model=model,
            )
        )
    pg_db.session.commit()

    repo = TicketRepository()
    all_results = repo.find_similar(exact, model="current-model", limit=20)
    assert [ticket.title for ticket, _ in all_results] == [
        "current-a",
        "current-b",
    ]

    limited = repo.find_similar(exact, model="current-model", limit=1)
    assert [ticket.title for ticket, _ in limited] == ["current-a"]


def test_similar_cli_reuses_the_whole_pipeline(pg_db, pg_client, pg_app):
    requester, _ = _seed(pg_db)
    title = "Cannot connect to office Wi-Fi"
    description = "My laptop stopped connecting to the wireless network."
    created = pg_client.post(
        "/api/tickets",
        json={
            "title": title,
            "description": description,
            "requester_id": str(requester.id),
        },
    )
    assert created.status_code == 201
    best_number = created.get_json()["ticket_number"]
    other = pg_client.post(
        "/api/tickets",
        json={
            "title": "Invoice charged twice",
            "description": "The customer was billed two times.",
            "requester_id": str(requester.id),
        },
    )
    other_number = other.get_json()["ticket_number"]

    # Same title/description as the stored ticket: the fake provider is
    # deterministic, so the query vector is identical → similarity 1.0.
    result = pg_app.test_cli_runner().invoke(
        args=[
            "embeddings",
            "similar",
            "--title", title,
            "--description", description,
            "--limit", "5",
        ]
    )

    assert result.exit_code == 0
    assert "1.0000" in result.output  # exact match ranks with similarity 1
    assert result.output.index(best_number) < result.output.index(other_number)
