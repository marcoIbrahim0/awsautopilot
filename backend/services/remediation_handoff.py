"""Shared handoff/closure metadata builders for remediation actions and runs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from pydantic import BaseModel, Field

_CLOSURE_COMPLETE_ACTION_STATUSES = {"resolved", "suppressed"}
_TERMINAL_RUN_STATUSES = {"success", "failed", "cancelled"}


class ImplementationArtifactLink(BaseModel):
    """One implementation artifact surfaced to engineering users."""

    key: str
    kind: str
    label: str
    description: str
    href: str | None = None
    executable: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidencePointer(BaseModel):
    """One evidence pointer tied to a remediation run."""

    key: str
    kind: str
    label: str
    description: str
    href: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClosureChecklistItem(BaseModel):
    """One closure step for a remediation run."""

    id: str
    title: str
    status: str
    detail: str
    evidence_keys: list[str] = Field(default_factory=list)


class RunArtifactMetadata(BaseModel):
    """Normalized run metadata for handoff-free closure UX."""

    implementation_artifacts: list[ImplementationArtifactLink] = Field(default_factory=list)
    evidence_pointers: list[EvidencePointer] = Field(default_factory=list)
    closure_checklist: list[ClosureChecklistItem] = Field(default_factory=list)


class ActionImplementationArtifactLink(BaseModel):
    """Action-detail summary of one linked remediation artifact."""

    run_id: str
    run_status: str
    run_mode: str
    artifact_key: str
    kind: str
    label: str
    description: str
    href: str
    executable: bool = False
    generated_at: str | None = None
    closure_status: str = "pending"
    metadata: dict[str, Any] = Field(default_factory=dict)


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return _string(value)


def _run_route(run_id: str, anchor: str | None = None) -> str:
    if not anchor:
        return f"/remediation-runs/{run_id}"
    return f"/remediation-runs/{run_id}#{anchor}"


def _bundle_metadata(artifacts: dict[str, Any]) -> dict[str, Any]:
    pr_bundle = _safe_dict(artifacts.get("pr_bundle"))
    files = _safe_list(pr_bundle.get("files"))
    steps = _safe_list(pr_bundle.get("steps"))
    metadata = _safe_dict(pr_bundle.get("metadata"))
    return {
        "format": _string(pr_bundle.get("format")) or "terraform",
        "file_count": len(files),
        "step_count": len(steps),
        "has_readme": any(str(item.get("path", "")).startswith("README") for item in files if isinstance(item, dict)),
        "generated_action_count": metadata.get("generated_action_count"),
        "skipped_action_count": metadata.get("skipped_action_count"),
    }


def _bundle_artifact(run_id: str, artifacts: dict[str, Any]) -> ImplementationArtifactLink | None:
    pr_bundle = _safe_dict(artifacts.get("pr_bundle"))
    if not _safe_list(pr_bundle.get("files")):
        return None
    metadata = _bundle_metadata(artifacts)
    file_count = int(metadata["file_count"] or 0)
    format_name = str(metadata["format"] or "terraform").capitalize()
    return ImplementationArtifactLink(
        key="pr_bundle",
        kind="bundle",
        label="Engineering PR bundle",
        description=f"{format_name} remediation bundle with {file_count} file{'s' if file_count != 1 else ''}.",
        href=_run_route(run_id, "run-generated-files"),
        executable=True,
        metadata=metadata,
    )


def _pr_payload_metadata(artifacts: dict[str, Any]) -> dict[str, Any]:
    payload = _safe_dict(artifacts.get("pr_payload"))
    repo_target = _safe_dict(payload.get("repo_target"))
    diff_metadata = _safe_dict(payload.get("diff_metadata"))
    return {
        "provider": _string(repo_target.get("provider")) or "generic_git",
        "repository": _string(repo_target.get("repository")),
        "base_branch": _string(repo_target.get("base_branch")),
        "head_branch": _string(repo_target.get("head_branch")),
        "root_path": _string(repo_target.get("root_path")),
        "file_count": diff_metadata.get("file_count"),
        "fingerprint_sha256": _string(diff_metadata.get("fingerprint_sha256")),
    }


def _pr_payload_artifact(run_id: str, artifacts: dict[str, Any]) -> ImplementationArtifactLink | None:
    payload = _safe_dict(artifacts.get("pr_payload"))
    if not payload:
        return None
    metadata = _pr_payload_metadata(artifacts)
    repository = _string(metadata.get("repository")) or "configured repository"
    base_branch = _string(metadata.get("base_branch")) or "default branch"
    file_count = int(metadata.get("file_count") or 0)
    return ImplementationArtifactLink(
        key="pr_payload",
        kind="pr_payload",
        label="Provider-agnostic PR payload",
        description=(
            f"Draft PR payload for {repository} -> {base_branch} "
            f"covering {file_count} mapped file{'s' if file_count != 1 else ''}."
        ),
        href=_run_route(run_id, "run-generated-files"),
        executable=False,
        metadata=metadata,
    )


def _change_summary_metadata(artifacts: dict[str, Any]) -> dict[str, Any]:
    summary = _safe_dict(artifacts.get("change_summary"))
    changes = _safe_list(summary.get("changes"))
    return {
        "applied_at": _iso(summary.get("applied_at")),
        "applied_by": _string(summary.get("applied_by")) or "system",
        "change_count": len(changes),
    }


def _change_summary_artifact(run_id: str, artifacts: dict[str, Any]) -> ImplementationArtifactLink | None:
    summary = _safe_dict(artifacts.get("change_summary"))
    if not _safe_list(summary.get("changes")):
        return None
    metadata = _change_summary_metadata(artifacts)
    change_count = int(metadata["change_count"] or 0)
    applied_by = str(metadata["applied_by"] or "system")
    return ImplementationArtifactLink(
        key="change_summary",
        kind="change_summary",
        label="Applied change summary",
        description=f"{change_count} recorded change{'s' if change_count != 1 else ''} applied by {applied_by}.",
        href=_run_route(run_id, "run-activity"),
        executable=False,
        metadata=metadata,
    )


def _direct_fix_metadata(artifacts: dict[str, Any], outcome: str | None) -> dict[str, Any]:
    payload = _safe_dict(artifacts.get("direct_fix"))
    recorded_at = _iso(payload.get("recorded_at"))
    return {
        "outcome": _string(payload.get("outcome")) or outcome,
        "recorded_at": recorded_at,
        "post_check_passed": bool(payload.get("post_check_passed")),
        "log_count": int(payload.get("log_count") or 0),
    }


def _direct_fix_artifact(
    run_id: str,
    artifacts: dict[str, Any],
    outcome: str | None,
) -> ImplementationArtifactLink | None:
    payload = _safe_dict(artifacts.get("direct_fix"))
    if not payload and not outcome:
        return None
    metadata = _direct_fix_metadata(artifacts, outcome)
    detail = _string(metadata.get("outcome")) or "Direct fix outcome recorded."
    return ImplementationArtifactLink(
        key="direct_fix",
        kind="direct_fix",
        label="Applied direct-fix record",
        description=detail,
        href=_run_route(run_id, "run-activity"),
        executable=False,
        metadata=metadata,
    )


def _risk_snapshot_pointer(run_id: str, artifacts: dict[str, Any]) -> EvidencePointer | None:
    snapshot = _safe_dict(artifacts.get("risk_snapshot"))
    checks = _safe_list(snapshot.get("checks"))
    if not snapshot and not checks:
        return None
    return EvidencePointer(
        key="risk_snapshot",
        kind="risk_snapshot",
        label="Dependency review snapshot",
        description=f"{len(checks)} dependency check{'s' if len(checks) != 1 else ''} captured for this run.",
        href=_run_route(run_id, "run-generated-files"),
        metadata={"check_count": len(checks), "recommendation": _string(snapshot.get("recommendation"))},
    )


def _diff_summary_pointer(run_id: str, artifacts: dict[str, Any]) -> EvidencePointer | None:
    summary = _safe_dict(artifacts.get("diff_summary"))
    if not summary:
        return None
    return EvidencePointer(
        key="diff_summary",
        kind="diff_summary",
        label="Generated diff summary",
        description=f"{int(summary.get('file_count') or 0)} mapped file(s) captured with reproducible hashes.",
        href=_run_route(run_id, "run-generated-files"),
        metadata={
            "file_count": int(summary.get("file_count") or 0),
            "fingerprint_sha256": _string(summary.get("fingerprint_sha256")),
        },
    )


def _rollback_notes_pointer(run_id: str, artifacts: dict[str, Any]) -> EvidencePointer | None:
    notes = _safe_dict(artifacts.get("rollback_notes"))
    if not notes:
        return None
    return EvidencePointer(
        key="rollback_notes",
        kind="rollback_notes",
        label="Rollback notes",
        description=f"{int(notes.get('entry_count') or 0)} rollback note(s) prepared for this run.",
        href=_run_route(run_id, "run-generated-files"),
        metadata={"entry_count": int(notes.get("entry_count") or 0)},
    )


def _control_mapping_pointer(run_id: str, artifacts: dict[str, Any]) -> EvidencePointer | None:
    context = _safe_dict(artifacts.get("control_mapping_context"))
    if not context:
        return None
    control_ids = _safe_list(context.get("control_ids"))
    mappings = _safe_list(context.get("mappings"))
    return EvidencePointer(
        key="control_mapping_context",
        kind="control_mapping_context",
        label="Control mapping context",
        description=f"{len(control_ids)} control ID(s) and {len(mappings)} framework mapping row(s) attached.",
        href=_run_route(run_id, "run-generated-files"),
        metadata={"control_count": len(control_ids), "mapping_count": len(mappings)},
    )


def _bundle_error_pointer(run_id: str, artifacts: dict[str, Any]) -> EvidencePointer | None:
    payload = _safe_dict(artifacts.get("pr_bundle_error"))
    detail = _string(payload.get("detail"))
    code = _string(payload.get("code"))
    if not detail and not code:
        return None
    description = detail or "PR bundle generation error recorded for this run."
    return EvidencePointer(
        key="pr_bundle_error",
        kind="bundle_error",
        label="PR bundle generation error",
        description=description,
        href=_run_route(run_id, "run-activity"),
        metadata={"code": code},
    )


def _activity_log_pointer(run_id: str, logs: str | None) -> EvidencePointer | None:
    lines = [line for line in (logs or "").splitlines() if line.strip()]
    if not lines:
        return None
    return EvidencePointer(
        key="activity_log",
        kind="activity_log",
        label="Run activity log",
        description=f"{len(lines)} execution log line{'s' if len(lines) != 1 else ''} recorded for this run.",
        href=_run_route(run_id, "run-activity"),
        metadata={"line_count": len(lines)},
    )


def _unique_pointers(pointers: Iterable[EvidencePointer]) -> list[EvidencePointer]:
    seen: set[str] = set()
    result: list[EvidencePointer] = []
    for pointer in pointers:
        if pointer.key in seen:
            continue
        seen.add(pointer.key)
        result.append(pointer)
    return result


def _implementation_artifacts(
    run_id: str,
    mode: str,
    artifacts: dict[str, Any],
    outcome: str | None,
) -> list[ImplementationArtifactLink]:
    items = [
        _bundle_artifact(run_id, artifacts),
        _pr_payload_artifact(run_id, artifacts),
        _change_summary_artifact(run_id, artifacts),
    ]
    if mode == "direct_fix":
        items.append(_direct_fix_artifact(run_id, artifacts, outcome))
    return [item for item in items if item is not None]


def _evidence_pointers(
    run_id: str,
    artifacts: dict[str, Any],
    logs: str | None,
    implementation_artifacts: list[ImplementationArtifactLink],
) -> list[EvidencePointer]:
    pointers = [
        EvidencePointer(**item.model_dump())
        for item in implementation_artifacts
    ]
    pointers.extend(
        [
            _risk_snapshot_pointer(run_id, artifacts),
            _diff_summary_pointer(run_id, artifacts),
            _rollback_notes_pointer(run_id, artifacts),
            _control_mapping_pointer(run_id, artifacts),
            _bundle_error_pointer(run_id, artifacts),
            _activity_log_pointer(run_id, logs),
        ]
    )
    return _unique_pointers(pointer for pointer in pointers if pointer is not None)


def _artifact_checklist_item(
    implementation_artifacts: list[ImplementationArtifactLink],
    status: str,
) -> ClosureChecklistItem:
    complete = bool(implementation_artifacts)
    detail = "Implementation artifact linked for engineering handoff." if complete else "No implementation artifact was recorded for this run."
    if status == "failed":
        detail = "Run failed before a reusable implementation artifact was recorded."
    return ClosureChecklistItem(
        id="artifact_recorded",
        title="Implementation artifact recorded",
        status="complete" if complete else "pending",
        detail=detail,
        evidence_keys=[item.key for item in implementation_artifacts],
    )


def _evidence_checklist_item(evidence_pointers: list[EvidencePointer]) -> ClosureChecklistItem:
    complete = bool(evidence_pointers)
    detail = "Evidence pointers are attached to this run." if complete else "No evidence pointers are attached to this run yet."
    return ClosureChecklistItem(
        id="evidence_attached",
        title="Evidence pointers attached",
        status="complete" if complete else "pending",
        detail=detail,
        evidence_keys=[item.key for item in evidence_pointers],
    )


def _verification_checklist_item(action_status: str | None) -> ClosureChecklistItem:
    complete = (action_status or "").strip().lower() in _CLOSURE_COMPLETE_ACTION_STATUSES
    detail = "The parent action is already marked resolved/suppressed." if complete else "Refresh or recompute the parent action to confirm closure."
    return ClosureChecklistItem(
        id="action_closure_verified",
        title="Action closure verified",
        status="complete" if complete else "pending",
        detail=detail,
    )


def _closure_checklist(
    status: str,
    action_status: str | None,
    implementation_artifacts: list[ImplementationArtifactLink],
    evidence_pointers: list[EvidencePointer],
) -> list[ClosureChecklistItem]:
    if status not in _TERMINAL_RUN_STATUSES:
        return []
    return [
        _artifact_checklist_item(implementation_artifacts, status),
        _evidence_checklist_item(evidence_pointers),
        _verification_checklist_item(action_status),
    ]


def build_run_artifact_metadata(
    *,
    run_id: Any,
    mode: Any,
    status: Any,
    artifacts: Any,
    outcome: Any = None,
    logs: Any = None,
    action_status: Any = None,
) -> RunArtifactMetadata:
    safe_run_id = str(run_id)
    safe_mode = _string(mode) or ""
    safe_status = _string(status) or ""
    safe_artifacts = _safe_dict(artifacts)
    safe_outcome = _string(outcome)
    safe_logs = logs if isinstance(logs, str) else None
    implementation = _implementation_artifacts(safe_run_id, safe_mode, safe_artifacts, safe_outcome)
    evidence = _evidence_pointers(safe_run_id, safe_artifacts, safe_logs, implementation)
    checklist = _closure_checklist(safe_status, _string(action_status), implementation, evidence)
    return RunArtifactMetadata(
        implementation_artifacts=implementation,
        evidence_pointers=evidence,
        closure_checklist=checklist,
    )


def build_action_implementation_artifacts(
    runs: Iterable[Any],
    *,
    action_status: Any,
) -> list[ActionImplementationArtifactLink]:
    items: list[ActionImplementationArtifactLink] = []
    closure_status = "complete" if _string(action_status) in _CLOSURE_COMPLETE_ACTION_STATUSES else "pending"
    for run in runs:
        metadata = build_run_artifact_metadata(
            run_id=getattr(run, "id", ""),
            mode=getattr(run, "mode", ""),
            status=getattr(run, "status", ""),
            artifacts=getattr(run, "artifacts", None),
            outcome=getattr(run, "outcome", None),
            logs=getattr(run, "logs", None),
            action_status=action_status,
        )
        items.extend(_action_links_for_run(run, metadata, closure_status))
    return items[:8]


def _action_links_for_run(
    run: Any,
    metadata: RunArtifactMetadata,
    closure_status: str,
) -> list[ActionImplementationArtifactLink]:
    run_id = str(getattr(run, "id", ""))
    run_mode = _string(getattr(run, "mode", "")) or ""
    run_status = _string(getattr(run, "status", "")) or ""
    generated_at = _iso(getattr(run, "completed_at", None)) or _iso(getattr(run, "created_at", None))
    items: list[ActionImplementationArtifactLink] = []
    for artifact in metadata.implementation_artifacts:
        items.append(
            ActionImplementationArtifactLink(
                run_id=run_id,
                run_status=run_status,
                run_mode=run_mode,
                artifact_key=artifact.key,
                kind=artifact.kind,
                label=artifact.label,
                description=artifact.description,
                href=artifact.href or _run_route(run_id),
                executable=artifact.executable,
                generated_at=generated_at,
                closure_status=closure_status,
                metadata=artifact.metadata,
            )
        )
    return items
