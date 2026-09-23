"""SPA serving tests (Fase 6 · Option B): Flask serves ``frontend/dist``.

A tiny dist is built inside a temporary directory, so these tests
never depend on ``npm run build`` — and the rest of the suite never
depends on whether ``frontend/dist`` exists on this machine
(``TestingConfig.SPA_DIST_DIR`` is empty by default).
"""

import pytest

from app import create_app

INDEX_HTML = (
    "<!doctype html><html><head><title>SupportIQ</title></head>"
    '<body><div id="root"></div></body></html>'
)


@pytest.fixture()
def app(tmp_path):
    """Testing application with a simulated frontend/dist."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (dist / "assets" / "app-abc123.js").write_text(
        "window.__supportiq = true;", encoding="utf-8"
    )

    application = create_app("testing")
    application.config["SPA_DIST_DIR"] = str(dist)
    yield application
    # No teardown needed: the fixture directory is tmp_path's.


def test_health_stays_json(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.is_json


def test_unknown_api_route_is_json_404_not_index(client):
    response = client.get("/api/definitely-not-a-route")

    assert response.status_code == 404
    assert response.is_json
    assert "<title>" not in response.get_data(as_text=True)


def test_bare_api_prefix_is_json_404(client):
    response = client.get("/api")

    assert response.status_code == 404
    assert response.is_json


def test_root_serves_the_spa_index(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.content_type.startswith("text/html")
    assert "<title>SupportIQ</title>" in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "path", ["/tickets", "/tickets/new", "/tickets/SUP-000001"]
)
def test_react_deep_links_serve_the_spa_index(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert "<title>SupportIQ</title>" in response.get_data(as_text=True)


def test_existing_asset_is_served_as_a_real_file(client):
    response = client.get("/assets/app-abc123.js")

    assert response.status_code == 200
    assert "window.__supportiq" in response.get_data(as_text=True)
    assert not response.content_type.startswith("text/html")


def test_missing_asset_is_404_not_misleading_html(client):
    response = client.get("/assets/does-not-exist.js")

    assert response.status_code == 404
    assert response.is_json
    assert "<title>" not in response.get_data(as_text=True)


def test_known_api_route_still_answers_json_with_the_spa_active(client, db):
    """The blueprint must win over the catch-all fallback."""
    response = client.get("/api/tickets/SUP-000001")

    assert response.status_code == 404
    assert response.is_json


def test_spa_serving_is_disabled_by_default_in_tests():
    application = create_app("testing")

    assert application.config["SPA_DIST_DIR"] == ""
    response = application.test_client().get("/")
    assert response.status_code == 404
    assert response.is_json
