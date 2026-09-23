"""Semantic embeddings: provider selection and shared constants."""

from app.embeddings.base import (
    EmbeddingError,
    EmbeddingErrorKind,
    EmbeddingProvider,
)

__all__ = [
    "DIMENSIONS",
    "EmbeddingError",
    "EmbeddingErrorKind",
    "EmbeddingProvider",
    "get_provider",
]

# Must match Ticket.embedding (vector(768)) and migration c94d2e81fa63.
# Deliberately NOT an environment variable: a value that has to agree
# with the database schema must have a single source of truth in code.
DIMENSIONS = 768


def get_provider() -> EmbeddingProvider:
    """Return the provider named by ``EMBEDDING_PROVIDER``.

    Requires an application context (configuration lives in the app).
    Fails fast with a clear ``EmbeddingError`` for unknown names or a
    missing key. Providers are stateless, so no caching is involved.
    """
    from flask import current_app

    from app.embeddings.fake import FakeEmbeddingProvider
    from app.embeddings.gemini import GeminiProvider

    name = (current_app.config.get("EMBEDDING_PROVIDER") or "").lower()

    if name == "fake":
        return FakeEmbeddingProvider(dimensions=DIMENSIONS)
    if name == "gemini":
        return GeminiProvider(
            api_key=current_app.config.get("EMBEDDING_API_KEY") or "",
            model=current_app.config.get("EMBEDDING_MODEL") or "",
            dimensions=DIMENSIONS,
        )
    raise EmbeddingError(
        f"unknown EMBEDDING_PROVIDER {name!r}: expected 'gemini' or 'fake'",
        kind=EmbeddingErrorKind.CONFIG,
    )
