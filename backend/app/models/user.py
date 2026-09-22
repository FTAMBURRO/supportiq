"""User model."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.extensions import db
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.ticket_event import TicketEvent


class User(TimestampMixin, db.Model):
    """A person who interacts with SupportIQ.

    There is no authentication yet: a user exists so tickets and events
    can record who requested, was assigned to, or acted on something.
    Inactive users are deactivated with ``is_active`` rather than deleted.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    requested_tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", foreign_keys="Ticket.requester_id", back_populates="requester"
    )
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", foreign_keys="Ticket.assignee_id", back_populates="assignee"
    )
    events: Mapped[list["TicketEvent"]] = relationship(
        "TicketEvent", back_populates="actor"
    )

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        """Trim and lowercase emails so the unique constraint is reliable."""
        return value.strip().lower()
