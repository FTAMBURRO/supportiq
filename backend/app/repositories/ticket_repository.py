"""Persistence for tickets and their events."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Ticket, TicketEvent

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

    def add_event(self, event: TicketEvent) -> None:
        db.session.add(event)
