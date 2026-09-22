"""Tests for extension and configuration wiring.

These tests deliberately avoid opening a database connection so the suite
runs without Docker/PostgreSQL.
"""

import importlib

from flask_sqlalchemy import SQLAlchemy

from app.extensions import db, migrate


def test_app_uses_sqlalchemy_extension(app):
    assert app.extensions["sqlalchemy"] is db


def test_app_uses_migrate_extension(app):
    assert "migrate" in app.extensions


def test_testing_config_uses_in_memory_sqlite(app):
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"
    assert app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] is False


def test_development_config_reads_database_url(monkeypatch):
    import app.config as config_module

    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/db"
    )
    # Class attributes read the environment at import time, so reload to
    # observe the value set above.
    importlib.reload(config_module)

    assert (
        config_module.DevelopmentConfig.SQLALCHEMY_DATABASE_URI
        == "postgresql+psycopg://user:pass@localhost:5432/db"
    )


def test_db_extension_is_declared_without_app():
    assert isinstance(db, SQLAlchemy)
