"""Shared pytest fixtures."""

import os

import httpx
import pytest

from app import create_app


@pytest.fixture(autouse=True)
def _forbid_outbound_http(monkeypatch):
    """Fail loudly if any test attempts a real outbound HTTP call.

    ``EMBEDDING_PROVIDER=fake`` already keeps embeddings in-process;
    this is the explicit second layer required by the $0 rule: any
    accidental HTTP client use becomes a test failure, never a silent
    call to a real service.
    """

    def _blocked(self, *args, **kwargs):
        raise AssertionError(
            "Outbound HTTP is forbidden in tests; "
            "use FakeEmbeddingProvider instead"
        )

    monkeypatch.setattr(httpx.Client, "request", _blocked)
    monkeypatch.setattr(httpx.AsyncClient, "request", _blocked)


@pytest.fixture()
def app():
    """Create an application configured for testing."""
    application = create_app("testing")
    yield application


@pytest.fixture()
def client(app):
    """Provide a test client for the application."""
    return app.test_client()


@pytest.fixture()
def db(app):
    """Provide the extension with tables created (in-memory SQLite).

    Keeps unit tests independent of Docker/PostgreSQL.
    """
    from app.extensions import db as database

    with app.app_context():
        database.create_all()
        yield database
        database.session.remove()
        database.drop_all()


@pytest.fixture()
def session(db):
    """Provide a database session with the schema in place."""
    return db.session


@pytest.fixture()
def seed_data(db):
    """Insert the reference data the ticket endpoints need.

    Returns the created entities so tests can reference ids directly.
    Kept in tests (not production code) so the suite stays Docker-free.
    """
    from app.models import Category, User

    active_user = User(
        email="requester@supportiq.test", full_name="Requester"
    )
    assignee = User(email="assignee@supportiq.test", full_name="Assignee")
    inactive = User(
        email="inactive@supportiq.test", full_name="Inactive", is_active=False
    )
    category = Category(name="Access", slug="access")
    inactive_category = Category(
        name="Legacy", slug="legacy", is_active=False
    )
    db.session.add_all(
        [
            active_user,
            assignee,
            inactive,
            category,
            inactive_category,
        ]
    )
    db.session.commit()

    return {
        "requester": active_user,
        "assignee": assignee,
        "inactive": inactive,
        "category": category,
        "inactive_category": inactive_category,
    }


@pytest.fixture()
def ticket_payload(seed_data):
    """Minimal valid body for POST /api/tickets."""
    return {
        "title": "VPN does not connect",
        "description": "The VPN client times out after the MFA prompt.",
        "requester_id": str(seed_data["requester"].id),
    }


# --- PostgreSQL / pgvector fixtures (marked tests only) --------------------


def _ensure_pg_test_database(database_url: str) -> None:
    """Create the test database if it does not exist yet (no-op after)."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import ProgrammingError

    base, _, dbname = database_url.rpartition("/")
    admin = create_engine(base + "/postgres", isolation_level="AUTOCOMMIT")
    quoted = '"' + dbname.replace('"', '""') + '"'
    try:
        with admin.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {quoted}"))
    except ProgrammingError:
        pass  # already exists
    finally:
        admin.dispose()


@pytest.fixture(scope="session")
def pg_app():
    """Application pointed at a real PostgreSQL with pgvector.

    Requires ``TEST_DATABASE_URL`` (a SEPARATE database, created on
    first use) and skips with a clear message otherwise, so plain
    ``uv run pytest -q`` stays Docker-free, offline and fast. SQLite
    cannot execute pgvector operators (``<=>``): that is exactly what
    the ``postgres``-marked tests cover.
    """
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "PostgreSQL tests need TEST_DATABASE_URL, e.g. "
            "postgresql+psycopg://supportiq:supportiq@127.0.0.1:15432"
            "/supportiq_test"
        )

    _ensure_pg_test_database(database_url)

    # Patch the exact class create_app consults: app/__init__ binds
    # config_by_name at import time, and test_extensions.py reloads
    # app.config (which recreates the classes) — patching
    # app.config.TestingConfig directly would miss after that reload.
    # Flask-SQLAlchemy builds the engine during init_app, so the URI has
    # to be in place before create_app runs; restore it right after so
    # the normal SQLite suite is unaffected.
    from app import config_by_name

    testing_cls = config_by_name["testing"]
    original_uri = testing_cls.SQLALCHEMY_DATABASE_URI
    testing_cls.SQLALCHEMY_DATABASE_URI = database_url
    try:
        application = create_app("testing")
    finally:
        testing_cls.SQLALCHEMY_DATABASE_URI = original_uri
    yield application


@pytest.fixture()
def pg_db(pg_app):
    """Schema on real PostgreSQL, rebuilt per test for isolation."""
    from sqlalchemy import text

    from app.extensions import db as database

    with pg_app.app_context():
        # The test database is schema-built (create_all), not migrated:
        # create the extension the VECTOR type needs, exactly like
        # migration c94d2e81fa63 does in real environments. Commit it
        # immediately: create_all() runs on a different connection and
        # cannot see an uncommitted CREATE EXTENSION.
        database.session.execute(
            text("CREATE EXTENSION IF NOT EXISTS vector")
        )
        database.session.commit()
        database.drop_all()
        database.create_all()
        # Created by migration a6fa2ebf0568, not part of model metadata.
        database.session.execute(
            text("CREATE SEQUENCE IF NOT EXISTS ticket_number_seq START 1")
        )
        database.session.commit()
        yield database
        database.session.remove()
        database.drop_all()


@pytest.fixture()
def pg_client(pg_app):
    """Test client for the PostgreSQL-backed application."""
    return pg_app.test_client()
