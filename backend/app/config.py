"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

# Load .env before the class attributes below are evaluated: module-level
# ``os.environ.get`` runs at import time, which happens before
# ``create_app`` is ever called.
load_dotenv()


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    TESTING = False

    # PostgreSQL connection string, e.g.
    # postgresql+psycopg://supportiq:supportiq@localhost:5432/supportiq
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    """Configuration for local development."""

    DEBUG = True


class TestingConfig(Config):
    """Configuration for the test suite.

    Uses an in-memory SQLite database so the test suite runs without
    Docker or a running PostgreSQL instance.
    """

    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"


class ProductionConfig(Config):
    """Configuration for production deployments."""

    DEBUG = False

    @staticmethod
    def init_app(app):
        """Fail fast when a required secret is missing in production."""
        if not app.config["SECRET_KEY"]:
            raise RuntimeError(
                "SECRET_KEY must be set in the environment for production."
            )


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
