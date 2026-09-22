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
