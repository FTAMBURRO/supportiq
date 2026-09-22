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
