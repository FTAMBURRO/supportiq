"""embed_and_persist / find_similar_tickets behaviour (fake provider).

Covers the degradation contract: tickets never depend on the provider,
embeddings are never stale, and non-text PATCHes never touch them.
"""

import pytest

from app.errors import ValidationError
from app.models import Ticket
from app.services import embedding_service


def _break_provider(app):
    """Make the provider unusable (no key) without touching the code."""
    app.config["EMBEDDING_PROVIDER"] = "gemini"
    app.config["EMBEDDING_API_KEY"] = ""


def test_create_persists_embedding_and_model(app, client, db, ticket_payload):
    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 201
    ticket = db.session.query(Ticket).one()
    assert ticket.embedding is not None
    assert len(ticket.embedding) == 768
    assert ticket.embedding_model == app.config["EMBEDDING_MODEL"]


def test_provider_failure_keeps_ticket_valid_with_null_embedding(
    app, client, db, ticket_payload
):
    _break_provider(app)

    response = client.post("/api/tickets", json=ticket_payload)

    # Creation NEVER fails because the provider failed.
    assert response.status_code == 201
    ticket = db.session.query(Ticket).one()
    assert ticket.embedding is None
    assert ticket.embedding_model is None


@pytest.mark.parametrize(
    ("field", "new_value"),
    [
        ("title", "Laptop cannot reach the office Wi-Fi"),
        ("description", "Wireless connection fails since this morning."),
    ],
)
def test_patch_text_field_invalidates_embedding_in_transaction(
    app, client, db, ticket_payload, field, new_value
):
    created = client.post("/api/tickets", json=ticket_payload)
    assert created.status_code == 201

    # The provider goes down and the embedded text changes at once: the
    # invalidation must still happen, in the PATCH transaction itself.
    _break_provider(app)
    patched = client.patch(
        f"/api/tickets/{created.get_json()['ticket_number']}",
        json={field: new_value},
    )

    assert patched.status_code == 200  # the edit never depends on Gemini
    ticket = db.session.query(Ticket).one()
    # NULL, not the vector of the OLD text: never a stale embedding.
    assert ticket.embedding is None
    assert ticket.embedding_model is None


def test_patch_non_text_fields_never_touch_embedding(
    app, client, db, ticket_payload
):
    created = client.post("/api/tickets", json=ticket_payload)
    ticket_number = created.get_json()["ticket_number"]
    original = list(db.session.query(Ticket).one().embedding)
    assert original

    # Provider down: if status/priority triggered a re-embed or an
    # invalidation, the embedding would now be NULL.
    _break_provider(app)
    patched = client.patch(
        f"/api/tickets/{ticket_number}",
        json={"status": "IN_PROGRESS", "priority": "HIGH"},
    )

    assert patched.status_code == 200
    ticket = db.session.query(Ticket).one()
    assert list(ticket.embedding) == original
    assert ticket.embedding_model is not None


def test_patch_text_regenerates_the_embedding(
    app, client, db, ticket_payload
):
    created = client.post("/api/tickets", json=ticket_payload)
    before = list(db.session.query(Ticket).one().embedding)

    patched = client.patch(
        f"/api/tickets/{created.get_json()['ticket_number']}",
        json={"title": "A completely different problem"},
    )

    assert patched.status_code == 200
    ticket = db.session.query(Ticket).one()
    assert ticket.embedding is not None
    # Deterministic fake: different text MUST yield a different vector.
    assert list(ticket.embedding) != before
    assert ticket.embedding_model == app.config["EMBEDDING_MODEL"]


def test_find_similar_tickets_rejects_limits_outside_range(app):
    # Validation runs before any provider call or SQL, so a bad limit
    # costs no free-tier quota either.
    for limit in (0, 21):
        with pytest.raises(ValidationError):
            embedding_service.find_similar_tickets(
                title="x", description="y", limit=limit
            )
