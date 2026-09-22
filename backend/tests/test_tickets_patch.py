"""PATCH /api/tickets/<ticket_number>."""

import uuid

from sqlalchemy import select

from app.models import TicketEvent


def _events(db, ticket_id):
    """Persisted events for a ticket (id as returned by the API), oldest first."""
    query = (
        select(TicketEvent)
        .where(TicketEvent.ticket_id == uuid.UUID(ticket_id))
        .order_by(TicketEvent.created_at)
    )
    return db.session.execute(query).scalars().all()


def _types(events):
    return [event.event_type.value for event in events]


def _create(client, payload, **overrides):
    response = client.post("/api/tickets", json=dict(payload, **overrides))
    assert response.status_code == 201
    return response.get_json()


def _patch(client, ticket_number, payload):
    return client.patch(f"/api/tickets/{ticket_number}", json=payload)


# --- field updates ----------------------------------------------------------


def test_update_title_and_description(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"title": "New title", "description": "New description"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["title"] == "New title"
    assert body["description"] == "New description"
    assert body["status"] == "OPEN"  # untouched
    assert body["ticket_number"] == created["ticket_number"]
    # Text-only edits do not generate events.
    assert _types(_events(db, created["id"])) == ["TICKET_CREATED"]


def test_update_persists(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    _patch(client, created["ticket_number"], {"title": "Persisted"})

    body = client.get(f"/api/tickets/{created['ticket_number']}").get_json()
    assert body["title"] == "Persisted"


def test_empty_body_is_200_noop(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(client, created["ticket_number"], {})

    assert response.status_code == 200
    assert _types(_events(db, created["id"])) == ["TICKET_CREATED"]


def test_same_values_are_noop(db, client, seed_data, ticket_payload):
    created = _create(client, ticket_payload, priority="HIGH")

    response = _patch(
        client,
        created["ticket_number"],
        {"priority": "HIGH", "title": ticket_payload["title"]},
    )

    assert response.status_code == 200
    assert _types(_events(db, created["id"])) == ["TICKET_CREATED"]


# --- status transitions -----------------------------------------------------


def test_open_to_in_progress(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client, created["ticket_number"], {"status": "IN_PROGRESS"}
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "IN_PROGRESS"

    events = _events(db, created["id"])
    assert _types(events) == ["TICKET_CREATED", "STATUS_CHANGED"]
    assert events[1].data == {"from": "OPEN", "to": "IN_PROGRESS"}
    assert events[1].actor_id is None  # no auth yet: never taken from the body


def test_open_to_resolved_sets_resolved_at(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    body = _patch(client, created["ticket_number"], {"status": "RESOLVED"}).get_json()

    assert body["status"] == "RESOLVED"
    assert body["resolved_at"] is not None
    assert body["closed_at"] is None


def test_resolved_to_in_progress_clears_resolved_at(db, client, ticket_payload):
    created = _create(client, ticket_payload)
    _patch(client, created["ticket_number"], {"status": "RESOLVED"})

    body = _patch(
        client, created["ticket_number"], {"status": "IN_PROGRESS"}
    ).get_json()

    assert body["status"] == "IN_PROGRESS"
    assert body["resolved_at"] is None
    assert body["closed_at"] is None


def test_resolved_to_closed_sets_closed_at(db, client, ticket_payload):
    created = _create(client, ticket_payload)
    _patch(client, created["ticket_number"], {"status": "RESOLVED"})

    body = _patch(client, created["ticket_number"], {"status": "CLOSED"}).get_json()

    assert body["status"] == "CLOSED"
    assert body["resolved_at"] is not None
    assert body["closed_at"] is not None


def test_open_to_closed_is_409(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(client, created["ticket_number"], {"status": "CLOSED"})

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


def test_rejected_transition_changes_nothing(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"status": "CLOSED", "priority": "URGENT"},
    )

    assert response.status_code == 409
    body = client.get(f"/api/tickets/{created['ticket_number']}").get_json()
    assert body["status"] == "OPEN"
    assert body["priority"] == "MEDIUM"
    assert _types(_events(db, created["id"])) == ["TICKET_CREATED"]


def test_closed_ticket_is_locked_for_status(db, client, ticket_payload):
    created = _create(client, ticket_payload)
    _patch(client, created["ticket_number"], {"status": "RESOLVED"})
    _patch(client, created["ticket_number"], {"status": "CLOSED"})

    response = _patch(client, created["ticket_number"], {"status": "IN_PROGRESS"})

    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


def test_closed_ticket_still_allows_text_edits(db, client, ticket_payload):
    created = _create(client, ticket_payload)
    _patch(client, created["ticket_number"], {"status": "RESOLVED"})
    _patch(client, created["ticket_number"], {"status": "CLOSED"})

    response = _patch(client, created["ticket_number"], {"title": "Final note"})

    assert response.status_code == 200
    assert response.get_json()["title"] == "Final note"


def test_invalid_status_enum_is_400(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(client, created["ticket_number"], {"status": "DONE"})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_VALUE"


def test_status_with_wrong_type_is_400(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(client, created["ticket_number"], {"status": 3})

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_TYPE"


# --- priority / assignee / category ----------------------------------------


def test_priority_change_generates_event(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(client, created["ticket_number"], {"priority": "URGENT"})

    assert response.status_code == 200
    assert response.get_json()["priority"] == "URGENT"

    events = _events(db, created["id"])
    assert _types(events) == ["TICKET_CREATED", "PRIORITY_CHANGED"]
    assert events[1].data == {"from": "MEDIUM", "to": "URGENT"}


def test_assignment_generates_event(db, client, seed_data, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"assignee_id": str(seed_data["assignee"].id)},
    )

    assert response.status_code == 200
    assert response.get_json()["assignee_id"] == str(seed_data["assignee"].id)

    events = _events(db, created["id"])
    assert _types(events) == ["TICKET_CREATED", "ASSIGNED"]
    assert events[1].data == {
        "from": None,
        "to": str(seed_data["assignee"].id),
    }


def test_unassignment_generates_event(db, client, seed_data, ticket_payload):
    created = _create(
        client, ticket_payload, assignee_id=str(seed_data["assignee"].id)
    )

    response = _patch(client, created["ticket_number"], {"assignee_id": None})

    assert response.status_code == 200
    assert response.get_json()["assignee_id"] is None

    events = _events(db, created["id"])
    assert _types(events) == ["TICKET_CREATED", "ASSIGNED"]
    assert events[1].data["to"] is None


def test_reassignment_to_same_user_is_noop(db, client, seed_data, ticket_payload):
    created = _create(
        client, ticket_payload, assignee_id=str(seed_data["assignee"].id)
    )

    response = _patch(
        client,
        created["ticket_number"],
        {"assignee_id": str(seed_data["assignee"].id)},
    )

    assert response.status_code == 200
    assert _types(_events(db, created["id"])) == ["TICKET_CREATED"]


def test_category_change_generates_event(db, client, seed_data, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"category_id": str(seed_data["category"].id)},
    )

    assert response.status_code == 200
    assert response.get_json()["category_id"] == str(seed_data["category"].id)

    events = _events(db, created["id"])
    assert _types(events) == ["TICKET_CREATED", "CATEGORY_CHANGED"]
    assert events[1].data == {
        "from": None,
        "to": str(seed_data["category"].id),
    }


def test_multiple_changes_in_one_patch(db, client, seed_data, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {
            "status": "IN_PROGRESS",
            "priority": "HIGH",
            "assignee_id": str(seed_data["assignee"].id),
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "IN_PROGRESS"
    assert body["priority"] == "HIGH"
    assert body["assignee_id"] == str(seed_data["assignee"].id)

    assert _types(_events(db, created["id"])) == [
        "TICKET_CREATED",
        "STATUS_CHANGED",
        "PRIORITY_CHANGED",
        "ASSIGNED",
    ]


# --- validation and errors --------------------------------------------------


def test_forbidden_fields_are_400(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"requester_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "UNKNOWN_FIELD"


def test_read_only_identity_fields_are_400(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"id": created["id"], "ticket_number": "SUP-999999"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "UNKNOWN_FIELD"


def test_actor_id_in_body_is_rejected(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client, created["ticket_number"], {"actor_id": created["requester_id"]}
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "UNKNOWN_FIELD"


def test_blank_title_is_422(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(client, created["ticket_number"], {"title": "   "})

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_nonexistent_assignee_is_422(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"assignee_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_inactive_assignee_is_422(db, client, seed_data, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"assignee_id": str(seed_data["inactive"].id)},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_nonexistent_category_is_422(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"category_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_inactive_category_is_422(db, client, seed_data, ticket_payload):
    created = _create(client, ticket_payload)

    response = _patch(
        client,
        created["ticket_number"],
        {"category_id": str(seed_data["inactive_category"].id)},
    )

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_unknown_ticket_is_404(db, client):
    response = _patch(client, "SUP-999999", {"title": "x"})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_patch_malformed_ticket_number_is_404(db, client):
    response = _patch(client, "whatever", {"title": "x"})

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_patch_malformed_json_is_400(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    response = client.patch(
        f"/api/tickets/{created['ticket_number']}",
        data="{broken",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "MALFORMED_JSON"


def test_patch_events_have_no_actor_but_creation_keeps_actor(
    db, client, seed_data, ticket_payload
):
    created = _create(client, ticket_payload)
    _patch(client, created["ticket_number"], {"status": "IN_PROGRESS"})

    events = _events(db, created["id"])
    assert str(events[0].actor_id) == str(seed_data["requester"].id)
    assert events[1].actor_id is None
