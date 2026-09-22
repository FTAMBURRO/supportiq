"""GET /api/dashboard/summary."""

EMPTY_SUMMARY = {
    "tickets": {"total": 0, "open": 0, "in_progress": 0, "resolved": 0, "closed": 0},
    "priority": {"urgent": 0, "high": 0, "medium": 0, "low": 0},
    "unassigned": 0,
}


def _create(client, payload, **overrides):
    response = client.post("/api/tickets", json=dict(payload, **overrides))
    assert response.status_code == 201
    return response.get_json()


def _patch_status(client, ticket_number, status):
    response = client.patch(
        f"/api/tickets/{ticket_number}", json={"status": status}
    )
    assert response.status_code == 200


def _summary(client):
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    return response.get_json()


def test_empty_database_returns_all_zeros(db, client):
    body = _summary(client)

    assert body == EMPTY_SUMMARY  # exact keys and zero-filled structure


def test_zero_fill_when_only_some_statuses_exist(db, client, ticket_payload):
    _create(client, ticket_payload)  # a single OPEN ticket

    tickets = _summary(client)["tickets"]

    assert tickets["open"] == 1
    assert tickets["closed"] == 0
    assert tickets["in_progress"] == 0


def test_counts_every_status_and_holds_the_invariant(
    db, client, seed_data, ticket_payload
):
    assignee = str(seed_data["assignee"].id)

    open_ticket = _create(client, ticket_payload)  # OPEN, MEDIUM, unassigned
    in_progress = _create(client, ticket_payload, assignee_id=assignee)
    _patch_status(client, in_progress["ticket_number"], "IN_PROGRESS")
    resolved = _create(client, ticket_payload, assignee_id=assignee)
    _patch_status(client, resolved["ticket_number"], "IN_PROGRESS")
    _patch_status(client, resolved["ticket_number"], "RESOLVED")
    closed = _create(client, ticket_payload, assignee_id=assignee)
    _patch_status(client, closed["ticket_number"], "IN_PROGRESS")
    _patch_status(client, closed["ticket_number"], "RESOLVED")
    _patch_status(client, closed["ticket_number"], "CLOSED")

    tickets = _summary(client)["tickets"]

    assert tickets == {
        "total": 4,
        "open": 1,
        "in_progress": 1,
        "resolved": 1,
        "closed": 1,
    }

    # The invariant: every ticket has exactly one status.
    assert tickets["total"] == (
        tickets["open"] + tickets["in_progress"]
        + tickets["resolved"] + tickets["closed"]
    )
    assert open_ticket["status"] == "OPEN"


def test_counts_priorities_regardless_of_status_and_unassigned(
    db, client, seed_data, ticket_payload
):
    assignee = str(seed_data["assignee"].id)

    _create(client, ticket_payload, priority="URGENT")  # unassigned
    _create(client, ticket_payload, priority="HIGH", assignee_id=assignee)
    resolved = _create(client, ticket_payload, priority="MEDIUM")  # unassigned
    _patch_status(client, resolved["ticket_number"], "RESOLVED")
    _create(client, ticket_payload, priority="LOW", assignee_id=assignee)

    body = _summary(client)

    assert body["priority"] == {"urgent": 1, "high": 1, "medium": 1, "low": 1}
    # Unassigned ignores status: the OPEN and the RESOLVED tickets have no
    # assignee, the other two do.
    assert body["unassigned"] == 2
    assert body["tickets"]["total"] == 4


def test_summary_matches_top_level_keys(db, client):
    assert set(_summary(client)) == {"tickets", "priority", "unassigned"}
    assert set(EMPTY_SUMMARY["tickets"]) == {
        "total", "open", "in_progress", "resolved", "closed",
    }
    assert set(EMPTY_SUMMARY["priority"]) == {"urgent", "high", "medium", "low"}
