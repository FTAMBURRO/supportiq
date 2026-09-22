"""Application configuration loaded from environment variables."""

import os


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    TESTING = False


class DevelopmentConfig(Config):
    """Configuration for local development."""

    DEBUG = True


class TestingConfig(Config):
    """Configuration for the test suite."""

    TESTING = True
    SECRET_KEY = "test-secret-key"


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
