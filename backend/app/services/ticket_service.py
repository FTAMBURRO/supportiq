"""Business rules for tickets.

Every write operation validates first, mutates second, and commits
exactly once: the service owns the transaction boundary, the repository
owns the session primitives.
"""

import uuid
from typing import Any

from app.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.extensions import db
from app.models import (
    Category,
    Ticket,
    TicketEvent,
    TicketEventType,
    TicketPriority,
    TicketStatus,
    User,
)
from app.models.mixins import utcnow
from app.repositories.category_repository import CategoryRepository
from app.repositories.ticket_repository import TicketRepository
from app.repositories.user_repository import UserRepository

_ticket_repo = TicketRepository()
_user_repo = UserRepository()
_category_repo = CategoryRepository()

# Sentinel telling "field not present" apart from "field present and null".
_MISSING = object()

_CREATE_FIELDS = frozenset(
    {
        "title",
        "description",
        "requester_id",
        "priority",
        "assignee_id",
        "category_id",
    }
)
_UPDATE_FIELDS = frozenset(
    {
        "title",
        "description",
        "status",
        "priority",
        "assignee_id",
        "category_id",
    }
)

_TITLE_MAX_LENGTH = 200

_ALLOWED_STATUS_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
    TicketStatus.IN_PROGRESS: {TicketStatus.OPEN, TicketStatus.RESOLVED},
    TicketStatus.RESOLVED: {TicketStatus.IN_PROGRESS, TicketStatus.CLOSED},
    TicketStatus.CLOSED: set(),
}


# --- validation helpers ----------------------------------------------------


def _ensure_known_fields(data: dict[str, Any], allowed: frozenset[str]) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise BadRequestError(
            f"Unknown or read-only fields: {', '.join(sorted(unknown))}",
            code="UNKNOWN_FIELD",
        )


def _parse_uuid(value: Any, field: str) -> uuid.UUID:
    if not isinstance(value, str):
        raise BadRequestError(f"{field} must be a UUID string", code="INVALID_TYPE")
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise BadRequestError(
            f"{field} must be a valid UUID", code="INVALID_TYPE"
        ) from exc


def _parse_enum(enum_cls, value: Any, field: str):
    if not isinstance(value, str):
        raise BadRequestError(f"{field} must be a string", code="INVALID_TYPE")
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in enum_cls)
        raise BadRequestError(
            f"{field} must be one of: {allowed}", code="INVALID_VALUE"
        ) from exc


def _validated_text(value: Any, field: str, max_length: int | None = None) -> str:
    if not isinstance(value, str):
        raise BadRequestError(f"{field} must be a string", code="INVALID_TYPE")
    text = value.strip()
    if not text:
        raise ValidationError(f"{field} must not be empty")
    if max_length is not None and len(text) > max_length:
        raise ValidationError(f"{field} must be at most {max_length} characters")
    return text


def _required_text(data: dict[str, Any], field: str,
                   max_length: int | None = None) -> str:
    if field not in data:
        raise ValidationError(f"{field} is required")
    return _validated_text(data[field], field, max_length)


def _resolve_user(user_id: uuid.UUID, field: str) -> User:
    user = _user_repo.get(user_id)
    if user is None:
        raise ValidationError(f"{field}: user does not exist")
    if not user.is_active:
        raise ValidationError(f"{field}: user is inactive")
    return user


def _resolve_category(category_id: uuid.UUID, field: str) -> Category:
    category = _category_repo.get(category_id)
    if category is None:
        raise ValidationError(f"{field}: category does not exist")
    if not category.is_active:
        raise ValidationError(f"{field}: category is inactive")
    return category


def _ensure_transition(current: TicketStatus, new: TicketStatus) -> None:
    if new not in _ALLOWED_STATUS_TRANSITIONS[current]:
        raise ConflictError(
            f"Cannot transition ticket from {current.value} to {new.value}",
            code="INVALID_STATUS_TRANSITION",
        )


def _persist(ticket: Ticket, events: list[TicketEvent]) -> None:
    """Commit ticket + events in a single transaction.

    The service owns the transaction boundary: the repository only
    queries and stages entities.
    """
    try:
        _ticket_repo.add(ticket)
        for event in events:
            _ticket_repo.add_event(event)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# --- operations ------------------------------------------------------------


def create(data: dict[str, Any]) -> Ticket:
    """Create a ticket plus its TICKET_CREATED event, atomically."""
    _ensure_known_fields(data, _CREATE_FIELDS)

    title = _required_text(data, "title", max_length=_TITLE_MAX_LENGTH)
    description = _required_text(data, "description")

    if data.get("requester_id") is None:
        raise ValidationError("requester_id is required")
    requester = _resolve_user(
        _parse_uuid(data["requester_id"], "requester_id"), "requester_id"
    )

    priority = TicketPriority.MEDIUM
    if data.get("priority") is not None:
        priority = _parse_enum(TicketPriority, data["priority"], "priority")

    assignee = None
    if data.get("assignee_id") is not None:
        assignee = _resolve_user(
            _parse_uuid(data["assignee_id"], "assignee_id"), "assignee_id"
        )

    category = None
    if data.get("category_id") is not None:
        category = _resolve_category(
            _parse_uuid(data["category_id"], "category_id"), "category_id"
        )

    ticket = Ticket(
        title=title,
        description=description,
        priority=priority,
        requester=requester,
        assignee=assignee,
        category=category,
    )
    event = TicketEvent(
        ticket=ticket,
        actor_id=requester.id,
        event_type=TicketEventType.TICKET_CREATED,
        data={},
    )

    _persist(ticket, [event])
    return ticket


def get(ticket_number: str) -> Ticket:
    """Return a ticket or raise a 404."""
    ticket = _ticket_repo.get_by_ticket_number(ticket_number)
    if ticket is None:
        raise NotFoundError(
            f"Ticket {ticket_number} not found", code="TICKET_NOT_FOUND"
        )
    return ticket


def get_events(ticket_number: str) -> list[TicketEvent]:
    """Full audit trail of a ticket, oldest event first.

    No pagination: a normal ticket has a moderate amount of events.
    """
    ticket = get(ticket_number)  # reuses the 404 above
    return _ticket_repo.list_events(ticket.id)


def list_tickets(
    *, page: int, per_page: int, filters: dict[str, str | None]
) -> tuple[list[Ticket], int]:
    """Validate list filters and return a page of tickets plus the total."""
    kwargs: dict[str, Any] = {"page": page, "per_page": per_page}

    if filters.get("status"):
        kwargs["status"] = _parse_enum(TicketStatus, filters["status"], "status")
    if filters.get("priority"):
        kwargs["priority"] = _parse_enum(
            TicketPriority, filters["priority"], "priority"
        )
    for name in ("category_id", "assignee_id", "requester_id"):
        raw = filters.get(name)
        if raw:
            # A valid-but-nonexistent id simply yields an empty page.
            kwargs[name] = _parse_uuid(raw, name)

    return _ticket_repo.list(**kwargs)


def update(ticket_number: str, data: dict[str, Any]) -> Ticket:
    """Apply a PATCH: validate everything first, mutate, then commit once."""
    ticket = get(ticket_number)
    _ensure_known_fields(data, _UPDATE_FIELDS)

    # No authentication yet: the actor comes from the authenticated user,
    # never from the payload, so events record NULL until auth exists.
    actor_id: uuid.UUID | None = None

    # --- validation phase: nothing has been mutated yet ---
    new_title = (
        _MISSING if "title" not in data
        else _validated_text(data["title"], "title", _TITLE_MAX_LENGTH)
    )
    new_description = (
        _MISSING if "description" not in data
        else _validated_text(data["description"], "description")
    )

    new_status = None
    if "status" in data:
        new_status = _parse_enum(TicketStatus, data["status"], "status")
        if new_status != ticket.status:
            _ensure_transition(ticket.status, new_status)

    new_priority = None
    if "priority" in data:
        new_priority = _parse_enum(TicketPriority, data["priority"], "priority")

    new_assignee: User | None | object = _MISSING
    if "assignee_id" in data:
        raw = data["assignee_id"]
        new_assignee = (
            None if raw is None
            else _resolve_user(_parse_uuid(raw, "assignee_id"), "assignee_id")
        )

    new_category: Category | None | object = _MISSING
    if "category_id" in data:
        raw = data["category_id"]
        new_category = (
            None if raw is None
            else _resolve_category(_parse_uuid(raw, "category_id"), "category_id")
        )

    # --- apply phase ---
    events: list[TicketEvent] = []

    if new_title is not _MISSING:
        ticket.title = new_title
    if new_description is not _MISSING:
        ticket.description = new_description

    if new_status is not None and new_status != ticket.status:
        old_status = ticket.status
        ticket.status = new_status
        if new_status == TicketStatus.RESOLVED:
            ticket.resolved_at = utcnow()
        elif old_status == TicketStatus.RESOLVED and new_status == TicketStatus.IN_PROGRESS:
            ticket.resolved_at = None
        if new_status == TicketStatus.CLOSED:
            ticket.closed_at = utcnow()
        events.append(
            TicketEvent(
                ticket=ticket,
                actor_id=actor_id,
                event_type=TicketEventType.STATUS_CHANGED,
                data={"from": old_status.value, "to": new_status.value},
            )
        )

    if new_priority is not None and new_priority != ticket.priority:
        old_priority = ticket.priority
        ticket.priority = new_priority
        events.append(
            TicketEvent(
                ticket=ticket,
                actor_id=actor_id,
                event_type=TicketEventType.PRIORITY_CHANGED,
                data={"from": old_priority.value, "to": new_priority.value},
            )
        )

    if new_assignee is not _MISSING:
        new_assignee_id = new_assignee.id if new_assignee is not None else None
        if new_assignee_id != ticket.assignee_id:
            old_assignee_id = ticket.assignee_id
            ticket.assignee = new_assignee
            events.append(
                TicketEvent(
                    ticket=ticket,
                    actor_id=actor_id,
                    event_type=TicketEventType.ASSIGNED,
                    data={
                        "from": str(old_assignee_id) if old_assignee_id else None,
                        "to": str(new_assignee_id) if new_assignee_id else None,
                    },
                )
            )

    if new_category is not _MISSING:
        new_category_id = new_category.id if new_category is not None else None
        if new_category_id != ticket.category_id:
            old_category_id = ticket.category_id
            ticket.category = new_category
            events.append(
                TicketEvent(
                    ticket=ticket,
                    actor_id=actor_id,
                    event_type=TicketEventType.CATEGORY_CHANGED,
                    data={
                        "from": str(old_category_id) if old_category_id else None,
                        "to": str(new_category_id) if new_category_id else None,
                    },
                )
            )

    _persist(ticket, events)
    return ticket
