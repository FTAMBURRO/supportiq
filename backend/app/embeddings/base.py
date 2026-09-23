"""Minimal embedding provider contract.

One method on purpose: turning text into a vector is the whole job.
Providers are pluggable via configuration (``EMBEDDING_PROVIDER``);
SupportIQ is not coupled to any vendor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum


class EmbeddingErrorKind(StrEnum):
    """Machine-readable reason an embedding call failed."""

    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    INVALID = "INVALID"  # malformed response or wrong dimensions
    CONFIG = "CONFIG"  # provider name/key misconfigured


class EmbeddingError(Exception):
    """External embedding failure.

    One class with a machine-readable ``kind`` — no exception hierarchy.
    Never carries the API key (providers use headers, not URLs, and build
    messages themselves).
    """

    def __init__(self, message: str, *, kind: EmbeddingErrorKind) -> None:
        super().__init__(message)
        self.message = message
        self.kind = kind


class EmbeddingProvider(ABC):
    """Turns text into a vector."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return exactly ``DIMENSIONS`` floats, or raise ``EmbeddingError``."""
