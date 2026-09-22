"""Read model for the future dashboard.

Counts come from SQL aggregates (never rows pulled into Python). The
service's job is normalization: fill statuses/priorities absent from the
``GROUP BY`` with zero and shape the public response.
"""

from app.models import TicketPriority, TicketStatus
from app.repositories.ticket_repository import TicketRepository

_ticket_repo = TicketRepository()


def summary() -> dict:
    """Return the headline numbers of the system."""
    status_counts = _ticket_repo.counts_by_status()
    priority_counts = _ticket_repo.counts_by_priority()

    return {
        "tickets": {
            "total": _ticket_repo.count_total(),
            "open": status_counts.get(TicketStatus.OPEN.value, 0),
            "in_progress": status_counts.get(TicketStatus.IN_PROGRESS.value, 0),
            "resolved": status_counts.get(TicketStatus.RESOLVED.value, 0),
            "closed": status_counts.get(TicketStatus.CLOSED.value, 0),
        },
        "priority": {
            "urgent": priority_counts.get(TicketPriority.URGENT.value, 0),
            "high": priority_counts.get(TicketPriority.HIGH.value, 0),
            "medium": priority_counts.get(TicketPriority.MEDIUM.value, 0),
            "low": priority_counts.get(TicketPriority.LOW.value, 0),
        },
        "unassigned": _ticket_repo.count_unassigned(),
    }
