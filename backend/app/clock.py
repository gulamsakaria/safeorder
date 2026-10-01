"""Simulated clock. All business logic reads time from here, never from datetime.now().

The demo panel fast-forwards the clock to pass the 72-hour hold period.
Datetimes are timezone-aware UTC.
"""

import threading
from datetime import UTC, datetime, timedelta


def real_utc_now() -> datetime:
    return datetime.now(UTC)


def to_iso(value: datetime) -> str:
    """ISO 8601 UTC string for API output, for example 2026-10-02T10:00:00Z."""
    return value.astimezone(UTC).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


class SimClock:
    def __init__(self, start: datetime | None = None) -> None:
        """``start`` freezes the origin for deterministic runs. None means real time."""
        self._start = start
        self._offset = timedelta(0)
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            base = self._start if self._start is not None else real_utc_now()
            return base + self._offset

    def advance(self, hours: float) -> datetime:
        if hours < 0:
            raise ValueError("the clock can only move forward")
        with self._lock:
            self._offset += timedelta(hours=hours)
        return self.now()

    def reset(self) -> None:
        with self._lock:
            self._offset = timedelta(0)


clock = SimClock()
