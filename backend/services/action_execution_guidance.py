"""
Shared execution guidance builder for action detail responses.

This composes existing remediation risk and runtime-check services into a
stable, mode-aware contract that security and engineering can execute from
without a separate handoff step.
"""
from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from backend.models.action import Action
from backend.models.aws_account import AwsAccount
from backend.services.direct_fix_bridge import get_supported_direct_fix_action_types
from backend.services.remediation_profile_selection import resolve_runtime_probe_inputs
from backend.services.remediation_risk import evaluate_strategy_impact
from backend.services.remediation_runtime_checks import collect_runtime_risk_signals
from backend.services.remediation_strategy import (
    BlastRadius,
    RemediationStrategy,
    get_blast_radius,
    get_estimated_resolution_time,
    get_rollback_command,
    list_strategies_for_action_type,
    supports_immediate_reeval,
)

GuidanceStatus = Literal["pass", "warn", "unknown", "fail", "info"]

_S3_BUCKET_ARN_PATTERN = re.compile(r"arn:aws:s3:::(?P<bucket>[A-Za-z0-9.\-_]{3,63})")
_SECURITY_GROUP_ID_PATTERN = re.compile(r"\bsg-[0-9a-fA-F]{8,17}\b")


class ExecutionGuidanceCheck(TypedDict):
    """One execution-check item for action detail guidance."""

    code: str
    status: GuidanceStatus
    message: str


class ExecutionGuidanceRollback(TypedDict):
    """Rollback guidance for one strategy."""

    summary: str
    command: str
    notes: list[str]


class ActionExecutionGuidance(TypedDict):
    """Structured execution guidance for one actionable strategy."""

    strategy_id: str
    label: str
    mode: Literal["pr_only", "direct_fix"]
    recommended: bool
    blast_radius: BlastRadius
    blast_radius_summary: str
    pre_checks: list[ExecutionGuidanceCheck]
    expected_outcome: str
    post_checks: list[ExecutionGuidanceCheck]
    rollback: ExecutionGuidanceRollback


def build_action_execution_guidance(
    action: Action,
    *,
    account: AwsAccount | None = None,
) -> list[ActionExecutionGuidance]:
    """Return additive execution guidance for actionable strategies."""
    strategies = _actionable_strategies(action)
    if not strategies:
        return []
    return [_build_strategy_guidance(action, strategy, account) for strategy in strategies]


def _actionable_strategies(action: Action) -> list[RemediationStrategy]:
    strategies = list_strategies_for_action_type(getattr(action, "action_type", None))
    actionable = [strategy for strategy in strategies if not strategy.get("exception_only")]
    if actionable:
        return actionable
    return _fallback_actionable_strategies(action)


def _fallback_actionable_strategies(action: Action) -> list[RemediationStrategy]:
    action_type = str(getattr(action, "action_type", "") or "").strip()
    if action_type not in get_supported_direct_fix_action_types():
        return []
    return [
        RemediationStrategy(
            strategy_id=f"{action_type}_direct_fix_fallback",
            action_type=action_type,
            label="Direct fix",
            mode="direct_fix",
            risk_level="medium",
            recommended=True,
            requires_inputs=False,
            input_schema={"fields": []},
            supports_exception_flow=False,
            exception_only=False,
            warnings=[],
            legacy_pr_bundle_variant=None,
        )
    ]


def _build_strategy_guidance(
    action: Action,
    strategy: RemediationStrategy,
    account: AwsAccount | None,
) -> ActionExecutionGuidance:
    probe_inputs = resolve_runtime_probe_inputs(
        action_type=action.action_type,
        strategy=strategy,
        requested_profile_id=None,
        explicit_inputs=None,
        tenant_settings=None,
        action=action,
    )
    runtime_signals = collect_runtime_risk_signals(action, strategy, probe_inputs, account)
    risk_snapshot = evaluate_strategy_impact(
        action,
        strategy,
        probe_inputs,
        account=account,
        runtime_signals=runtime_signals,
    )
    blast_radius = get_blast_radius(action.action_type, strategy["strategy_id"])
    return {
        "strategy_id": strategy["strategy_id"],
        "label": strategy["label"],
        "mode": strategy["mode"],
        "recommended": bool(strategy.get("recommended")),
        "blast_radius": blast_radius,
        "blast_radius_summary": _blast_radius_summary(action, blast_radius),
        "pre_checks": _pre_checks(action, strategy, risk_snapshot),
        "expected_outcome": _expected_outcome(action, strategy),
        "post_checks": _post_checks(action, strategy, blast_radius),
        "rollback": _rollback(action, strategy, runtime_signals),
    }


def _pre_checks(
    action: Action,
    strategy: RemediationStrategy,
    risk_snapshot: dict[str, Any],
) -> list[ExecutionGuidanceCheck]:
    checks = [_scope_check(action), _mode_pre_check(strategy)]
    input_check = _input_pre_check(strategy)
    if input_check is not None:
        checks.append(input_check)
    checks.extend(_risk_checks(risk_snapshot))
    return checks


def _scope_check(action: Action) -> ExecutionGuidanceCheck:
    scope = _scope_text(action)
    return _check("target_scope_confirmed", "info", f"Confirm this change is intended for {scope}.")


def _mode_pre_check(strategy: RemediationStrategy) -> ExecutionGuidanceCheck:
    if strategy["mode"] == "direct_fix":
        return _check(
            "direct_fix_change_window",
            "info",
            "Direct fix mutates AWS state immediately after approval. Confirm change window and rollback owner before execution.",
        )
    return _check(
        "pr_bundle_owner_confirmed",
        "info",
        "Confirm the repository, deployment path, and approver that own this infrastructure change before generating the PR bundle.",
    )


def _input_pre_check(strategy: RemediationStrategy) -> ExecutionGuidanceCheck | None:
    if not strategy.get("requires_inputs"):
        return None
    keys = _input_keys(strategy)
    detail = ", ".join(keys[:4]) if keys else "strategy-specific fields"
    return _check(
        "strategy_inputs_required",
        "info",
        f"Provide the required strategy inputs before execution: {detail}.",
    )


def _risk_checks(risk_snapshot: dict[str, Any]) -> list[ExecutionGuidanceCheck]:
    raw_checks = risk_snapshot.get("checks")
    if not isinstance(raw_checks, list):
        return []
    checks: list[ExecutionGuidanceCheck] = []
    for raw_check in raw_checks:
        if not isinstance(raw_check, dict):
            continue
        checks.append(
            _check(
                str(raw_check.get("code") or "risk_check"),
                _normalize_status(raw_check.get("status")),
                str(raw_check.get("message") or "Review this remediation dependency check."),
            )
        )
    return checks


def _expected_outcome(action: Action, strategy: RemediationStrategy) -> str:
    summary = _strategy_outcome_summary(action, strategy)
    resolution_time = get_estimated_resolution_time(action.action_type, strategy["strategy_id"])
    if strategy["mode"] == "direct_fix":
        return (
            f"Direct fix applies the change in AWS immediately: {summary} Security Hub should reflect the remediated state "
            f"within {resolution_time}."
        )
    return (
        f"PR mode produces a reviewable infrastructure change: {summary} After merge and apply through your IaC path, "
        f"Security Hub should reflect the remediated state within {resolution_time}."
    )


def _strategy_outcome_summary(action: Action, strategy: RemediationStrategy) -> str:
    impact_text = str(strategy.get("impact_text") or "").strip()
    if impact_text:
        return impact_text
    title = str(getattr(action, "title", "") or "").strip()
    if title:
        return title
    label = str(strategy.get("label") or "").strip()
    if label:
        return label
    return "The selected secure state is applied to the intended scope."


def _post_checks(
    action: Action,
    strategy: RemediationStrategy,
    blast_radius: BlastRadius,
) -> list[ExecutionGuidanceCheck]:
    if strategy["mode"] == "direct_fix":
        checks = [_direct_fix_completion_check(), _scope_verification_check(action, blast_radius)]
    else:
        checks = [_pr_apply_completion_check(), _scope_verification_check(action, blast_radius)]
    checks.append(_closure_check(action, strategy))
    return checks


def _direct_fix_completion_check() -> ExecutionGuidanceCheck:
    return _check(
        "direct_fix_run_success",
        "info",
        "Confirm the remediation run completed successfully and capture the run logs or audit artifacts for change evidence.",
    )


def _pr_apply_completion_check() -> ExecutionGuidanceCheck:
    return _check(
        "pr_bundle_review_and_apply",
        "info",
        "Review the generated bundle or diff, then capture plan and apply evidence after the change is merged through the normal infrastructure workflow.",
    )


def _scope_verification_check(action: Action, blast_radius: BlastRadius) -> ExecutionGuidanceCheck:
    return _check(
        "scope_verification",
        "info",
        f"Verify the completed change only affected the intended {blast_radius.replace('_', ' ')} scope for {_target_label(action)}.",
    )


def _closure_check(action: Action, strategy: RemediationStrategy) -> ExecutionGuidanceCheck:
    resolution_time = get_estimated_resolution_time(action.action_type, strategy["strategy_id"])
    if supports_immediate_reeval(action.action_type, strategy["strategy_id"]):
        return _check(
            "control_closure_confirmation",
            "info",
            "Trigger immediate re-evaluation after the change lands and confirm the action closes without reopening.",
        )
    return _check(
        "control_closure_confirmation",
        "info",
        f"Within {resolution_time}, confirm the finding or action moves to PASSED/resolved in Security Hub and the action queue.",
    )


def _rollback(
    action: Action,
    strategy: RemediationStrategy,
    runtime_signals: dict[str, Any],
) -> ExecutionGuidanceRollback:
    raw_command = get_rollback_command(action.action_type, strategy["strategy_id"])
    command = _hydrate_rollback_command(raw_command, action, runtime_signals)
    summary = _rollback_summary(strategy)
    notes = [_rollback_note(strategy)]
    return {"summary": summary, "command": command, "notes": notes}


def _rollback_summary(strategy: RemediationStrategy) -> str:
    if strategy["mode"] == "direct_fix":
        return "Use this rollback command to revert the live AWS change if verification fails or the blast radius is broader than expected."
    return "Use this rollback path to revert the infrastructure change through the same reviewed delivery workflow."


def _rollback_note(strategy: RemediationStrategy) -> str:
    if strategy["mode"] == "direct_fix":
        return "Capture the current state before approval when your operating policy requires a backout snapshot."
    return "Prefer reverting through version control and your normal deployment pipeline so rollback stays auditable."


def _hydrate_rollback_command(
    raw_command: str | None,
    action: Action,
    runtime_signals: dict[str, Any],
) -> str:
    command = str(raw_command or "").strip()
    if not command:
        return "Revert the generated infrastructure change through the same deployment path used for apply."
    for placeholder, value in _rollback_values(action, runtime_signals).items():
        if value:
            command = command.replace(placeholder, value)
    return command


def _rollback_values(action: Action, runtime_signals: dict[str, Any]) -> dict[str, str]:
    evidence = runtime_signals.get("evidence")
    context = runtime_signals.get("context")
    return {
        "<ACCOUNT_ID>": str(getattr(action, "account_id", "") or "").strip(),
        "<BUCKET_NAME>": _bucket_name(action, evidence),
        "<SOURCE_BUCKET>": _bucket_name(action, evidence),
        "<SECURITY_GROUP_ID>": _security_group_id(action, evidence),
        "<RECORDER_NAME>": _evidence_value(evidence, "config_recorder_name") or "default",
        "<TRAIL_NAME>": _trail_name(context),
    }


def _bucket_name(action: Action, evidence: Any) -> str:
    evidence_bucket = _evidence_value(evidence, "target_bucket")
    if evidence_bucket:
        return evidence_bucket
    target_id = str(getattr(action, "target_id", "") or "").strip()
    match = _S3_BUCKET_ARN_PATTERN.search(target_id)
    if match:
        return match.group("bucket")
    if target_id.startswith("arn:aws:s3:::"):
        return target_id.split("arn:aws:s3:::")[-1].split("/")[0].strip()
    return target_id if target_id and target_id.startswith("s3://") is False else ""


def _security_group_id(action: Action, evidence: Any) -> str:
    evidence_id = _evidence_value(evidence, "security_group_id")
    if evidence_id:
        return evidence_id
    target_id = str(getattr(action, "target_id", "") or "").strip()
    match = _SECURITY_GROUP_ID_PATTERN.search(target_id)
    return match.group(0) if match else ""


def _trail_name(context: Any) -> str:
    if not isinstance(context, dict):
        return "security-autopilot-trail"
    default_inputs = context.get("default_inputs")
    if not isinstance(default_inputs, dict):
        return "security-autopilot-trail"
    return str(default_inputs.get("trail_name") or "security-autopilot-trail").strip()


def _input_keys(strategy: RemediationStrategy) -> list[str]:
    schema = strategy.get("input_schema")
    fields = schema.get("fields") if isinstance(schema, dict) else []
    if not isinstance(fields, list):
        return []
    required = [str(field.get("key") or "").strip() for field in fields if field.get("required")]
    names = [key for key in required if key]
    if names:
        return names
    return [str(field.get("key") or "").strip() for field in fields if str(field.get("key") or "").strip()]


def _scope_text(action: Action) -> str:
    account_id = str(getattr(action, "account_id", "") or "").strip()
    region = str(getattr(action, "region", "") or "").strip()
    target = _target_label(action)
    if region:
        return f"{target} in account {account_id} ({region})"
    return f"{target} in account {account_id}"


def _target_label(action: Action) -> str:
    resource_id = str(getattr(action, "resource_id", "") or "").strip()
    if resource_id:
        return resource_id
    target_id = str(getattr(action, "target_id", "") or "").strip()
    return target_id or "the affected resource"


def _blast_radius_summary(action: Action, blast_radius: BlastRadius) -> str:
    if blast_radius == "account":
        return f"Affects account-wide security posture for account {action.account_id}."
    if blast_radius == "access_changing":
        return f"Changes live access behavior for {_target_label(action)}."
    return f"Targets {_target_label(action)} without intending account-wide mutation."


def _normalize_status(raw_status: Any) -> GuidanceStatus:
    normalized = str(raw_status or "").strip().lower()
    if normalized in {"pass", "warn", "unknown", "fail"}:
        return normalized  # type: ignore[return-value]
    return "info"


def _evidence_value(evidence: Any, key: str) -> str:
    if not isinstance(evidence, dict):
        return ""
    return str(evidence.get(key) or "").strip()


def _check(code: str, status: GuidanceStatus, message: str) -> ExecutionGuidanceCheck:
    return {"code": code, "status": status, "message": message}
