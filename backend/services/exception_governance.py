"""Exception governance helpers: lifecycle state and reminder/revalidation scheduling."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

LIFECYCLE_ACTIVE = "active"
LIFECYCLE_EXPIRING = "expiring"
LIFECYCLE_ACTION_REQUIRED = "action_required"
LIFECYCLE_EXPIRED = "expired"

EXPIRING_SOON_DAYS = 3


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def schedule_next_reminder_at(
    *,
    expires_at: datetime,
    interval_days: int | None,
    now: datetime,
    last_reminded_at: datetime | None,
) -> datetime | None:
    """Compute next reminder timestamp while never scheduling beyond expiry."""
    if not interval_days or interval_days <= 0:
        return None
    expiry_utc = _as_utc(expires_at)
    base = _as_utc(last_reminded_at) if last_reminded_at else _as_utc(now)
    candidate = base + timedelta(days=int(interval_days))
    return expiry_utc if candidate > expiry_utc else candidate


def schedule_next_revalidation_at(
    *,
    expires_at: datetime,
    interval_days: int | None,
    now: datetime,
    last_revalidated_at: datetime | None,
) -> datetime | None:
    """Compute next revalidation timestamp while never scheduling beyond expiry."""
    if not interval_days or interval_days <= 0:
        return None
    expiry_utc = _as_utc(expires_at)
    base = _as_utc(last_revalidated_at) if last_revalidated_at else _as_utc(now)
    candidate = base + timedelta(days=int(interval_days))
    return expiry_utc if candidate > expiry_utc else candidate


def get_exception_lifecycle_status(exception, now: datetime | None = None) -> str:
    """Resolve governance lifecycle from expiry, reminder, and revalidation schedule."""
    if not getattr(exception, "expires_at", None):
        return LIFECYCLE_ACTION_REQUIRED

    current = _as_utc(now or datetime.now(timezone.utc))
    expires_at = _as_utc(exception.expires_at)
    if expires_at <= current:
        return LIFECYCLE_EXPIRED

    next_revalidation = getattr(exception, "next_revalidation_at", None)
    next_reminder = getattr(exception, "next_reminder_at", None)
    if next_revalidation and _as_utc(next_revalidation) <= current:
        return LIFECYCLE_ACTION_REQUIRED
    if next_reminder and _as_utc(next_reminder) <= current:
        return LIFECYCLE_ACTION_REQUIRED

    if expires_at <= current + timedelta(days=EXPIRING_SOON_DAYS):
        return LIFECYCLE_EXPIRING
    return LIFECYCLE_ACTIVE


def is_reminder_due(exception, now: datetime | None = None) -> bool:
    current = _as_utc(now or datetime.now(timezone.utc))
    next_reminder = getattr(exception, "next_reminder_at", None)
    if not next_reminder:
        return False
    return _as_utc(next_reminder) <= current


def is_revalidation_due(exception, now: datetime | None = None) -> bool:
    current = _as_utc(now or datetime.now(timezone.utc))
    next_revalidation = getattr(exception, "next_revalidation_at", None)
    if not next_revalidation:
        return False
    return _as_utc(next_revalidation) <= current
