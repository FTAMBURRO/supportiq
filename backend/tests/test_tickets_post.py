"""POST /api/tickets."""

import json
import uuid

from sqlalchemy import select

from app.models import TicketEvent


def _events(db, ticket_id):
    """Read the persisted events for a ticket (id as returned by the API)."""
    query = select(TicketEvent).where(
        TicketEvent.ticket_id == uuid.UUID(ticket_id)
    )
    return db.session.execute(query).scalars().all()


def test_create_returns_201_with_defaults(db, client, seed_data, ticket_payload):
    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 201
    body = response.get_json()
    assert body["ticket_number"].startswith("SUP-")
    assert body["status"] == "OPEN"
    assert body["priority"] == "MEDIUM"
    assert body["assignee_id"] is None
    assert body["category_id"] is None
    assert body["resolved_at"] is None
    assert body["closed_at"] is None
    assert body["requester_id"] == str(seed_data["requester"].id)


def test_create_writes_ticket_created_event(db, client, seed_data, ticket_payload):
    body = client.post("/api/tickets", json=ticket_payload).get_json()

    events = _events(db, body["id"])
    assert [event.event_type.value for event in events] == ["TICKET_CREATED"]
    assert str(events[0].actor_id) == str(seed_data["requester"].id)


def test_create_with_optional_fields(db, client, seed_data, ticket_payload):
    ticket_payload.update(
        {
            "priority": "HIGH",
            "assignee_id": str(seed_data["assignee"].id),
            "category_id": str(seed_data["category"].id),
        }
    )

    body = client.post("/api/tickets", json=ticket_payload).get_json()

    assert body["priority"] == "HIGH"
    assert body["assignee_id"] == str(seed_data["assignee"].id)
    assert body["category_id"] == str(seed_data["category"].id)

    # Spec: an assignee set at creation still produces only TICKET_CREATED.
    events = _events(db, body["id"])
    assert [event.event_type.value for event in events] == ["TICKET_CREATED"]


def test_create_persists_the_ticket(db, client, ticket_payload):
    body = client.post("/api/tickets", json=ticket_payload).get_json()

    fetched = client.get(f"/api/tickets/{body['ticket_number']}")
    assert fetched.status_code == 200
    assert fetched.get_json()["id"] == body["id"]


def test_missing_title_is_422(client, ticket_payload):
    del ticket_payload["title"]

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_blank_title_is_422(client, ticket_payload):
    ticket_payload["title"] = "   "

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_title_longer_than_200_is_422(client, ticket_payload):
    ticket_payload["title"] = "x" * 201

    assert client.post("/api/tickets", json=ticket_payload).status_code == 422


def test_missing_description_is_422(client, ticket_payload):
    del ticket_payload["description"]

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_missing_requester_is_422(client, ticket_payload):
    del ticket_payload["requester_id"]

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_nonexistent_requester_is_422(client, ticket_payload):
    ticket_payload["requester_id"] = "00000000-0000-0000-0000-000000000000"

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_inactive_requester_is_422(client, seed_data, ticket_payload):
    ticket_payload["requester_id"] = str(seed_data["inactive"].id)

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_nonexistent_assignee_is_422(client, ticket_payload):
    ticket_payload["assignee_id"] = "00000000-0000-0000-0000-000000000000"

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 422


def test_nonexistent_category_is_422(client, ticket_payload):
    ticket_payload["category_id"] = "00000000-0000-0000-0000-000000000000"

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 422


def test_inactive_category_is_422(client, seed_data, ticket_payload):
    ticket_payload["category_id"] = str(seed_data["inactive_category"].id)

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 422


def test_invalid_priority_is_400(client, ticket_payload):
    ticket_payload["priority"] = "CRITICAL"

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_VALUE"


def test_priority_with_wrong_type_is_400(client, ticket_payload):
    ticket_payload["priority"] = 5

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_TYPE"


def test_malformed_requester_uuid_is_400(client, ticket_payload):
    ticket_payload["requester_id"] = "not-a-uuid"

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_TYPE"


def test_read_only_fields_are_400(client, ticket_payload):
    ticket_payload["id"] = "00000000-0000-0000-0000-000000000000"
    ticket_payload["ticket_number"] = "SUP-999999"

    response = client.post("/api/tickets", json=ticket_payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "UNKNOWN_FIELD"


def test_status_and_timestamps_are_rejected(client, ticket_payload):
    payload = dict(ticket_payload, status="CLOSED", created_at="2020-01-01")

    response = client.post("/api/tickets", json=payload)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "UNKNOWN_FIELD"


def test_malformed_json_is_400(client):
    response = client.post(
        "/api/tickets",
        data="{not json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "MALFORMED_JSON"


def test_json_array_body_is_400(client):
    response = client.post("/api/tickets", json=[{"title": "x"}])

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "MALFORMED_JSON"


def test_missing_content_type_is_400(client):
    response = client.post("/api/tickets", data=json.dumps({"title": "x"}))

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "MALFORMED_JSON"
