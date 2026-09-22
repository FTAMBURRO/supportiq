"""GET /api/tickets and GET /api/tickets/<ticket_number>."""


def _create(client, payload, **overrides):
    body = dict(payload, **overrides)
    response = client.post("/api/tickets", json=body)
    assert response.status_code == 201
    return response.get_json()


# --- GET one ticket ---------------------------------------------------------


def test_get_by_ticket_number_returns_200(db, client, seed_data, ticket_payload):
    created = _create(client, ticket_payload)

    response = client.get(f"/api/tickets/{created['ticket_number']}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["id"] == created["id"]
    assert body["ticket_number"] == created["ticket_number"]
    assert body["title"] == ticket_payload["title"]
    assert body["requester_id"] == str(seed_data["requester"].id)


def test_get_does_not_include_events(db, client, ticket_payload):
    created = _create(client, ticket_payload)

    body = client.get(f"/api/tickets/{created['ticket_number']}").get_json()

    assert "events" not in body


def test_get_unknown_ticket_number_is_404(db, client):
    response = client.get("/api/tickets/SUP-999999")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "TICKET_NOT_FOUND"


def test_get_malformed_ticket_number_is_404(db, client):
    response = client.get("/api/tickets/not-a-ticket")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "TICKET_NOT_FOUND"


# --- GET list ---------------------------------------------------------------


def test_list_defaults_to_page_1_and_20(db, client, ticket_payload):
    _create(client, ticket_payload)

    response = client.get("/api/tickets")

    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {"items", "pagination"}
    assert body["pagination"] == {
        "page": 1,
        "per_page": 20,
        "total": 1,
        "pages": 1,
    }
    assert len(body["items"]) == 1


def test_list_empty(db, client):
    body = client.get("/api/tickets").get_json()

    assert body["items"] == []
    assert body["pagination"]["total"] == 0
    assert body["pagination"]["pages"] == 0


def test_list_is_ordered_newest_first(db, client, ticket_payload):
    numbers = [
        _create(client, ticket_payload)["ticket_number"] for _ in range(3)
    ]

    body = client.get("/api/tickets").get_json()

    assert [item["ticket_number"] for item in body["items"]] == numbers[::-1]


def test_list_paginates(db, client, ticket_payload):
    for index in range(3):
        _create(client, ticket_payload, title=f"Ticket {index}")

    body = client.get("/api/tickets?page=2&per_page=2").get_json()

    assert body["pagination"] == {
        "page": 2,
        "per_page": 2,
        "total": 3,
        "pages": 2,
    }
    assert len(body["items"]) == 1


def test_list_rejects_page_zero(client):
    response = client.get("/api/tickets?page=0")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_VALUE"


def test_list_rejects_negative_page(client):
    response = client.get("/api/tickets?page=-1")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_VALUE"


def test_list_rejects_non_integer_page(client):
    response = client.get("/api/tickets?page=abc")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_VALUE"


def test_list_rejects_per_page_above_100(client):
    response = client.get("/api/tickets?per_page=101")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_VALUE"


def test_list_accepts_per_page_100(db, client):
    assert client.get("/api/tickets?per_page=100").status_code == 200


def test_list_filters_by_status(db, client, ticket_payload):
    keep = _create(client, ticket_payload)
    other = _create(client, ticket_payload, title="Second")

    client.patch(
        f"/api/tickets/{other['ticket_number']}", json={"status": "IN_PROGRESS"}
    )

    body = client.get("/api/tickets?status=OPEN").get_json()

    assert [item["ticket_number"] for item in body["items"]] == [
        keep["ticket_number"]
    ]


def test_list_filters_by_priority(db, client, ticket_payload):
    keep = _create(client, ticket_payload, priority="URGENT")
    _create(client, ticket_payload, priority="LOW")

    body = client.get("/api/tickets?priority=URGENT").get_json()

    assert body["pagination"]["total"] == 1
    assert body["items"][0]["ticket_number"] == keep["ticket_number"]


def test_list_filters_by_requester(db, client, seed_data, ticket_payload):
    keep = _create(client, ticket_payload)
    _create(
        client,
        ticket_payload,
        requester_id=str(seed_data["assignee"].id),
    )

    body = client.get(
        f"/api/tickets?requester_id={seed_data['requester'].id}"
    ).get_json()

    assert body["pagination"]["total"] == 1
    assert body["items"][0]["ticket_number"] == keep["ticket_number"]


def test_list_filters_by_assignee(db, client, seed_data, ticket_payload):
    keep = _create(client, ticket_payload, assignee_id=str(seed_data["assignee"].id))

    body = client.get(
        f"/api/tickets?assignee_id={seed_data['assignee'].id}"
    ).get_json()

    assert body["pagination"]["total"] == 1
    assert body["items"][0]["ticket_number"] == keep["ticket_number"]


def test_list_filters_by_category(db, client, seed_data, ticket_payload):
    keep = _create(client, ticket_payload, category_id=str(seed_data["category"].id))

    body = client.get(
        f"/api/tickets?category_id={seed_data['category'].id}"
    ).get_json()

    assert body["pagination"]["total"] == 1
    assert body["items"][0]["ticket_number"] == keep["ticket_number"]


def test_list_rejects_invalid_status_filter(client):
    response = client.get("/api/tickets?status=NOPE")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_VALUE"


def test_list_rejects_invalid_priority_filter(client):
    response = client.get("/api/tickets?priority=critical")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_VALUE"


def test_list_rejects_malformed_uuid_filter(client):
    response = client.get("/api/tickets?assignee_id=not-a-uuid")

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_TYPE"


def test_list_nonexistent_uuid_filter_returns_empty_page(db, client, ticket_payload):
    _create(client, ticket_payload)

    response = client.get(
        "/api/tickets?assignee_id=00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["items"] == []
    assert body["pagination"]["total"] == 0


def test_unknown_route_is_json_404(client):
    response = client.get("/api/nope")

    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"
