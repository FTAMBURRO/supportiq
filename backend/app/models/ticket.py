"""Ticket model."""

import itertools
import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    event,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import TimestampMixin
from pgvector.sqlalchemy import Vector

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


class CategorySource(StrEnum):
    """Provenance of the ticket's current category.

    MANUAL is the default and the only source the AI classifier may
    learn from: an AI-assigned category never becomes evidence for the
    next classification, which is what keeps the classifier from
    reinforcing its own mistakes (feedback-loop guard).
    """

    MANUAL = "MANUAL"
    AI = "AI"


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
        CheckConstraint(
            "classification_confidence >= 0 AND classification_confidence <= 1",
            name="ticket_classification_confidence",
        ),
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
    # Who assigned the CURRENT category (see CategorySource). MANUAL is
    # also the feedback-loop guard: only manual categories are eligible
    # evidence for automatic classification.
    category_source: Mapped[CategorySource] = mapped_column(
        _stored_enum(CategorySource, "ticket_category_source"),
        default=CategorySource.MANUAL,
        server_default="MANUAL",
        nullable=False,
    )
    # Heuristic score in (0..1] of the last AI classification — NOT a
    # calibrated probability (see classification_service). NULL whenever
    # a human set the category; the AI_CLASSIFIED event keeps history.
    classification_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Semantic embedding of "title + description" (never category: that
    # would leak the label a future classifier must predict).
    # NULL means "not embedded yet or text changed" — a valid state that
    # `flask embeddings backfill` repairs; vectors are never stale, because
    # PATCHing title/description nulls them in the same transaction.
    # embedding_model records the model that produced the vector so searches
    # never compare vectors from different embedding spaces.
    # 768 must match app.embeddings.DIMENSIONS and the c94d2e81fa63 migration.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(64), nullable=True
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
