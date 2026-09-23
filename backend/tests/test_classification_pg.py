"""Real PostgreSQL + pgvector classification behaviour (marked ``postgres``).

SQLite cannot execute the ``<=>`` operator, so everything that depends
on the real vector query lives here: the evidence eligibility matrix
(feedback-loop guard included), an end-to-end POST that classifies from
actual cosine neighbours, the authentic "AI output is not evidence"
scenario, and the leave-one-out evaluation command over real rows.

The fake provider is used throughout: the pipeline is under test, never
a paid model, and the CLI itself states that fake results validate
mechanics only.
"""

import re

import pytest

from app.models import (
    Category,
    CategorySource,
    Ticket,
    TicketEvent,
    TicketEventType,
    User,
)
from app.repositories.ticket_repository import TicketRepository

pytestmark = pytest.mark.postgres

_MODEL = "fixture-model"


def _reference(pg_db):
    """Minimal reference rows (the schema is rebuilt per test)."""
    requester = User(
        email="pg.classifier@supportiq.test", full_name="PG Classifier"
    )
    network = Category(name="Network", slug="network")
    billing = Category(name="Billing", slug="billing")
    legacy = Category(name="Legacy", slug="legacy", is_active=False)
    pg_db.session.add_all([requester, network, billing, legacy])
    pg_db.session.commit()
    return requester, {"network": network, "billing": billing, "legacy": legacy}


def _vector(first: float = 1.0):
    """A 768-dim vector with ``first`` at index 0 (cosine-exact matches)."""
    vector = [0.0] * 768
    vector[0] = first
    return vector


def _add_ticket(pg_db, requester, title, category, *, vector, model=_MODEL,
                source=None):
    ticket = Ticket(
        title=title,
        description=f"{title} (pg fixture)",
        requester=requester,
        category=category,
        embedding=vector,
        embedding_model=model,
    )
    if source is not None:
        ticket.category_source = source
    pg_db.session.add(ticket)
    return ticket


def test_evidence_query_excludes_self_uncategorized_inactive_ai_and_stale_models(
    pg_db, pg_app
):
    """The eligibility matrix, including the feedback-loop guard."""
    requester, cats = _reference(pg_db)
    exact = _vector()

    eligible = _add_ticket(pg_db, requester, "eligible", cats["network"],
                           vector=exact)
    _add_ticket(pg_db, requester, "uncategorized", None, vector=exact)
    _add_ticket(pg_db, requester, "inactive category", cats["legacy"],
                vector=exact)
    _add_ticket(pg_db, requester, "ai assigned", cats["billing"],
                vector=exact, source=CategorySource.AI)
    _add_ticket(pg_db, requester, "stale model", cats["network"],
                vector=exact, model="previous-model")
    _add_ticket(pg_db, requester, "self", cats["network"], vector=exact)
    pg_db.session.commit()

    repo = TicketRepository()
    results = repo.find_classification_neighbors(
        exclude_ticket_id=eligible.id,
        embedding=exact,
        model=_MODEL,
        k=10,
    )

    # Everything else was filtered: AI output must never be evidence,
    # inactive/uncategorized rows cannot vote, other models are other
    # embedding spaces, and self is excluded.
    assert [ticket.title for ticket, _ in results] == ["self"]
    assert results[0][1] == pytest.approx(1.0, abs=1e-5)

    without_self = repo.find_classification_neighbors(
        exclude_ticket_id=results[0][0].id,
        embedding=exact,
        model=_MODEL,
        k=10,
    )
    # Complementary view: with 'self' out, the eligible row appears.
    assert [ticket.title for ticket, _ in without_self] == ["eligible"]


def test_post_classifies_from_real_cosine_evidence(pg_db, pg_client, pg_app):
    requester, cats = _reference(pg_db)
    title = "Office Wi-Fi keeps disconnecting"
    description = "The wireless network drops every few minutes in the morning."

    # Historical evidence: a manually categorized ticket embedded through
    # the real create flow (fake provider is deterministic per text).
    evidence = pg_client.post(
        "/api/tickets",
        json={
            "title": title,
            "description": description,
            "requester_id": str(requester.id),
            "category_id": str(cats["network"].id),
        },
    )
    assert evidence.status_code == 201
    evidence_number = evidence.get_json()["ticket_number"]

    pg_app.config["CLASSIFICATION_ENABLED"] = True
    try:
        response = pg_client.post(
            "/api/tickets",
            json={
                "title": title,
                "description": description,
                "requester_id": str(requester.id),
            },
        )
    finally:
        pg_app.config["CLASSIFICATION_ENABLED"] = False

    assert response.status_code == 201
    body = response.get_json()
    # Identical text -> identical fake vector -> similarity exactly 1.0.
    assert body["category_id"] == str(cats["network"].id)
    assert body["category"] == {
        "id": str(cats["network"].id),
        "name": "Network",
        "slug": "network",
    }
    assert body["category_source"] == "AI"
    assert body["classification_confidence"] == pytest.approx(1.0)

    events = pg_client.get(
        f"/api/tickets/{body['ticket_number']}/events"
    ).get_json()["items"]
    assert [event["type"] for event in events] == [
        "TICKET_CREATED",
        "AI_CLASSIFIED",
    ]
    data = events[1]["data"]
    assert events[1]["actor"] is None
    assert data["category_slug"] == "network"
    assert data["confidence"] == pytest.approx(1.0)
    assert data["share"] == pytest.approx(1.0)
    assert data["margin"] == pytest.approx(1.0)
    assert data["top_similarity"] == pytest.approx(1.0, abs=1e-4)
    assert data["k"] == 5
    assert data["neighbors_used"] == 1
    assert data["evidence"] == [
        {
            "ticket_number": evidence_number,
            "category_slug": "network",
            "similarity": pytest.approx(1.0, abs=1e-4),
        }
    ]


def test_ai_classified_ticket_is_not_evidence_for_the_next_one(
    pg_db, pg_client, pg_app
):
    """The authentic feedback-loop scenario, end to end."""
    from app.embeddings import get_provider
    from app.embeddings.text import build_ticket_embedding_text

    requester, cats = _reference(pg_db)
    title = "Printer queue stuck in the finance floor"
    description = "Print jobs never leave the queue and the printer shows offline."
    payload = {
        "title": title,
        "description": description,
        "requester_id": str(requester.id),
    }

    evidence = pg_client.post(
        "/api/tickets",
        json=dict(payload, category_id=str(cats["network"].id)),
    )
    assert evidence.status_code == 201

    pg_app.config["CLASSIFICATION_ENABLED"] = True
    try:
        classified = pg_client.post("/api/tickets", json=payload)
    finally:
        pg_app.config["CLASSIFICATION_ENABLED"] = False
    assert classified.status_code == 201

    classified_body = classified.get_json()
    assert classified_body["category_source"] == "AI"
    assert classified_body["category_id"] is not None  # premise: it was AI-set

    # Next ticket with the same text: the AI-set twin must not vote.
    vector = get_provider().embed(
        build_ticket_embedding_text(title, description)
    )
    results = TicketRepository().find_classification_neighbors(
        exclude_ticket_id=evidence.get_json()["id"],
        embedding=vector,
        model=pg_app.config["EMBEDDING_MODEL"],
        k=10,
    )
    assert results == []  # only candidate was the AI-classified twin


def test_evaluate_cli_runs_over_real_rows_read_only(pg_db, pg_app):
    runner = pg_app.test_cli_runner()
    assert runner.invoke(args=["seed"]).exit_code == 0

    pending = runner.invoke(args=["classification", "evaluate"])
    assert pending.exit_code == 1  # honest stop: embeddings missing
    assert "dataset: 36 demo tickets present" in pending.output
    assert "backfill" in pending.output

    backfill = runner.invoke(args=["embeddings", "backfill"])
    assert backfill.exit_code == 0
    assert "remaining: 0" in backfill.output

    report = runner.invoke(args=["classification", "evaluate"])
    assert report.exit_code == 0
    out = report.output
    # The fake-provider disclaimer must be visible in the real output.
    assert "FakeEmbeddingProvider" in out
    assert "MECHANICS ONLY" in out
    assert "provider:   fake" in out
    assert "K:          5" in out
    assert "coverage (classified):" in out
    assert re.search(r"coverage \(classified\):\s+\d+/36", out)
    assert "accuracy among classified:" in out
    assert "forced accuracy (gates off):" in out
    assert "confidence (correct):" in out
    assert "confidence (wrong):" in out
    assert "confusion matrix" in out

    # Read-only guarantee: evaluation creates no events and no tickets.
    assert pg_db.session.query(Ticket).count() == 36
    assert pg_db.session.query(TicketEvent).count() == 0
    assert (
        pg_db.session.query(TicketEvent)
        .filter(TicketEvent.event_type == TicketEventType.AI_CLASSIFIED)
        .count()
        == 0
    )
