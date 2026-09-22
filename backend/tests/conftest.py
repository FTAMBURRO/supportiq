"""Shared pytest fixtures."""

import pytest

from app import create_app


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
