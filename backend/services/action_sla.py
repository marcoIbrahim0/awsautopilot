"""Deterministic SLA policy and escalation helpers for actions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Literal

from sqlalchemy import and_, case

from backend.config import settings

RiskTier = Literal["critical", "high", "medium", "low"]
SLAState = Literal["on_track", "expiring", "overdue"]
EscalationLevel = Literal["warning", "breach"]

CRITICAL_SCORE_MIN = 90
HIGH_SCORE_MIN = 70
MEDIUM_SCORE_MIN = 40
HIGH_IMPACT_RISK_TIERS = frozenset({"critical", "high"})


@dataclass(frozen=True)
class ActionSLAStatus:
    risk_tier: RiskTier
    due_in_hours: int
    expiring_in_hours: int
    due_at: datetime
    expiring_at: datetime
    state: SLAState
    is_expiring: bool
    is_overdue: bool
    hours_until_due: int | None
    hours_overdue: int | None
    escalation_level: EscalationLevel | None
    escalation_eligible: bool
    escalation_reason: str | None
    has_active_exception: bool


def normalize_action_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def risk_tier_from_score(score: int | None) -> RiskTier:
    value = int(score or 0)
    if value >= CRITICAL_SCORE_MIN:
        return "critical"
    if value >= HIGH_SCORE_MIN:
        return "high"
    if value >= MEDIUM_SCORE_MIN:
        return "medium"
    return "low"


def sla_due_in_hours_for_score(score: int | None) -> int:
    tier = risk_tier_from_score(score)
    if tier == "critical":
        return int(settings.ACTIONS_OWNER_QUEUE_OVERDUE_CRITICAL_HOURS)
    if tier == "high":
        return int(settings.ACTIONS_OWNER_QUEUE_OVERDUE_HIGH_HOURS)
    if tier == "medium":
        return int(settings.ACTIONS_OWNER_QUEUE_OVERDUE_DEFAULT_HOURS)
    return int(settings.ACTIONS_OWNER_QUEUE_OVERDUE_LOW_HOURS)


def sla_expiring_in_hours_for_score(score: int | None) -> int:
    due_in_hours = max(1, sla_due_in_hours_for_score(score))
    return max(6, min(72, due_in_hours // 3))


def compute_action_sla(
    *,
    created_at: datetime | None,
    score: int | None,
    now: datetime | None = None,
    has_active_exception: bool = False,
) -> ActionSLAStatus | None:
    created_at_utc = normalize_action_timestamp(created_at)
    if created_at_utc is None:
        return None

    reference = normalize_action_timestamp(now) or datetime.now(timezone.utc)
    due_in_hours = sla_due_in_hours_for_score(score)
    expiring_in_hours = sla_expiring_in_hours_for_score(score)
    due_at = created_at_utc + timedelta(hours=due_in_hours)
    expiring_at = due_at - timedelta(hours=expiring_in_hours)
    is_overdue = reference >= due_at
    is_expiring = not is_overdue and reference >= expiring_at
    state: SLAState = "overdue" if is_overdue else "expiring" if is_expiring else "on_track"

    seconds_until_due = (due_at - reference).total_seconds()
    seconds_overdue = (reference - due_at).total_seconds()
    hours_until_due = None if is_overdue else max(0, math.ceil(seconds_until_due / 3600))
    hours_overdue = max(0, math.ceil(seconds_overdue / 3600)) if is_overdue else None

    risk_tier = risk_tier_from_score(score)
    escalation_eligible = (
        risk_tier in HIGH_IMPACT_RISK_TIERS
        and state in {"expiring", "overdue"}
        and not has_active_exception
    )
    escalation_level: EscalationLevel | None = None
    escalation_reason: str | None = None
    if escalation_eligible:
        if is_overdue:
            escalation_level = "breach"
            escalation_reason = "High-impact action is overdue and has no active exception."
        else:
            escalation_level = "warning"
            escalation_reason = "High-impact action is nearing its SLA due time and has no active exception."

    return ActionSLAStatus(
        risk_tier=risk_tier,
        due_in_hours=due_in_hours,
        expiring_in_hours=expiring_in_hours,
        due_at=due_at,
        expiring_at=expiring_at,
        state=state,
        is_expiring=is_expiring,
        is_overdue=is_overdue,
        hours_until_due=hours_until_due,
        hours_overdue=hours_overdue,
        escalation_level=escalation_level,
        escalation_eligible=escalation_eligible,
        escalation_reason=escalation_reason,
        has_active_exception=bool(has_active_exception),
    )


def build_action_escalation_context(
    *,
    action_id: Any,
    action_type: str | None,
    title: str | None,
    owner_type: str | None,
    owner_key: str | None,
    owner_label: str | None,
    created_at: datetime | None,
    score: int | None,
    now: datetime | None = None,
    has_active_exception: bool = False,
) -> dict[str, Any] | None:
    sla = compute_action_sla(
        created_at=created_at,
        score=score,
        now=now,
        has_active_exception=has_active_exception,
    )
    if sla is None or not sla.escalation_eligible:
        return None
    return {
        "action_id": str(action_id),
        "action_type": action_type,
        "title": title,
        "owner_type": owner_type,
        "owner_key": owner_key,
        "owner_label": owner_label,
        "risk_tier": sla.risk_tier,
        "sla_state": sla.state,
        "due_at": sla.due_at.isoformat(),
        "expiring_at": sla.expiring_at.isoformat(),
        "due_in_hours": sla.due_in_hours,
        "expiring_in_hours": sla.expiring_in_hours,
        "hours_until_due": sla.hours_until_due,
        "hours_overdue": sla.hours_overdue,
        "escalation_level": sla.escalation_level,
        "escalation_reason": sla.escalation_reason,
    }


def action_sla_overdue_cutoff_expr(*, now: datetime, score_expr: object) -> object:
    return case(
        (
            score_expr >= CRITICAL_SCORE_MIN,
            now - timedelta(hours=settings.ACTIONS_OWNER_QUEUE_OVERDUE_CRITICAL_HOURS),
        ),
        (
            score_expr >= HIGH_SCORE_MIN,
            now - timedelta(hours=settings.ACTIONS_OWNER_QUEUE_OVERDUE_HIGH_HOURS),
        ),
        (
            score_expr >= MEDIUM_SCORE_MIN,
            now - timedelta(hours=settings.ACTIONS_OWNER_QUEUE_OVERDUE_DEFAULT_HOURS),
        ),
        else_=now - timedelta(hours=settings.ACTIONS_OWNER_QUEUE_OVERDUE_LOW_HOURS),
    )


def action_sla_expiring_cutoff_expr(*, now: datetime, score_expr: object) -> object:
    return case(
        (
            score_expr >= CRITICAL_SCORE_MIN,
            now - timedelta(
                hours=settings.ACTIONS_OWNER_QUEUE_OVERDUE_CRITICAL_HOURS
                - sla_expiring_in_hours_for_score(CRITICAL_SCORE_MIN)
            ),
        ),
        (
            score_expr >= HIGH_SCORE_MIN,
            now - timedelta(
                hours=settings.ACTIONS_OWNER_QUEUE_OVERDUE_HIGH_HOURS
                - sla_expiring_in_hours_for_score(HIGH_SCORE_MIN)
            ),
        ),
        (
            score_expr >= MEDIUM_SCORE_MIN,
            now - timedelta(
                hours=settings.ACTIONS_OWNER_QUEUE_OVERDUE_DEFAULT_HOURS
                - sla_expiring_in_hours_for_score(MEDIUM_SCORE_MIN)
            ),
        ),
        else_=now - timedelta(
            hours=settings.ACTIONS_OWNER_QUEUE_OVERDUE_LOW_HOURS - sla_expiring_in_hours_for_score(0)
        ),
    )


def action_sla_overdue_expr(*, created_at_expr: object, now: datetime, score_expr: object) -> object:
    return created_at_expr <= action_sla_overdue_cutoff_expr(now=now, score_expr=score_expr)


def action_sla_expiring_expr(*, created_at_expr: object, now: datetime, score_expr: object) -> object:
    overdue_cutoff = action_sla_overdue_cutoff_expr(now=now, score_expr=score_expr)
    expiring_cutoff = action_sla_expiring_cutoff_expr(now=now, score_expr=score_expr)
    return and_(
        created_at_expr <= expiring_cutoff,
        created_at_expr > overdue_cutoff,
    )
