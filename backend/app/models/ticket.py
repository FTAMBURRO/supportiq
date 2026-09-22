"""Ticket model."""

import itertools
import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, event, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.ticket_event import TicketEvent
    from app.models.user import User


class TicketStatus(StrEnum):
    """Lifecycle of a ticket."""

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(StrEnum):
    """Service priority of a ticket."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


def _stored_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """Enum stored as VARCHAR + CHECK (portable, readable, PG-compatible)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
    )


# Fallback counter for the in-memory SQLite test suite, which has no sequences.
_sqlite_ticket_counter = itertools.count(1)


class Ticket(TimestampMixin, db.Model):
    """A support ticket: the central entity of SupportIQ.

    ``ticket_number`` is a human-readable id (``SUP-000001``) generated on
    insert; ``id`` stays the internal UUID primary key. ``category_id`` is
    intentionally nullable because a later phase will classify tickets
    with AI.
    """

    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    ticket_number: Mapped[str] = mapped_column(
        String(16), unique=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[TicketStatus] = mapped_column(
        _stored_enum(TicketStatus, "ticket_status"),
        default=TicketStatus.OPEN,
        nullable=False,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        _stored_enum(TicketPriority, "ticket_priority"),
        default=TicketPriority.MEDIUM,
        nullable=False,
    )

    requester_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    requester: Mapped["User"] = relationship(
        "User", foreign_keys=[requester_id], back_populates="requested_tickets"
    )
    assignee: Mapped["User | None"] = relationship(
        "User", foreign_keys=[assignee_id], back_populates="assigned_tickets"
    )
    category: Mapped["Category | None"] = relationship(
        "Category", back_populates="tickets"
    )
    events: Mapped[list["TicketEvent"]] = relationship(
        "TicketEvent",
        back_populates="ticket",
        order_by="TicketEvent.created_at",
        cascade="save-update, merge",
    )


@event.listens_for(Ticket, "before_insert")
def _assign_ticket_number(mapper, connection, target: Ticket) -> None:
    """Give new tickets a human id such as ``SUP-000001``.

    PostgreSQL uses the ``ticket_number_seq`` sequence: nextval is atomic
    and collision-free under concurrency. The counter branch only serves
    the SQLite test suite.
    """
    if target.ticket_number is not None:
        return
    if connection.dialect.name == "postgresql":
        number = connection.execute(
            text("select nextval('ticket_number_seq')")
        ).scalar_one()
    else:
        number = next(_sqlite_ticket_counter)
    target.ticket_number = f"SUP-{int(number):06d}"
