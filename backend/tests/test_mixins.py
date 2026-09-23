"""utcnow: strictly increasing timestamps for a chronological audit trail.

Regression guard for a real defect: the OS clock ticks coarsely enough
that back-to-back writes shared ``created_at`` values, and the ``id``
tie-break (random uuid4) then produced non-chronological event orders
(~28% in a 300-run reproduction). Approved fix: a monotonic ``utcnow``.
"""

from datetime import datetime

from app.models import mixins


def test_utcnow_advances_even_when_the_clock_does_not(monkeypatch):
    """A frozen/coarse clock must yield distinct, increasing instants."""

    class _FrozenClock:
        @classmethod
        def now(cls, tz=None):
            return datetime(2020, 1, 1, 0, 0, tzinfo=tz)  # never advances

    monkeypatch.setattr(mixins, "datetime", _FrozenClock)
    monkeypatch.setattr(mixins, "_last_utcnow", None)  # isolated state

    first = mixins.utcnow()
    second = mixins.utcnow()
    third = mixins.utcnow()

    assert first < second < third
    assert (second - first).total_seconds() == 1e-6  # +1µs per repeat
    assert (third - second).total_seconds() == 1e-6
    assert first.tzinfo is not None  # stays timezone-aware
