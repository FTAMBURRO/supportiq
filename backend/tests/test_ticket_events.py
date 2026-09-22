"""GET /api/tickets/<ticket_number>/events."""

import uuid

EVENT_KEYS = {"id", "type", "actor", "data", "created_at"}


def _create(client, payload, **overrides):
    response = client.post("/api/tickets", json=dict(payload, **overrides))
    assert response.status_code == 201
    return response.get_json()


def _patch(client, ticket_number, payload):
    response = client.patch(f"/api/tickets/{ticket_number}", json=payload)
    assert response.status_code == 200
    return response.get_json()


def test_fresh_ticket_has_created_event_with_actor(
    db, client, seed_data, ticket_payload
):
    created = _create(client, ticket_payload)

    response = client.get(f"/api/tickets/{created['ticket_number']}/events")

    assert response.status_code == 200
    items = response.get_json()["items"]
    assert len(items) == 1

    event = items[0]
    assert set(event) == EVENT_KEYS
    assert event["type"] == "TICKET_CREATED"
    assert event["data"] == {}
    assert event["actor"] == {
        "id": str(seed_data["requester"].id),
        "full_name": "Requester",
        "email": "requester@supportiq.test",
    }
    assert event["created_at"] is not None


def test_timeline_is_chronological_with_null_actors_and_data(
    db, client, seed_data, ticket_payload
):
    created = _create(client, ticket_payload)
    number = created["ticket_number"]
    _patch(client, number, {"status": "IN_PROGRESS"})
    _patch(client, number, {"priority": "URGENT"})

    items = client.get(f"/api/tickets/{number}/events").get_json()["items"]

    # ASC order: creation first, then the two changes in request order.
    assert [event["type"] for event in items] == [
        "TICKET_CREATED",
        "STATUS_CHANGED",
        "PRIORITY_CHANGED",
    ]
    timestamps = [event["created_at"] for event in items]
    assert timestamps == sorted(timestamps)

    # PATCH-generated events have no actor yet (no auth).
    assert items[0]["actor"] is not None
    assert items[1]["actor"] is None
    assert items[2]["actor"] is None

    # data keeps the stored JSON exactly.
    assert items[1]["data"] == {"from": "OPEN", "to": "IN_PROGRESS"}
    assert items[2]["data"] == {"from": "MEDIUM", "to": "URGENT"}


def test_events_are_scoped_to_their_ticket(db, client, ticket_payload):
    first = _create(client, ticket_payload, title="First")
    second = _create(client, ticket_payload, title="Second")
    _patch(client, first["ticket_number"], {"status": "IN_PROGRESS"})

    items = client.get(
        f"/api/tickets/{second['ticket_number']}/events"
    ).get_json()["items"]

    assert [event["type"] for event in items] == ["TICKET_CREATED"]


def test_unknown_ticket_is_404(db, client):
    response = client.get("/api/tickets/SUP-999999/events")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_malformed_ticket_number_is_404(db, client):
    response = client.get("/api/tickets/whatever/events")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_event_ids_are_uuid_strings(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    event = client.get(
        f"/api/tickets/{created['ticket_number']}/events"
    ).get_json()["items"][0]

    assert str(uuid.UUID(event["id"])) == event["id"]
