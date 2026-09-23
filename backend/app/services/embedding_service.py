"""Synchronous embedding generation and semantic search.

Contract: ticket creation/editing NEVER depends on the provider. The
ticket transaction commits first, the provider call happens with no
write transaction open, and persistence is a second short commit. Any
provider failure degrades to ``embedding = NULL``, which
``flask embeddings backfill`` repairs later.

The valid degraded state is: ticket exists, embedding is NULL. A ticket
is never rolled back because a provider is down.
"""

from __future__ import annotations

from flask import current_app

from app.embeddings import (
    DIMENSIONS,
    EmbeddingError,
    EmbeddingErrorKind,
    get_provider,
)
from app.embeddings.text import build_ticket_embedding_text
from app.errors import ValidationError
from app.extensions import db
from app.models import Ticket
from app.repositories.ticket_repository import TicketRepository

_ticket_repo = TicketRepository()

# Small enough for the demo dataset and the Gemini free tier. There is
# no similarity threshold anywhere: search only ranks and scores, it
# never decides that two tickets are duplicates.
SIMILAR_MAX_LIMIT = 20


def embed_and_persist(ticket: Ticket) -> bool:
    """Embed the ticket's current text and store it. Best-effort.

    Prerequisite: the caller already committed the ticket (the row
    exists). Returns True when the vector was persisted. Any provider
    failure rolls the session back, logs a warning and returns False —
    it never raises, so API flows cannot fail because the provider is
    down. A database failure is not degradable and propagates.
    """
    text = build_ticket_embedding_text(ticket.title, ticket.description)

    try:
        vector = get_provider().embed(text)
    except EmbeddingError as exc:
        db.session.rollback()
        current_app.logger.warning(
            "embedding not stored for %s: %s (%s)",
            ticket.ticket_number,
            exc.message,
            exc.kind,
        )
        return False

    if len(vector) != DIMENSIONS:  # providers validate too; cheap guard
        db.session.rollback()
        current_app.logger.warning(
            "embedding for %s has %s dimensions, expected %s",
            ticket.ticket_number,
            len(vector),
            DIMENSIONS,
        )
        return False

    try:
        ticket.embedding = vector
        ticket.embedding_model = current_app.config["EMBEDDING_MODEL"]
        db.session.commit()
    except Exception:
        db.session.rollback()  # a database failure is not degradable
        raise
    return True


def find_similar_tickets(
    *, title: str, description: str, limit: int = 5
) -> list[tuple[Ticket, float]]:
    """Rank stored tickets by semantic similarity of their embedded text.

    Internal operation: the CLI demo uses it now and the future
    classification flow reuses it later. Returns ``(ticket, similarity)``
    pairs, best match first, computed by pgvector's exact cosine
    distance. No threshold and no duplicate decisions — a ranking only.

    Raises ``ValidationError`` for a limit outside 1..20 and
    ``EmbeddingError`` when the query itself cannot be embedded.
    """
    if not 1 <= limit <= SIMILAR_MAX_LIMIT:
        raise ValidationError(
            f"limit must be between 1 and {SIMILAR_MAX_LIMIT}"
        )

    query_vector = get_provider().embed(
        build_ticket_embedding_text(title, description)
    )
    if len(query_vector) != DIMENSIONS:
        raise EmbeddingError(
            f"provider returned {len(query_vector)} dimensions, "
            f"expected {DIMENSIONS}",
            kind=EmbeddingErrorKind.INVALID,
        )

    return _ticket_repo.find_similar(
        query_vector,
        model=current_app.config["EMBEDDING_MODEL"],
        limit=limit,
    )
