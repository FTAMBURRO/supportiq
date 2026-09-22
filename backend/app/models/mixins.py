"""Shared model mixins."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    """Current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


class TimestampMixin:
    """``created_at``/``updated_at`` maintained by the application.

    Python-side defaults are used instead of server defaults so the
    behaviour is identical (and testable) on PostgreSQL and on the
    in-memory SQLite test suite.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
