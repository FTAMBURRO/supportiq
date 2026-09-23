"""POST/PATCH classification flows over the API (SQLite suite).

Classification is disabled in TestingConfig on purpose: these tests flip
it explicitly and replace the evidence loader with controlled votes —
exactly how the approved design intends the seams to be used. pgvector's
real cosine query and its eligibility filters are PostgreSQL-only and
live in test_classification_pg.py.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models import Category, TicketEvent
from app.services import classification_service as cs


def _events(db, ticket_id):
    """Persisted events for a ticket (id as returned by the API)."""
    query = select(TicketEvent).where(
        TicketEvent.ticket_id == uuid.UUID(ticket_id)
    )
    return list(db.session.execute(query).scalars().all())


def _types(events):
    return [event.event_type.value for event in events]


def _vote(similarity, category, number="SUP-000001"):
    return cs.NeighborVote(
        ticket_id=uuid.uuid4(),
        ticket_number=number,
        category_id=category.id,
        category_slug=category.slug,
        similarity=similarity,
    )


def _enable(app, monkeypatch, votes):
    """Turn classification on and serve fixed evidence from the loader."""
    app.config["CLASSIFICATION_ENABLED"] = True
    monkeypatch.setattr(
        cs, "load_neighbor_votes", lambda ticket, *, k: list(votes)
    )


def _forbid_loader(monkeypatch):
    """Loader that fails the test if it is ever reached."""
    def _boom(ticket, *, k):
        raise AssertionError("evidence loader must not be called here")

    monkeypatch.setattr(cs, "load_neighbor_votes", _boom)


def test_disabled_by_default_the_loader_is_never_reached(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    _forbid_loader(monkeypatch)  # TestingConfig disables classification

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 201  # guard short-circuits before I/O
    body = response.get_json()
    assert body["category_id"] is None
    assert body["category"] is None
    assert body["category_source"] == "MANUAL"
    assert body["classification_confidence"] is None
    assert _types(_events(db, body["id"])) == ["TICKET_CREATED"]


def test_post_classifies_and_persists_a_capped_audit_event(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    access = seed_data["category"]
    _enable(
        app,
        monkeypatch,
        [
            _vote(0.93, access, "SUP-000001"),
            _vote(0.88, access, "SUP-000014"),
            _vote(0.60, access, "SUP-000032"),
            _vote(0.55, access, "SUP-000040"),
        ],
    )

    response = client.post("/api/tickets", json=ticket_payload)
    assert response.status_code == 201

    body = response.get_json()
    assert body["category_id"] == str(access.id)
    assert body["category"] == {
        "id": str(access.id),
        "name": "Access",
        "slug": "access",
    }
    assert body["category_source"] == "AI"
    # All evidence is one category: share = margin = 1, conf = 1 * 0.93.
    assert body["classification_confidence"] == pytest.approx(0.93)

    events = _events(db, body["id"])
    assert _types(events) == ["TICKET_CREATED", "AI_CLASSIFIED"]
    audit = events[1]
    assert audit.actor_id is None  # system event, pre-auth
    assert set(audit.data) == {
        "category_id",
        "category_slug",
        "confidence",
        "share",
        "margin",
        "top_similarity",
        "k",
        "neighbors_used",
        "evidence",
    }
    assert audit.data["category_id"] == str(access.id)
    assert audit.data["category_slug"] == "access"
    assert audit.data["confidence"] == pytest.approx(0.93)
    assert audit.data["share"] == pytest.approx(1.0)
    assert audit.data["margin"] == pytest.approx(1.0)
    assert audit.data["top_similarity"] == pytest.approx(0.93)
    assert audit.data["k"] == 5
    assert audit.data["neighbors_used"] == 4
    assert len(audit.data["evidence"]) == 3  # top-3 cap
    assert audit.data["evidence"][0] == {
        "ticket_number": "SUP-000001",
        "category_slug": "access",
        "similarity": pytest.approx(0.93),
    }
    assert "embedding" not in str(audit.data)  # vectors never serialized


def test_loader_crash_still_creates_the_ticket_untouched(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    app.config["CLASSIFICATION_ENABLED"] = True

    def _crash(ticket, *, k):
        raise RuntimeError("pgvector exploded")

    monkeypatch.setattr(cs, "load_neighbor_votes", _crash)

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 201  # classification never breaks POST
    body = response.get_json()
    assert body["category_id"] is None
    assert body["category_source"] == "MANUAL"
    assert body["classification_confidence"] is None
    assert _types(_events(db, body["id"])) == ["TICKET_CREATED"]


def test_crash_after_the_assignment_is_rolled_back(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    access = seed_data["category"]
    _enable(app, monkeypatch, [_vote(0.95, access)])

    def _crash(event):  # fails inside the classification transaction
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(cs._ticket_repo, "add_event", _crash)

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 201
    body = response.get_json()
    # The half-done assignment must be gone: degraded state only.
    assert body["category_id"] is None
    assert body["category_source"] == "MANUAL"
    assert body["classification_confidence"] is None
    assert _types(_events(db, body["id"])) == ["TICKET_CREATED"]


def test_no_usable_evidence_abstains_silently(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    _enable(app, monkeypatch, [])

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 201
    body = response.get_json()
    assert body["category_id"] is None
    assert body["classification_confidence"] is None
    assert _types(_events(db, body["id"])) == ["TICKET_CREATED"]


def test_weakly_relevant_evidence_abstains(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    access = seed_data["category"]
    _enable(
        app,
        monkeypatch,
        [
            _vote(0.31, access, "SUP-1"),
            _vote(0.29, access, "SUP-2"),
            _vote(0.27, access, "SUP-3"),
        ],
    )

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 201
    assert response.get_json()["category_id"] is None
    # Abstention writes nothing: still exactly one event.
    assert _types(_events(db, response.get_json()["id"])) == ["TICKET_CREATED"]


def test_a_category_provided_by_the_requester_skips_classification(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    access = seed_data["category"]
    app.config["CLASSIFICATION_ENABLED"] = True
    _forbid_loader(monkeypatch)  # guard fires before any evidence query

    response = client.post(
        "/api/tickets",
        json=dict(ticket_payload, category_id=str(access.id)),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["category_id"] == str(access.id)
    assert body["category_source"] == "MANUAL"  # provenance stays human
    assert body["classification_confidence"] is None


def test_human_correction_marks_manual_and_clears_confidence(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    hardware = Category(name="Hardware", slug="hardware")
    db.session.add(hardware)
    db.session.commit()

    access = seed_data["category"]
    _enable(app, monkeypatch, [_vote(0.93, access)])
    created = client.post("/api/tickets", json=ticket_payload).get_json()
    assert created["category_source"] == "AI"
    assert created["classification_confidence"] is not None

    corrected = client.patch(
        f"/api/tickets/{created['ticket_number']}",
        json={"category_id": str(hardware.id)},
    )
    assert corrected.status_code == 200

    body = corrected.get_json()
    assert body["category_id"] == str(hardware.id)
    assert body["category"]["slug"] == "hardware"
    assert body["category_source"] == "MANUAL"  # human evidence again
    assert body["classification_confidence"] is None

    events = _events(db, created["id"])
    assert _types(events) == [
        "TICKET_CREATED",
        "AI_CLASSIFIED",
        "CATEGORY_CHANGED",
    ]  # the AI decision stays in history; the correction is auditable
    assert events[2].data == {
        "from": str(access.id),
        "to": str(hardware.id),
    }


def test_noop_and_unrelated_patches_keep_ai_provenance(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    access = seed_data["category"]
    _enable(app, monkeypatch, [_vote(0.93, access)])
    created = client.post("/api/tickets", json=ticket_payload).get_json()

    same = client.patch(
        f"/api/tickets/{created['ticket_number']}",
        json={"category_id": str(access.id)},
    )
    assert same.status_code == 200
    untouched = client.patch(
        f"/api/tickets/{created['ticket_number']}",
        json={"priority": "HIGH"},
    )
    assert untouched.status_code == 200

    body = untouched.get_json()
    assert body["category_source"] == "AI"  # nothing human happened
    assert body["classification_confidence"] == pytest.approx(0.93)
    # No CATEGORY_CHANGED: re-sending the same id is not a correction.
    assert _types(_events(db, created["id"])) == [
        "TICKET_CREATED",
        "AI_CLASSIFIED",
        "PRIORITY_CHANGED",
    ]


def test_clearing_the_category_resets_provenance_to_manual(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    access = seed_data["category"]
    _enable(app, monkeypatch, [_vote(0.93, access)])
    created = client.post("/api/tickets", json=ticket_payload).get_json()

    cleared = client.patch(
        f"/api/tickets/{created['ticket_number']}",
        json={"category_id": None},
    )
    assert cleared.status_code == 200

    body = cleared.get_json()
    assert body["category_id"] is None
    assert body["category"] is None
    assert body["category_source"] == "MANUAL"
    assert body["classification_confidence"] is None
    assert _types(_events(db, created["id"])) == [
        "TICKET_CREATED",
        "AI_CLASSIFIED",
        "CATEGORY_CHANGED",
    ]


def test_only_creation_runs_classification_never_a_title_edit(
    app, client, db, seed_data, ticket_payload, monkeypatch
):
    calls = []

    def _spy(ticket, *, k):
        calls.append(ticket.ticket_number)
        return []

    app.config["CLASSIFICATION_ENABLED"] = True
    monkeypatch.setattr(cs, "load_neighbor_votes", _spy)

    created = client.post("/api/tickets", json=ticket_payload).get_json()
    assert len(calls) == 1

    edited = client.patch(
        f"/api/tickets/{created['ticket_number']}",
        json={"title": "Renamed after creation"},
    )
    assert edited.status_code == 200
    assert len(calls) == 1  # title edits re-embed, they never reclassify
