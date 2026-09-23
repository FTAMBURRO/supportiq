"""Domain models.

Importing this package registers every model with SQLAlchemy's metadata,
which is what Alembic autogenerate and ``db.create_all`` need in order to
see them.
"""

from app.models.category import Category
from app.models.ticket import (
    CategorySource,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from app.models.ticket_event import TicketEvent, TicketEventType
from app.models.user import User

__all__ = [
    "Category",
    "CategorySource",
    "Ticket",
    "TicketEvent",
    "TicketEventType",
    "TicketPriority",
    "TicketStatus",
    "User",
]
