"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

# Load .env before the class attributes below are evaluated: module-level
# ``os.environ.get`` runs at import time, which happens before
# ``create_app`` is ever called.
load_dotenv()


def env_flag(name: str, default: bool) -> bool:
    """Parse an explicit boolean environment flag.

    Only ``true`` and ``false`` (case-insensitive) are accepted: a typo
    must fail loudly at startup instead of silently flipping a feature.
    Deliberately independent of every other variable — notably
    ``EMBEDDING_PROVIDER`` — so "the classifier runs" and "which
    provider embeds" stay separate, explicitly configured concerns.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(
        f"{name} must be 'true' or 'false' (got {raw!r}); "
        "leave it unset to use the default"
    )


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    TESTING = False

    # PostgreSQL connection string, e.g.
    # postgresql+psycopg://supportiq:supportiq@localhost:5432/supportiq
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Embeddings (Fase 3). The API key only ever comes from the
    # environment: never committed, logged, printed or put in tests.
    EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "gemini")
    EMBEDDING_MODEL = os.environ.get(
        "EMBEDDING_MODEL", "gemini-embedding-001"
    )
    EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY")

    # Classification (Fase 3). Deliberately explicit per environment and
    # NEVER inferred from EMBEDDING_PROVIDER: whether the classifier runs
    # and which provider embeds are separate concerns.
    CLASSIFICATION_ENABLED = True
    # Similarity-weighted vote parameters. These are initial
    # HYPOTHESES, validated with `flask classification evaluate` over
    # the fictional dataset; there is deliberately no target accuracy
    # or abstention rate to tune toward — results are published as
    # measured.
    CLASSIFICATION_K = 5
    CLASSIFICATION_MIN_SIMILARITY = 0.55
    CLASSIFICATION_MIN_MARGIN = 0.20
    CLASSIFICATION_MIN_CONFIDENCE = 0.50


class DevelopmentConfig(Config):
    """Configuration for local development."""

    DEBUG = True
    # The dev database currently holds FakeEmbeddingProvider vectors,
    # which carry no semantic meaning: classification stays off until
    # dev embeddings are real. An explicit switch, not a provider sniff:
    # CLASSIFICATION_ENABLED=true in the environment turns it on (for
    # real-provider demos) without implying anything about which
    # provider is configured; unset means false.
    CLASSIFICATION_ENABLED = env_flag("CLASSIFICATION_ENABLED", False)


class TestingConfig(Config):
    """Configuration for the test suite.

    Uses an in-memory SQLite database so the test suite runs without
    Docker or a running PostgreSQL instance.
    """

    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"

    # Guarantee the suite can never reach a real provider: embeddings are
    # generated in-process by FakeEmbeddingProvider. tests/conftest.py adds
    # a second, explicit layer: any outbound HTTP call fails the test.
    EMBEDDING_PROVIDER = "fake"

    # Hash vectors must never drive decisions. Classification tests
    # enable this explicitly and inject controlled neighbours. The env
    # var is deliberately ignored here: a stray CLASSIFICATION_ENABLED
    # in the shell must never flip the suite's default.
    CLASSIFICATION_ENABLED = False


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
