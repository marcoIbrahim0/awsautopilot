from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import urllib.error
import urllib.request
from urllib.parse import urljoin


PROVIDER_JIRA = "jira"
PROVIDER_SERVICENOW = "servicenow"
PROVIDER_SLACK = "slack"
SUPPORTED_INTEGRATION_PROVIDERS = {PROVIDER_JIRA, PROVIDER_SERVICENOW, PROVIDER_SLACK}
_RETRYABLE_HTTP_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
_RETRYABLE_SLACK_ERRORS = {"internal_error", "fatal_error", "ratelimited"}


class IntegrationAdapterError(RuntimeError):
    """Provider adapter error with retry classification."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class IntegrationAdapterUnavailableError(IntegrationAdapterError):
    """Raised when a provider temporarily rejects or delays a request."""

    def __init__(self, code: str, message: str):
        super().__init__(code, message, retryable=True)


class IntegrationAdapterValidationError(IntegrationAdapterError):
    """Raised when integration configuration or payload is invalid."""

    def __init__(self, code: str, message: str):
        super().__init__(code, message, retryable=False)


@dataclass(frozen=True)
class ProviderSyncResult:
    external_id: str
    external_key: str | None = None
    external_url: str | None = None
    external_status: str | None = None
    external_assignee_key: str | None = None
    external_assignee_label: str | None = None
    metadata: dict[str, object] | None = None


def sync_provider_item(*, provider: str, config: dict, secret: dict, payload: dict) -> ProviderSyncResult:
    normalized = str(provider or "").strip().lower()
    if normalized == PROVIDER_JIRA:
        return _sync_jira(config=config, secret=secret, payload=payload)
    if normalized == PROVIDER_SERVICENOW:
        return _sync_servicenow(config=config, secret=secret, payload=payload)
    if normalized == PROVIDER_SLACK:
        return _sync_slack(config=config, secret=secret, payload=payload)
    raise IntegrationAdapterValidationError("unsupported_provider", f"Unsupported provider '{provider}'.")


def _require_text(source: dict, key: str, *, code: str) -> str:
    value = str(source.get(key) or "").strip()
    if value:
        return value
    raise IntegrationAdapterValidationError(code, f"Missing required field '{key}'.")


def _bearer_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _basic_headers(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _merge_headers(*parts: dict[str, str]) -> dict[str, str]:
    merged = {"Content-Type": "application/json"}
    for part in parts:
        merged.update(part)
    return merged


def _json_request(*, method: str, url: str, payload: dict | None, headers: dict[str, str]) -> dict:
    body = None if payload is None else json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read().decode("utf-8") if response.length != 0 else ""
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        _raise_http_error(error)
    except urllib.error.URLError as error:
        raise IntegrationAdapterUnavailableError("provider_unreachable", str(error.reason or error)) from error


def _raise_http_error(error: urllib.error.HTTPError) -> None:
    body = error.read().decode("utf-8", errors="replace")
    message = body[:500] or error.reason or f"http_{error.code}"
    if error.code in _RETRYABLE_HTTP_CODES:
        raise IntegrationAdapterUnavailableError(f"http_{error.code}", message) from error
    raise IntegrationAdapterValidationError(f"http_{error.code}", message) from error


def _sync_jira(*, config: dict, secret: dict, payload: dict) -> ProviderSyncResult:
    base_url = _require_text(config, "base_url", code="jira_base_url_required")
    user_email = _require_text(secret, "user_email", code="jira_user_email_required")
    api_token = _require_text(secret, "api_token", code="jira_api_token_required")
    headers = _merge_headers(_basic_headers(user_email, api_token), {"Accept": "application/json"})
    operation = _require_text(payload, "operation", code="jira_operation_required")
    if operation == "create":
        response = _json_request(
            method="POST",
            url=urljoin(f"{base_url.rstrip('/')}/", "rest/api/3/issue"),
            payload=_jira_create_payload(config=config, payload=payload),
            headers=headers,
        )
        issue_id = str(response.get("id") or "")
        issue_key = str(response.get("key") or issue_id)
        _maybe_apply_jira_transition(
            base_url=base_url,
            issue_key=issue_key,
            status_value=str(payload.get("external_status") or ""),
            transition_map=_string_map(config.get("transition_map")),
            headers=headers,
        )
        return ProviderSyncResult(
            external_id=issue_id or issue_key,
            external_key=issue_key or issue_id,
            external_url=_jira_issue_url(base_url, issue_key or issue_id),
            external_status=str(payload.get("external_status") or "") or None,
            external_assignee_key=str(payload.get("external_assignee_key") or "") or None,
            external_assignee_label=str(payload.get("external_assignee_label") or "") or None,
        )
    issue_id = _require_text(payload, "external_key", code="jira_external_key_required")
    _json_request(
        method="PUT",
        url=urljoin(f"{base_url.rstrip('/')}/", f"rest/api/3/issue/{issue_id}"),
        payload=_jira_update_payload(payload=payload),
        headers=headers,
    )
    _maybe_apply_jira_transition(
        base_url=base_url,
        issue_key=issue_id,
        status_value=str(payload.get("external_status") or ""),
        transition_map=_string_map(config.get("transition_map")),
        headers=headers,
    )
    return ProviderSyncResult(
        external_id=str(payload.get("external_id") or issue_id),
        external_key=issue_id,
        external_url=_jira_issue_url(base_url, issue_id),
        external_status=str(payload.get("external_status") or "") or None,
        external_assignee_key=str(payload.get("external_assignee_key") or "") or None,
        external_assignee_label=str(payload.get("external_assignee_label") or "") or None,
    )


def _jira_create_payload(*, config: dict, payload: dict) -> dict:
    fields = {
        "project": {"key": _require_text(config, "project_key", code="jira_project_key_required")},
        "issuetype": {"name": str(config.get("issue_type") or "Task")},
        "summary": str(payload.get("title") or "AWS Security Autopilot action"),
        "description": _jira_description_doc(payload=payload),
    }
    assignee = _jira_assignee_field(payload=payload)
    if assignee is not None:
        fields["assignee"] = assignee
    return {"fields": fields}


def _jira_update_payload(*, payload: dict) -> dict:
    fields = {
        "summary": str(payload.get("title") or "AWS Security Autopilot action"),
        "description": _jira_description_doc(payload=payload),
    }
    assignee = _jira_assignee_field(payload=payload)
    if assignee is not None:
        fields["assignee"] = assignee
    return {"fields": fields}


def _jira_description_doc(*, payload: dict) -> dict:
    text = str(payload.get("description") or payload.get("title") or "").strip()
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text or "AWS Security Autopilot action"}],
            }
        ],
    }


def _jira_assignee_field(*, payload: dict) -> dict[str, str] | None:
    assignee_key = str(payload.get("external_assignee_key") or "").strip()
    if not assignee_key or assignee_key.lower() == "unassigned":
        return None
    return {"accountId": assignee_key}


def _jira_issue_url(base_url: str, issue_key: str) -> str:
    return urljoin(f"{base_url.rstrip('/')}/", f"browse/{issue_key}")


def _maybe_apply_jira_transition(
    *,
    base_url: str,
    issue_key: str,
    status_value: str,
    transition_map: dict[str, str],
    headers: dict[str, str],
) -> None:
    transition_id = transition_map.get(status_value.strip().lower())
    if not transition_id:
        return
    _json_request(
        method="POST",
        url=urljoin(f"{base_url.rstrip('/')}/", f"rest/api/3/issue/{issue_key}/transitions"),
        payload={"transition": {"id": transition_id}},
        headers=headers,
    )


def _sync_servicenow(*, config: dict, secret: dict, payload: dict) -> ProviderSyncResult:
    base_url = _require_text(config, "base_url", code="servicenow_base_url_required")
    table = _require_text(config, "table", code="servicenow_table_required")
    username = _require_text(secret, "username", code="servicenow_username_required")
    password = _require_text(secret, "password", code="servicenow_password_required")
    headers = _merge_headers(_basic_headers(username, password), {"Accept": "application/json"})
    method = "POST" if str(payload.get("operation") or "") == "create" else "PATCH"
    record_path = "" if method == "POST" else f"/{_require_text(payload, 'external_id', code='servicenow_external_id_required')}"
    response = _json_request(
        method=method,
        url=urljoin(f"{base_url.rstrip('/')}/", f"api/now/table/{table}{record_path}"),
        payload=_servicenow_payload(payload=payload),
        headers=headers,
    )
    result = response.get("result") if isinstance(response.get("result"), dict) else response
    external_id = str(result.get("sys_id") or payload.get("external_id") or "")
    external_key = str(result.get("number") or external_id)
    return ProviderSyncResult(
        external_id=external_id or external_key,
        external_key=external_key or external_id,
        external_url=_servicenow_record_url(base_url, table, external_id or external_key),
        external_status=str(result.get("state") or payload.get("external_status") or "") or None,
        external_assignee_key=str(result.get("assigned_to") or payload.get("external_assignee_key") or "") or None,
        external_assignee_label=str(payload.get("external_assignee_label") or "") or None,
    )


def _servicenow_payload(*, payload: dict) -> dict:
    body = {
        "short_description": str(payload.get("title") or "AWS Security Autopilot action"),
        "description": str(payload.get("description") or payload.get("title") or ""),
    }
    status_value = str(payload.get("external_status") or "").strip()
    if status_value:
        body["state"] = status_value
    assignee_key = str(payload.get("external_assignee_key") or "").strip()
    if assignee_key:
        body["assigned_to"] = assignee_key
    return body


def _servicenow_record_url(base_url: str, table: str, external_id: str) -> str:
    return urljoin(f"{base_url.rstrip('/')}/", f"nav_to.do?uri={table}.do?sys_id={external_id}")


def _sync_slack(*, config: dict, secret: dict, payload: dict) -> ProviderSyncResult:
    bot_token = _require_text(secret, "bot_token", code="slack_bot_token_required")
    api_base_url = str(config.get("api_base_url") or "https://slack.com/api").rstrip("/")
    headers = _merge_headers(_bearer_headers(bot_token))
    if str(payload.get("operation") or "") == "create":
        response = _json_request(
            method="POST",
            url=f"{api_base_url}/chat.postMessage",
            payload=_slack_create_payload(config=config, payload=payload),
            headers=headers,
        )
    else:
        response = _json_request(
            method="POST",
            url=f"{api_base_url}/chat.update",
            payload=_slack_update_payload(payload=payload),
            headers=headers,
        )
    _raise_slack_error_if_needed(response)
    channel = str(response.get("channel") or payload.get("channel_id") or "")
    ts = str(response.get("ts") or payload.get("message_ts") or "")
    external_id = f"{channel}:{ts}" if channel and ts else str(payload.get("external_id") or ts)
    return ProviderSyncResult(
        external_id=external_id,
        external_key=ts or external_id,
        external_status=str(payload.get("external_status") or "") or None,
        external_assignee_key=str(payload.get("external_assignee_key") or "") or None,
        external_assignee_label=str(payload.get("external_assignee_label") or "") or None,
        metadata={"channel": channel, "message_ts": ts},
    )


def _slack_create_payload(*, config: dict, payload: dict) -> dict:
    channel_id = _require_text(config, "channel_id", code="slack_channel_id_required")
    text = _slack_text(payload)
    return {
        "channel": channel_id,
        "text": text,
        "metadata": {"event_type": "aws_security_autopilot_action", "event_payload": _slack_metadata(payload)},
    }


def _slack_update_payload(*, payload: dict) -> dict:
    channel_id = _require_text(payload, "channel_id", code="slack_channel_id_required")
    message_ts = _require_text(payload, "message_ts", code="slack_message_ts_required")
    return {
        "channel": channel_id,
        "ts": message_ts,
        "text": _slack_text(payload),
        "metadata": {"event_type": "aws_security_autopilot_action", "event_payload": _slack_metadata(payload)},
    }


def _slack_text(payload: dict) -> str:
    title = str(payload.get("title") or "AWS Security Autopilot action")
    status_value = str(payload.get("external_status") or "open")
    assignee = str(payload.get("external_assignee_label") or payload.get("external_assignee_key") or "Unassigned")
    return f"{title}\nStatus: {status_value}\nAssignee: {assignee}"


def _slack_metadata(payload: dict) -> dict[str, str]:
    return {
        "action_id": str(payload.get("action_id") or ""),
        "status": str(payload.get("external_status") or ""),
        "assignee_key": str(payload.get("external_assignee_key") or ""),
        "assignee_label": str(payload.get("external_assignee_label") or ""),
    }


def _raise_slack_error_if_needed(response: dict) -> None:
    if bool(response.get("ok")):
        return
    code = str(response.get("error") or "slack_request_failed")
    if code in _RETRYABLE_SLACK_ERRORS:
        raise IntegrationAdapterUnavailableError(code, code)
    raise IntegrationAdapterValidationError(code, code)


def _string_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key).strip().lower(): str(inner).strip() for key, inner in value.items() if str(inner).strip()}
