"""Deterministic embedding provider for tests and offline development.

No network, no intelligence — pure reproducibility: the same text always
yields the same 768-dimensional vector, different texts yield different
vectors. Selected with ``EMBEDDING_PROVIDER=fake`` (the testing default),
so the suite never touches a real API.
"""

from __future__ import annotations

import hashlib

from app.embeddings.base import EmbeddingProvider


class FakeEmbeddingProvider(EmbeddingProvider):
    """SHAKE-based pseudo-random vectors, stable across runs and machines."""

    def __init__(self, *, dimensions: int) -> None:
        self._dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        # shake_256 yields an arbitrary-length deterministic stream.
        raw = hashlib.shake_256(text.encode("utf-8")).digest(
            self._dimensions * 4
        )
        return [
            int.from_bytes(raw[i : i + 4], "big") / 2**32
            for i in range(0, len(raw), 4)
        ]
