"""Persistence for tickets and their events."""

from __future__ import annotations  # the method below named ``list`` shadows the builtin

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Category, CategorySource, Ticket, TicketEvent

# Eager-load what the serializer touches so listings never fall into N+1.
_EAGER_LOADS = (
    selectinload(Ticket.requester),
    selectinload(Ticket.assignee),
    selectinload(Ticket.category),
)


class TicketRepository:
    """SQL queries for tickets. Stateless: uses the app-scoped session."""

    def get_by_ticket_number(self, ticket_number: str) -> Ticket | None:
        query = (
            select(Ticket)
            .where(Ticket.ticket_number == ticket_number)
            .options(*_EAGER_LOADS)
        )
        return db.session.execute(query).scalars().first()

    def list(
        self,
        *,
        page: int,
        per_page: int,
        status=None,
        priority=None,
        category_id: uuid.UUID | None = None,
        assignee_id: uuid.UUID | None = None,
        requester_id: uuid.UUID | None = None,
    ) -> tuple[list[Ticket], int]:
        """Return a page of tickets (newest first) and the total count.

        Filter values arrive already validated by the service; this class
        does not interpret them.
        """
        clauses = []
        if status is not None:
            clauses.append(Ticket.status == status)
        if priority is not None:
            clauses.append(Ticket.priority == priority)
        if category_id is not None:
            clauses.append(Ticket.category_id == category_id)
        if assignee_id is not None:
            clauses.append(Ticket.assignee_id == assignee_id)
        if requester_id is not None:
            clauses.append(Ticket.requester_id == requester_id)

        count_query = select(func.count()).select_from(Ticket)
        list_query = (
            select(Ticket)
            .options(*_EAGER_LOADS)
            # Secondary key keeps pagination stable when timestamps tie.
            .order_by(Ticket.created_at.desc(), Ticket.ticket_number.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        if clauses:
            count_query = count_query.where(*clauses)
            list_query = list_query.where(*clauses)

        total = db.session.execute(count_query).scalar_one()
        items = list(db.session.execute(list_query).scalars().all())
        return items, total

    def add(self, ticket: Ticket) -> None:
        db.session.add(ticket)

    def list_by_titles(self, titles: list[str]) -> list[Ticket]:
        """Tickets whose title exactly matches one of ``titles``.

        Used by the evaluation flow to locate the fixed demo dataset
        without needing a schema marker column; ids come back in title
        order for reproducibility.
        """
        if not titles:
            return []
        query = (
            select(Ticket)
            .where(Ticket.title.in_(titles))
            .options(*_EAGER_LOADS)
            .order_by(Ticket.title.asc())
        )
        return list(db.session.execute(query).scalars().all())

    def add_event(self, event: TicketEvent) -> None:
        db.session.add(event)

    def list_events(self, ticket_id: uuid.UUID) -> list[TicketEvent]:
        """Return the ticket's timeline, oldest first.

        ``created_at`` ties (events created in the same PATCH share a
        timestamp) are broken deterministically by ``id``; there is no
        sequence column and the schema stays untouched.
        """
        query = (
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .options(selectinload(TicketEvent.actor))  # no N+1 on actor
            .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
        )
        return list(db.session.execute(query).scalars().all())

    # --- dashboard aggregates (SQL, never rows-to-Python) -------------------

    def counts_by_status(self) -> dict:
        """{status: count} for statuses present in the table."""
        rows = db.session.execute(
            select(Ticket.status, func.count()).group_by(Ticket.status)
        ).all()
        return {status.value: count for status, count in rows}

    def counts_by_priority(self) -> dict:
        """{priority: count} for priorities present in the table."""
        rows = db.session.execute(
            select(Ticket.priority, func.count()).group_by(Ticket.priority)
        ).all()
        return {priority.value: count for priority, count in rows}

    def count_unassigned(self) -> int:
        """Tickets with no assignee, regardless of status."""
        query = select(func.count()).select_from(Ticket).where(
            Ticket.assignee_id.is_(None)
        )
        return db.session.execute(query).scalar_one()

    def count_total(self) -> int:
        """Own COUNT so the total/status-sum invariant is really testable."""
        query = select(func.count()).select_from(Ticket)
        return db.session.execute(query).scalar_one()

    # --- semantic search / embeddings (pgvector) ----------------------------

    @staticmethod
    def _similarity_query(embedding: list[float], *, model: str):
        """Base cosine select shared by search AND classification.

        One implementation of the vector math: same ``<=>`` operator,
        same ``1 - distance`` similarity, same model guard (vectors from
        different models live in different spaces and must never be
        compared), same deterministic ``id`` tie-break. Callers only
        add their own WHERE clauses, joins and LIMIT.
        """
        distance = Ticket.embedding.cosine_distance(embedding)
        return (
            select(Ticket, (1 - distance).label("similarity"))
            .where(
                Ticket.embedding.isnot(None),
                Ticket.embedding_model == model,
            )
            .order_by(distance.asc(), Ticket.id.asc())
        )

    def find_similar(
        self, embedding: list[float], *, model: str, limit: int = 5
    ) -> list[tuple[Ticket, float]]:
        """Exact cosine nearest neighbours (pgvector), best match first.

        Deliberately no ANN index (HNSW/IVFFlat): exact search has
        perfect recall and is fast enough until the table grows large;
        the ORDER BY uses the raw ``<=>`` operator so an index can be
        added later without touching this query, and similarity is
        computed only in the SELECT list. Only tickets embedded by the
        currently configured model are candidates. Ties break on ``id``
        for a deterministic ranking.
        """
        query = self._similarity_query(embedding, model=model).limit(limit)
        return [
            (ticket, float(similarity))
            for ticket, similarity in db.session.execute(query).all()
        ]

    def find_classification_neighbors(
        self,
        *,
        exclude_ticket_id: uuid.UUID,
        embedding: list[float],
        model: str,
        k: int,
    ) -> list[tuple[Ticket, float]]:
        """Evidence for automatic classification: same cosine core,
        narrower WHERE.

        A neighbour only counts as evidence when it carries a category a
        human set (``category_source = MANUAL``) that is still active:
        AI-assigned tickets are excluded so the classifier never learns
        from its own past output (feedback-loop guard). Status and
        assignee deliberately do NOT filter — a closed ticket's
        category is as valid as an open one. The queried ticket itself
        is always excluded. Best match first, at most ``k`` rows.
        """
        query = (
            self._similarity_query(embedding, model=model)
            .join(Ticket.category)
            .where(
                Ticket.id != exclude_ticket_id,
                Ticket.category_id.isnot(None),
                Category.is_active.is_(True),
                Ticket.category_source == CategorySource.MANUAL,
            )
            .options(selectinload(Ticket.category))  # evidence needs slugs
            .limit(k)
        )
        return [
            (ticket, float(similarity))
            for ticket, similarity in db.session.execute(query).all()
        ]

    def list_pending_embeddings(
        self, *, limit: int | None = None
    ) -> list[Ticket]:
        """Tickets with no embedding yet, oldest first (backfill queue)."""
        query = (
            select(Ticket)
            .where(Ticket.embedding.is_(None))
            .order_by(Ticket.created_at.asc(), Ticket.id.asc())
        )
        if limit is not None:
            query = query.limit(limit)
        return list(db.session.execute(query).scalars().all())

    def count_pending_embeddings(self) -> int:
        """How many tickets still lack an embedding."""
        query = (
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.embedding.is_(None))
        )
        return db.session.execute(query).scalar_one()
