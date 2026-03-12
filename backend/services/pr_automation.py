"""Provider-agnostic PR automation artifacts for remediation bundles."""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
from typing import Any, Sequence

from backend.models.action import Action
from backend.services.remediation_strategy import get_rollback_command

_ARTIFACT_VERSION = 1
_AUTOMATION_DIR = "pr_automation"
_DIFF_SUMMARY_PATH = f"{_AUTOMATION_DIR}/diff_summary.json"
_ROLLBACK_NOTES_PATH = f"{_AUTOMATION_DIR}/rollback_notes.md"
_CONTROL_MAPPING_PATH = f"{_AUTOMATION_DIR}/control_mapping_context.json"
_PR_PAYLOAD_PATH = f"{_AUTOMATION_DIR}/pr_payload.json"
_BRANCH_TOKEN_PATTERN = re.compile(r"[^a-z0-9._/-]+")
_S3_BUCKET_ARN_PATTERN = re.compile(r"arn:aws:s3:::(?P<bucket>[A-Za-z0-9.\-_]{3,63})")
_SECURITY_GROUP_ID_PATTERN = re.compile(r"\bsg-[0-9a-zA-Z-]{8,}\b")


def build_pr_automation_artifacts(
    *,
    run_id: str,
    actions: Sequence[Action],
    bundle: dict[str, Any],
    repo_target: dict[str, Any] | None,
    strategy_id: str | None,
    control_mapping_rows: Sequence[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return enriched bundle plus additive PR-automation artifacts."""
    bundle_files = _normalize_bundle_files(bundle.get("files"))
    if not bundle_files:
        return bundle, {}
    normalized_target = normalize_repo_target(repo_target, run_id=run_id, actions=actions)
    diff_summary = _build_diff_summary(bundle_files, normalized_target)
    rollback_notes = _build_rollback_notes(actions, strategy_id)
    control_context = _build_control_mapping_context(actions, control_mapping_rows)
    pr_payload = _build_pr_payload(actions, normalized_target, diff_summary, rollback_notes, control_context)
    enriched = dict(bundle)
    enriched["files"] = bundle_files + _automation_files(diff_summary, rollback_notes, control_context, pr_payload)
    enriched["metadata"] = _merge_metadata(bundle, diff_summary, normalized_target, pr_payload)
    artifacts = _artifact_payload(diff_summary, rollback_notes, control_context, normalized_target, pr_payload)
    return enriched, artifacts


def normalize_repo_target(
    repo_target: dict[str, Any] | None,
    *,
    run_id: str,
    actions: Sequence[Action],
) -> dict[str, str] | None:
    """Normalize optional repo-target metadata into a stable payload."""
    if not isinstance(repo_target, dict):
        return None
    repository = _clean(repo_target.get("repository"))
    base_branch = _clean(repo_target.get("base_branch"))
    if not repository or not base_branch:
        return None
    target = {
        "provider": _clean(repo_target.get("provider")) or "generic_git",
        "repository": repository,
        "base_branch": base_branch,
        "head_branch": _clean(repo_target.get("head_branch")) or _default_head_branch(actions, run_id),
        "root_path": _normalize_root_path(repo_target.get("root_path")),
    }
    if not target["root_path"]:
        target.pop("root_path", None)
    return target


def _normalize_bundle_files(files: Any) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    if not isinstance(files, list):
        return result
    for item in files:
        normalized = _normalize_bundle_file(item)
        if normalized is not None:
            result.append(normalized)
    return result


def _normalize_bundle_file(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    path = _clean(item.get("path"))
    if not path:
        return None
    content = item.get("content")
    content_str = content if isinstance(content, str) else str(content or "")
    return {"path": path, "content": content_str}


def _build_diff_summary(
    files: Sequence[dict[str, str]],
    repo_target: dict[str, str] | None,
) -> dict[str, Any]:
    entries = [_diff_entry(file_item, repo_target) for file_item in files]
    fingerprint = _sha256(_json(entries))
    return {
        "version": _ARTIFACT_VERSION,
        "artifact_type": "generated_diff_summary",
        "repo_target_configured": repo_target is not None,
        "file_count": len(entries),
        "fingerprint_sha256": fingerprint,
        "files": entries,
        "summary_lines": [_summary_line(entry) for entry in entries],
    }


def _diff_entry(file_item: dict[str, str], repo_target: dict[str, str] | None) -> dict[str, Any]:
    content = file_item["content"]
    return {
        "bundle_path": file_item["path"],
        "repo_path": _repo_path(file_item["path"], repo_target),
        "change_type": "create_or_update",
        "content_sha256": _sha256(content),
        "byte_count": len(content.encode("utf-8")),
        "line_count": _line_count(content),
    }


def _build_rollback_notes(actions: Sequence[Action], strategy_id: str | None) -> dict[str, Any]:
    entries = [_rollback_entry(action, strategy_id) for action in actions]
    return {
        "version": _ARTIFACT_VERSION,
        "artifact_type": "rollback_notes",
        "entry_count": len(entries),
        "recommended_path": "Prefer reverting through version control and the same reviewed deployment workflow.",
        "entries": entries,
    }


def _rollback_entry(action: Action, strategy_id: str | None) -> dict[str, Any]:
    return {
        "action_id": str(action.id),
        "action_type": action.action_type,
        "control_id": _clean(action.control_id) or "",
        "title": _clean(action.title) or action.action_type,
        "target_id": _clean(action.target_id) or "",
        "rollback_command": _hydrate_rollback_command(action, strategy_id),
    }


def _build_control_mapping_context(
    actions: Sequence[Action],
    control_mapping_rows: Sequence[dict[str, str]],
) -> dict[str, Any]:
    control_ids = sorted({_clean(action.control_id) or "" for action in actions if _clean(action.control_id)})
    mappings = [dict(row) for row in control_mapping_rows if _clean(row.get("control_id")) in control_ids]
    mapped_ids = {row["control_id"] for row in mappings if _clean(row.get("control_id"))}
    return {
        "version": _ARTIFACT_VERSION,
        "artifact_type": "control_mapping_context",
        "control_ids": control_ids,
        "mapped_control_ids": sorted(mapped_ids),
        "unmapped_control_ids": [control_id for control_id in control_ids if control_id not in mapped_ids],
        "mappings": mappings,
    }


def _build_pr_payload(
    actions: Sequence[Action],
    repo_target: dict[str, str] | None,
    diff_summary: dict[str, Any],
    rollback_notes: dict[str, Any],
    control_context: dict[str, Any],
) -> dict[str, Any] | None:
    if repo_target is None:
        return None
    return {
        "version": _ARTIFACT_VERSION,
        "artifact_type": "provider_agnostic_pr_payload",
        "provider_agnostic": True,
        "repo_target": repo_target,
        "title": _pr_title(actions),
        "commit_message": _commit_message(actions),
        "body_markdown": _pr_body(actions, repo_target, diff_summary, rollback_notes, control_context),
        "diff_metadata": diff_summary,
        "rollback_notes": rollback_notes,
    }


def _automation_files(
    diff_summary: dict[str, Any],
    rollback_notes: dict[str, Any],
    control_context: dict[str, Any],
    pr_payload: dict[str, Any] | None,
) -> list[dict[str, str]]:
    files = [
        {"path": _DIFF_SUMMARY_PATH, "content": _json(diff_summary) + "\n"},
        {"path": _ROLLBACK_NOTES_PATH, "content": _rollback_markdown(rollback_notes)},
        {"path": _CONTROL_MAPPING_PATH, "content": _json(control_context) + "\n"},
    ]
    if pr_payload is not None:
        files.append({"path": _PR_PAYLOAD_PATH, "content": _json(pr_payload) + "\n"})
    return files


def _merge_metadata(
    bundle: dict[str, Any],
    diff_summary: dict[str, Any],
    repo_target: dict[str, str] | None,
    pr_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    existing = bundle.get("metadata")
    metadata = dict(existing) if isinstance(existing, dict) else {}
    metadata["diff_fingerprint_sha256"] = diff_summary["fingerprint_sha256"]
    metadata["repo_target_configured"] = repo_target is not None
    metadata["automation_file_count"] = 4 if pr_payload is not None else 3
    if repo_target is not None:
        metadata["repo_repository"] = repo_target["repository"]
        metadata["repo_base_branch"] = repo_target["base_branch"]
        metadata["repo_head_branch"] = repo_target["head_branch"]
        if repo_target.get("root_path"):
            metadata["repo_root_path"] = repo_target["root_path"]
    return metadata


def _artifact_payload(
    diff_summary: dict[str, Any],
    rollback_notes: dict[str, Any],
    control_context: dict[str, Any],
    repo_target: dict[str, str] | None,
    pr_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    artifacts = {
        "diff_summary": diff_summary,
        "rollback_notes": rollback_notes,
        "control_mapping_context": control_context,
    }
    if repo_target is not None:
        artifacts["repo_target"] = repo_target
    if pr_payload is not None:
        artifacts["pr_payload"] = pr_payload
    return artifacts


def _repo_path(path: str, repo_target: dict[str, str] | None) -> str:
    root_path = repo_target.get("root_path") if repo_target else None
    return posixpath.join(root_path, path) if root_path else path


def _default_head_branch(actions: Sequence[Action], run_id: str) -> str:
    first = actions[0] if actions else None
    token = _slug(_clean(getattr(first, "control_id", None)) or _clean(getattr(first, "action_type", None)) or "bundle")
    return f"autopilot/remediation/{token}-{run_id[:8].lower()}"


def _pr_title(actions: Sequence[Action]) -> str:
    if len(actions) == 1:
        action = actions[0]
        label = _clean(action.control_id) or action.action_type
        return f"Apply AWS Security Autopilot remediation for {label}"
    return f"Apply AWS Security Autopilot remediation bundle ({len(actions)} actions)"


def _commit_message(actions: Sequence[Action]) -> str:
    return _pr_title(actions)


def _pr_body(
    actions: Sequence[Action],
    repo_target: dict[str, str],
    diff_summary: dict[str, Any],
    rollback_notes: dict[str, Any],
    control_context: dict[str, Any],
) -> str:
    sections = [
        "## Summary",
        _summary_block(actions, repo_target),
        "## Generated diff",
        _diff_block(diff_summary),
        "## Rollback",
        _rollback_block(rollback_notes),
        "## Control mapping context",
        _control_mapping_block(control_context),
    ]
    return "\n\n".join(section for section in sections if section)


def _summary_block(actions: Sequence[Action], repo_target: dict[str, str]) -> str:
    lines = [
        f"- Repository: `{repo_target['repository']}`",
        f"- Base branch: `{repo_target['base_branch']}`",
        f"- Head branch: `{repo_target['head_branch']}`",
    ]
    root_path = repo_target.get("root_path")
    if root_path:
        lines.append(f"- Repo root path: `{root_path}`")
    lines.extend(_action_summary_lines(actions))
    return "\n".join(lines)


def _action_summary_lines(actions: Sequence[Action]) -> list[str]:
    lines: list[str] = []
    for action in actions[:10]:
        label = _clean(action.control_id) or action.action_type
        lines.append(f"- Action: `{label}` · `{action.account_id}` · `{_scope_label(action)}`")
    return lines


def _diff_block(diff_summary: dict[str, Any]) -> str:
    lines = [
        f"- Fingerprint: `{diff_summary['fingerprint_sha256']}`",
        f"- File count: `{diff_summary['file_count']}`",
    ]
    for summary in diff_summary.get("summary_lines", [])[:10]:
        lines.append(f"- {summary}")
    return "\n".join(lines)


def _rollback_block(rollback_notes: dict[str, Any]) -> str:
    lines = [f"- Recommended path: {rollback_notes['recommended_path']}"]
    for entry in rollback_notes.get("entries", [])[:10]:
        title = entry.get("title") or entry.get("action_type") or "action"
        command = entry.get("rollback_command") or "Revert through version control."
        lines.append(f"- {title}: `{command}`")
    return "\n".join(lines)


def _control_mapping_block(control_context: dict[str, Any]) -> str:
    control_ids = control_context.get("control_ids") or []
    lines = [f"- Control IDs: {', '.join(f'`{control_id}`' for control_id in control_ids) or 'none'}"]
    for row in control_context.get("mappings", [])[:10]:
        lines.append(
            "- "
            f"`{row.get('control_id', '')}` -> `{row.get('framework_name', '')}` "
            f"`{row.get('framework_control_code', '')}`"
        )
    return "\n".join(lines)


def _rollback_markdown(rollback_notes: dict[str, Any]) -> str:
    lines = [
        "# Rollback notes",
        "",
        rollback_notes["recommended_path"],
        "",
    ]
    for entry in rollback_notes.get("entries", []):
        lines.extend(_rollback_markdown_entry(entry))
    return "\n".join(lines).rstrip() + "\n"


def _rollback_markdown_entry(entry: dict[str, Any]) -> list[str]:
    return [
        f"## {entry.get('title') or entry.get('action_type') or 'Action'}",
        f"- Action ID: `{entry.get('action_id') or ''}`",
        f"- Control ID: `{entry.get('control_id') or ''}`",
        f"- Target: `{entry.get('target_id') or ''}`",
        f"- Rollback command: `{entry.get('rollback_command') or 'Revert through version control.'}`",
        "",
    ]


def _hydrate_rollback_command(action: Action, strategy_id: str | None) -> str:
    command = _clean(get_rollback_command(action.action_type, strategy_id))
    if not command:
        return "Revert the generated infrastructure change through the same deployment path used for apply."
    for placeholder, value in _rollback_values(action).items():
        if value:
            command = command.replace(placeholder, value)
    return command


def _rollback_values(action: Action) -> dict[str, str]:
    return {
        "<ACCOUNT_ID>": _clean(action.account_id) or "",
        "<BUCKET_NAME>": _bucket_name(action),
        "<SOURCE_BUCKET>": _bucket_name(action),
        "<SECURITY_GROUP_ID>": _security_group_id(action),
        "<RECORDER_NAME>": "default",
        "<TRAIL_NAME>": _clean(action.target_id) or "default",
        "<DETECTOR_ID>": _clean(action.target_id) or "<DETECTOR_ID>",
        "<ROOT_ACCESS_KEY_ID>": "<ROOT_ACCESS_KEY_ID>",
    }


def _bucket_name(action: Action) -> str:
    target = _clean(action.target_id) or ""
    match = _S3_BUCKET_ARN_PATTERN.search(target)
    if match:
        return match.group("bucket")
    if target.startswith("arn:aws:s3:::"):
        return target.split("arn:aws:s3:::")[-1].split("/")[0].strip()
    return target if not target.startswith("s3://") else target[len("s3://"):].split("/")[0]


def _security_group_id(action: Action) -> str:
    for candidate in (_clean(action.target_id), _clean(action.resource_id)):
        if not candidate:
            continue
        match = _SECURITY_GROUP_ID_PATTERN.search(candidate)
        if match:
            return match.group(0)
    return "<SECURITY_GROUP_ID>"


def _scope_label(action: Action) -> str:
    target = _clean(action.target_id)
    if target:
        return target
    if action.region:
        return f"{action.account_id}/{action.region}"
    return action.account_id


def _summary_line(entry: dict[str, Any]) -> str:
    return (
        f"`{entry['repo_path']}` <- `{entry['bundle_path']}` "
        f"({entry['line_count']} lines, sha256:{entry['content_sha256'][:12]})"
    )


def _normalize_root_path(value: Any) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    normalized = cleaned.strip("/")
    return normalized or None


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _slug(value: str) -> str:
    lowered = value.lower().replace(" ", "-")
    normalized = _BRANCH_TOKEN_PATTERN.sub("-", lowered)
    return normalized.strip("-") or "bundle"


def _line_count(content: str) -> int:
    if not content:
        return 0
    return content.count("\n") + (0 if content.endswith("\n") else 1)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)
