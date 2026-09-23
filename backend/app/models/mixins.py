"""Shared model mixins."""

import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

# Last timestamp handed out by ``utcnow`` (guarded by ``_UTCNOW_LOCK``).
_last_utcnow: datetime | None = None
_UTCNOW_LOCK = threading.Lock()


def utcnow() -> datetime:
    """Current UTC time as a timezone-aware datetime.

    Strictly increasing within this process: the OS clock advances in
    ticks, so back-to-back writes (a ticket and its audit events) can
    read the *same* microsecond. A repeat would hand event ordering over
    to the ``id`` tie-break, which is a random uuid4 — the audit trail
    could then display, say, PRIORITY_CHANGED before STATUS_CHANGED.
    When the clock does not advance, the next microsecond is issued
    instead of a repeat, so ``ORDER BY created_at ASC, id ASC`` is
    genuinely chronological.

    Timestamps can lead the wall clock by a few microseconds during a
    burst; they never repeat and never go backwards.
    """
    global _last_utcnow

    with _UTCNOW_LOCK:
        now = datetime.now(UTC)
        previous = _last_utcnow
        if previous is not None and now <= previous:
            now = previous + timedelta(microseconds=1)
        _last_utcnow = now
        return now


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
