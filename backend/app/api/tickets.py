"""Ticket endpoints.

Thin routes: parse the request, call the service, serialize the result.
All validation and business rules live in ``app.services.ticket_service``.
"""

from flask import jsonify, request

from app.api import api
from app.api.serializers import (
    serialize_event_list,
    serialize_ticket,
    serialize_ticket_list,
)
from app.errors import BadRequestError
from app.services import ticket_service

_DEFAULT_PER_PAGE = 20
_MAX_PER_PAGE = 100
_FILTERS = ("status", "priority", "category_id", "assignee_id", "requester_id")


def _json_body() -> dict:
    """Read the request body as a JSON object or raise a 400."""
    if not request.is_json:
        raise BadRequestError("Content-Type must be application/json",
                              code="MALFORMED_JSON")
    try:
        data = request.get_json()
    except Exception as exc:  # malformed JSON payload
        raise BadRequestError("Request body is not valid JSON",
                              code="MALFORMED_JSON") from exc
    if not isinstance(data, dict):
        raise BadRequestError("JSON body must be an object",
                              code="MALFORMED_JSON")
    return data


def _int_param(name: str, default: int, *, minimum: int,
               maximum: int | None = None) -> int:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise BadRequestError(f"{name} must be an integer",
                              code="INVALID_VALUE") from exc
    if value < minimum:
        raise BadRequestError(f"{name} must be >= {minimum}",
                              code="INVALID_VALUE")
    if maximum is not None and value > maximum:
        raise BadRequestError(f"{name} must be <= {maximum}",
                              code="INVALID_VALUE")
    return value


@api.post("/tickets")
def create_ticket():
    """Create a ticket. Returns 201 with the representation."""
    ticket = ticket_service.create(_json_body())
    return jsonify(serialize_ticket(ticket)), 201


@api.get("/tickets")
def list_tickets():
    """List tickets with pagination and filters."""
    page = _int_param("page", 1, minimum=1)
    per_page = _int_param("per_page", _DEFAULT_PER_PAGE, minimum=1,
                          maximum=_MAX_PER_PAGE)
    filters = {name: request.args.get(name) for name in _FILTERS}
    items, total = ticket_service.list_tickets(
        page=page, per_page=per_page, filters=filters
    )
    return jsonify(
        serialize_ticket_list(items, page=page, per_page=per_page, total=total)
    ), 200


@api.get("/tickets/<ticket_number>")
def get_ticket(ticket_number: str):
    """Return one ticket by its public number (SUP-000001)."""
    return jsonify(serialize_ticket(ticket_service.get(ticket_number))), 200


@api.get("/tickets/<ticket_number>/events")
def get_ticket_events(ticket_number: str):
    """Return the ticket's full audit trail, oldest event first.

    Not paginated: a normal ticket holds a moderate amount of events.
    """
    events = ticket_service.get_events(ticket_number)
    return jsonify(serialize_event_list(events)), 200


@api.patch("/tickets/<ticket_number>")
def update_ticket(ticket_number: str):
    """Apply a partial update. Empty body is a 200 no-op."""
    ticket = ticket_service.update(ticket_number, _json_body())
    return jsonify(serialize_ticket(ticket)), 200
