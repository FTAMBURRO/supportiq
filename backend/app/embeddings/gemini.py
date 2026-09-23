"""Gemini embeddings over plain REST — free tier, no SDK.

One POST per call via httpx with an explicit timeout. The API key comes
from configuration, travels in the ``x-goog-api-key`` header (never in
the URL) and is never logged nor included in exceptions.

Cost rule: SupportIQ runs on USD 0 — this provider must remain usable
with the Gemini API free tier (small datasets, at most one call per
ticket in normal flows, no retry loops).
"""

from __future__ import annotations

import httpx

from app.embeddings.base import (
    EmbeddingError,
    EmbeddingErrorKind,
    EmbeddingProvider,
)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Symmetric task: stored ticket text and query text share the same
# "Title/Description" shape, and the use case is duplicate/similarity
# detection — exactly what SEMANTIC_SIMILARITY is documented for.
_TASK_TYPE = "SEMANTIC_SIMILARITY"

_TIMEOUT_SECONDS = 10.0


class GeminiProvider(EmbeddingProvider):
    """embed() via ``models/{model}:embedContent``."""

    def __init__(self, *, api_key: str, model: str, dimensions: int) -> None:
        if not api_key:
            raise EmbeddingError(
                "EMBEDDING_API_KEY is not set (get a free key at "
                "aistudio.google.com)",
                kind=EmbeddingErrorKind.AUTH,
            )
        if not model:
            raise EmbeddingError(
                "EMBEDDING_MODEL is not set", kind=EmbeddingErrorKind.CONFIG
            )
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        payload = {
            "content": {"parts": [{"text": text}]},
            "taskType": _TASK_TYPE,
            "output_dimensionality": self._dimensions,
        }
        try:
            response = httpx.post(
                f"{_BASE_URL}/models/{self._model}:embedContent",
                json=payload,
                headers={"x-goog-api-key": self._api_key},
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise EmbeddingError(
                f"embedding request timed out after {_TIMEOUT_SECONDS}s",
                kind=EmbeddingErrorKind.TIMEOUT,
            ) from exc
        except httpx.TransportError as exc:
            raise EmbeddingError(
                f"embedding request failed: {type(exc).__name__}",
                kind=EmbeddingErrorKind.NETWORK,
            ) from exc

        if response.status_code == 429:
            raise EmbeddingError(
                "embedding provider rate limit reached (free tier)",
                kind=EmbeddingErrorKind.RATE_LIMIT,
            )
        if response.status_code in (401, 403):
            raise EmbeddingError(
                "embedding provider rejected EMBEDDING_API_KEY",
                kind=EmbeddingErrorKind.AUTH,
            )
        if response.status_code >= 500:
            raise EmbeddingError(
                f"embedding provider server error (HTTP {response.status_code})",
                kind=EmbeddingErrorKind.NETWORK,
            )
        if response.status_code >= 400:
            raise EmbeddingError(
                f"embedding provider rejected the request "
                f"(HTTP {response.status_code})",
                kind=EmbeddingErrorKind.INVALID,
            )

        values = self._extract_values(response)
        try:
            vector = [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise EmbeddingError(
                "embedding response contains non-numeric values",
                kind=EmbeddingErrorKind.INVALID,
            ) from exc
        if len(vector) != self._dimensions:
            raise EmbeddingError(
                f"embedding has {len(vector)} dimensions, "
                f"expected {self._dimensions}",
                kind=EmbeddingErrorKind.INVALID,
            )
        return vector

    @staticmethod
    def _extract_values(response: httpx.Response) -> list:
        """Parse ``embedding.values`` (embedContent); fall back to the
        batch shape ``embeddings[0].values`` if Google ever answers with it."""
        try:
            body = response.json()
        except ValueError as exc:
            raise EmbeddingError(
                "embedding response is not valid JSON",
                kind=EmbeddingErrorKind.INVALID,
            ) from exc
        try:
            if isinstance(body, dict) and "embedding" in body:
                return body["embedding"]["values"]
            return body["embeddings"][0]["values"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmbeddingError(
                "embedding response has an unexpected shape",
                kind=EmbeddingErrorKind.INVALID,
            ) from exc
