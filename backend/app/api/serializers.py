"""Explicit serializers for API responses.

No schema library: each function documents the exact shape the client
receives, which keeps the contract obvious and the stack small.
"""

from __future__ import annotations

from datetime import datetime

from app.models import Ticket


def _iso(value: datetime | None) -> str | None:
    """ISO-8601 with timezone, or null."""
    return value.isoformat() if value is not None else None


def serialize_ticket(ticket: Ticket) -> dict:
    """Public ticket representation.

    ``ticket_number`` is the public id; ``id`` (internal UUID) and the
    lifecycle timestamps are exposed. Events are not included yet.
    """
    return {
        "id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "requester_id": str(ticket.requester_id),
        "assignee_id": str(ticket.assignee_id) if ticket.assignee_id else None,
        "category_id": str(ticket.category_id) if ticket.category_id else None,
        "created_at": _iso(ticket.created_at),
        "updated_at": _iso(ticket.updated_at),
        "resolved_at": _iso(ticket.resolved_at),
        "closed_at": _iso(ticket.closed_at),
    }


def serialize_ticket_list(
    tickets: list[Ticket], *, page: int, per_page: int, total: int
) -> dict:
    """List envelope: items plus pagination metadata."""
    pages = -(-total // per_page) if per_page else 0  # ceil division
    return {
        "items": [serialize_ticket(ticket) for ticket in tickets],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
        },
    }
