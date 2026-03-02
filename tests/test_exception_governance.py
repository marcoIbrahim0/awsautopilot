from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.services.exception_governance import (
    LIFECYCLE_ACTION_REQUIRED,
    LIFECYCLE_ACTIVE,
    LIFECYCLE_EXPIRED,
    LIFECYCLE_EXPIRING,
    get_exception_lifecycle_status,
    is_reminder_due,
    is_revalidation_due,
    schedule_next_revalidation_at,
    schedule_next_reminder_at,
)


@dataclass
class _ExceptionStub:
    expires_at: datetime
    next_reminder_at: datetime | None = None
    next_revalidation_at: datetime | None = None


def test_lifecycle_active() -> None:
    now = datetime.now(timezone.utc)
    exc = _ExceptionStub(expires_at=now + timedelta(days=10))
    assert get_exception_lifecycle_status(exc, now=now) == LIFECYCLE_ACTIVE


def test_lifecycle_expiring() -> None:
    now = datetime.now(timezone.utc)
    exc = _ExceptionStub(expires_at=now + timedelta(days=1))
    assert get_exception_lifecycle_status(exc, now=now) == LIFECYCLE_EXPIRING


def test_lifecycle_action_required_on_due_reminder() -> None:
    now = datetime.now(timezone.utc)
    exc = _ExceptionStub(
        expires_at=now + timedelta(days=10),
        next_reminder_at=now - timedelta(minutes=1),
    )
    assert get_exception_lifecycle_status(exc, now=now) == LIFECYCLE_ACTION_REQUIRED


def test_lifecycle_expired() -> None:
    now = datetime.now(timezone.utc)
    exc = _ExceptionStub(expires_at=now - timedelta(seconds=1))
    assert get_exception_lifecycle_status(exc, now=now) == LIFECYCLE_EXPIRED


def test_schedule_next_reminder_caps_at_expiry() -> None:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=2)
    next_due = schedule_next_reminder_at(
        expires_at=expires_at,
        interval_days=7,
        now=now,
        last_reminded_at=None,
    )
    assert next_due == expires_at


def test_schedule_next_revalidation_uses_last_revalidated() -> None:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=30)
    last_revalidated = now - timedelta(days=2)
    next_due = schedule_next_revalidation_at(
        expires_at=expires_at,
        interval_days=10,
        now=now,
        last_revalidated_at=last_revalidated,
    )
    assert next_due == last_revalidated + timedelta(days=10)


def test_due_helpers() -> None:
    now = datetime.now(timezone.utc)
    exc = _ExceptionStub(
        expires_at=now + timedelta(days=20),
        next_reminder_at=now - timedelta(minutes=1),
        next_revalidation_at=now + timedelta(days=1),
    )
    assert is_reminder_due(exc, now=now) is True
    assert is_revalidation_due(exc, now=now) is False
