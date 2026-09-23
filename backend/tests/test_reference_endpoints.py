"""GET /api/users and GET /api/categories (read-only reference data)."""

USER_KEYS = {"id", "full_name", "email"}
CATEGORY_KEYS = {"id", "name", "slug"}


def _list(client, path):
    response = client.get(path)
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body, list)  # contract: plain JSON array, no envelope
    return body


# --- GET /api/users ---------------------------------------------------------


def test_users_returns_only_active_users_in_name_order(db, client, seed_data):
    users = _list(client, "/api/users")

    names = [user["full_name"] for user in users]
    assert names == ["Assignee", "Requester"]  # inactive excluded, name order
    assert seed_data["inactive"].full_name not in names


def test_users_shape(db, client, seed_data):
    users = _list(client, "/api/users")

    requester = next(
        user for user in users if user["id"] == str(seed_data["requester"].id)
    )
    assert set(requester) == USER_KEYS
    assert requester["email"] == "requester@supportiq.test"


def test_users_empty_database(db, client):
    assert _list(client, "/api/users") == []


# --- GET /api/categories ----------------------------------------------------


def test_categories_returns_only_active_in_name_order(db, client, seed_data):
    categories = _list(client, "/api/categories")

    names = [category["name"] for category in categories]
    assert names == ["Access"]  # inactive "Legacy" excluded
    assert seed_data["inactive_category"].name not in names


def test_categories_shape(db, client, seed_data):
    categories = _list(client, "/api/categories")

    access = next(
        c for c in categories if c["id"] == str(seed_data["category"].id)
    )
    assert set(access) == CATEGORY_KEYS
    assert access["slug"] == "access"


def test_categories_empty_database(db, client):
    assert _list(client, "/api/categories") == []
