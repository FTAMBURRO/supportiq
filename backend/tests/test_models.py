"""Unit tests for the domain model.

These run against in-memory SQLite so they stay independent of Docker.
PostgreSQL-only guarantees (JSONB, RESTRICT behaviour) are covered by the
manual verification done when applying the migration, and could later be
promoted to integration tests.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Category,
    Ticket,
    TicketEvent,
    TicketEventType,
    TicketPriority,
    TicketStatus,
    User,
)


@pytest.fixture()
def user(session):
    u = User(email="agent@SUPPORTIQ.io ", full_name="Ada Agent")
    session.add(u)
    session.flush()
    return u


@pytest.fixture()
def category(session):
    c = Category(name="Access", slug="Access", description="Login issues")
    session.add(c)
    session.flush()
    return c


@pytest.fixture()
def ticket(session, user):
    t = Ticket(title="Cannot log in", description="Password rejected", requester=user)
    session.add(t)
    session.flush()
    return t


# --- User -----------------------------------------------------------------


def test_valid_user_is_persisted_with_normalized_email(session):
    u = User(email="  Agent@SupportIQ.IO", full_name="Ada Agent")
    session.add(u)
    session.commit()

    assert u.id is not None
    assert u.email == "agent@supportiq.io"
    assert u.is_active is True
    assert u.created_at is not None
    assert u.updated_at is not None


def test_user_email_must_be_unique(session, user):
    duplicate = User(email=user.email, full_name="Impostor")

    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_user_email_is_required(session):
    session.add(User(full_name="No Email"))

    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


# --- Category -------------------------------------------------------------


def test_valid_category(session):
    c = Category(name="Hardware", slug="hardware", description="Devices")
    session.add(c)
    session.commit()

    assert c.id is not None
    assert c.is_active is True


def test_category_slug_is_normalized_and_validated(session):
    c = Category(name="Access", slug="  Access-Portal  ")
    session.add(c)
    session.flush()

    assert c.slug == "access-portal"


def test_category_slug_must_be_unique(session, category):
    duplicate = Category(name="Other", slug=category.slug.upper())

    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_category_slug_rejects_invalid_values(session):
    with pytest.raises(ValueError):
        Category(name="Bad", slug="not a slug!")


# --- Ticket ---------------------------------------------------------------


def test_valid_ticket_defaults(session, user):
    t = Ticket(title="Cannot log in", description="Password rejected", requester=user)
    session.add(t)
    session.commit()

    assert t.id is not None
    assert t.ticket_number.startswith("SUP-")
    assert t.status == TicketStatus.OPEN
    assert t.priority == TicketPriority.MEDIUM
    assert t.assignee_id is None
    assert t.category_id is None
    assert t.resolved_at is None
    assert t.closed_at is None


def test_ticket_requester_is_required(session):
    session.add(Ticket(title="No requester", description="x"))

    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_ticket_assignee_and_category_are_nullable(session, user):
    t = Ticket(title="Unassigned", description="x", requester=user)
    session.add(t)
    session.flush()

    assert t.assignee_id is None
    assert t.category_id is None


def test_ticket_number_is_unique(session, user):
    a = Ticket(title="A", description="x", requester=user, ticket_number="SUP-000001")
    b = Ticket(title="B", description="x", requester=user, ticket_number="SUP-000001")
    session.add_all([a, b])

    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_ticket_categories_can_be_assigned_later(session, user, category):
    t = Ticket(title="Categorized", description="x", requester=user, category=category)
    session.add(t)
    session.flush()

    assert t.category == category
    assert t in category.tickets


def test_ticket_requester_and_assignee_relationships(session, user):
    other = User(email="tech@supportiq.io", full_name="Tech")
    t = Ticket(title="Assigned", description="x", requester=user, assignee=other)
    session.add(t)
    session.flush()

    assert t.requester == user
    assert t.assignee == other
    assert t in user.requested_tickets
    assert t in other.assigned_tickets


# --- TicketEvent ----------------------------------------------------------


def test_ticket_event_is_persisted_with_ticket(session, ticket):
    e = TicketEvent(ticket=ticket, event_type=TicketEventType.TICKET_CREATED)
    session.add(e)
    session.commit()

    assert e.id is not None
    assert e.ticket == ticket
    assert e in ticket.events
    assert e.created_at is not None


def test_ticket_event_actor_is_nullable(session, ticket):
    e = TicketEvent(ticket=ticket, event_type=TicketEventType.AI_CLASSIFIED)
    session.add(e)
    session.flush()

    assert e.actor_id is None
    assert e.actor is None


def test_ticket_event_data_defaults_to_empty_dict(session, ticket, user):
    e = TicketEvent(
        ticket=ticket,
        actor=user,
        event_type=TicketEventType.STATUS_CHANGED,
        data={"from": "OPEN", "to": "IN_PROGRESS"},
    )
    session.add(e)
    session.flush()

    assert e.data == {"from": "OPEN", "to": "IN_PROGRESS"}
