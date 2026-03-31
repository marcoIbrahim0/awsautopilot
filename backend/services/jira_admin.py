from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request
from urllib.parse import quote, urljoin

from backend.config import settings

JIRA_WEBHOOK_EVENTS = ("jira:issue_created", "jira:issue_updated", "jira:issue_deleted")
JIRA_CANONICAL_STATUSES = ("open", "in_progress", "resolved", "suppressed")
JIRA_HEALTH_KEY = "health"
JIRA_ASSIGNEE_ACCOUNT_MAP_KEY = "assignee_account_map"
JIRA_CANARY_ACTION_ID_KEY = "canary_action_id"
JIRA_WEBHOOK_ID_KEY = "webhook_id"
JIRA_WEBHOOK_NAME_KEY = "webhook_name"
JIRA_WEBHOOK_URL_KEY = "webhook_url"
JIRA_WEBHOOK_SECRET_KEY = "webhook_secret"
JIRA_WEBHOOK_TOKEN_KEY = "webhook_token"


class JiraAdminError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class JiraHealthSnapshot:
    status: str
    credentials_valid: bool | None = None
    project_valid: bool | None = None
    issue_type_valid: bool | None = None
    transition_map_valid: bool | None = None
    webhook_registered: bool | None = None
    signed_webhook_enabled: bool | None = None
    webhook_mode: str | None = None
    last_validated_at: str | None = None
    last_validation_error: str | None = None
    last_inbound_at: str | None = None
    last_outbound_at: str | None = None
    last_provider_error: str | None = None
    last_provider_error_at: str | None = None
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class JiraWebhookSyncResult:
    webhook_id: str
    created: bool
    rotated_secret: bool
    webhook_url: str
    details: dict[str, object] = field(default_factory=dict)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def jira_secret_json(setting) -> dict[str, object]:
    secret = getattr(setting, "secret_json", None)
    return secret if isinstance(secret, dict) else {}


def jira_config_json(setting) -> dict[str, object]:
    config = getattr(setting, "config_json", None)
    return config if isinstance(config, dict) else {}


def normalize_jira_base_url(url: str | None) -> str | None:
    value = str(url or "").strip().rstrip("/")
    if not value:
        return None
    if not value.startswith("https://"):
        raise JiraAdminError("jira_base_url_invalid", "Jira base URL must start with https://.")
    return value


def normalize_jira_config(config: dict[str, object]) -> dict[str, object]:
    normalized = dict(config)
    if "base_url" in normalized:
        base_url = normalize_jira_base_url(normalized.get("base_url"))
        if base_url:
            normalized["base_url"] = base_url
        else:
            normalized.pop("base_url", None)
    if "project_key" in normalized:
        project_key = str(normalized.get("project_key") or "").strip().upper()
        if project_key:
            normalized["project_key"] = project_key
        else:
            normalized.pop("project_key", None)
    if "issue_type" in normalized:
        issue_type = str(normalized.get("issue_type") or "").strip()
        if issue_type:
            normalized["issue_type"] = issue_type
        else:
            normalized.pop("issue_type", None)
    if "transition_map" in normalized:
        normalized["transition_map"] = normalize_transition_map(normalized.get("transition_map"))
    if JIRA_ASSIGNEE_ACCOUNT_MAP_KEY in normalized:
        normalized[JIRA_ASSIGNEE_ACCOUNT_MAP_KEY] = normalize_assignee_account_map(
            normalized.get(JIRA_ASSIGNEE_ACCOUNT_MAP_KEY)
        )
    if JIRA_CANARY_ACTION_ID_KEY in normalized:
        canary = str(normalized.get(JIRA_CANARY_ACTION_ID_KEY) or "").strip()
        if canary:
            normalized[JIRA_CANARY_ACTION_ID_KEY] = canary
        else:
            normalized.pop(JIRA_CANARY_ACTION_ID_KEY, None)
    return normalized


def normalize_transition_map(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise JiraAdminError("jira_transition_map_invalid", "Jira transition map must be an object.")
    normalized: dict[str, str] = {}
    for key, item in value.items():
        status = str(key or "").strip().lower()
        transition = str(item or "").strip()
        if not status or not transition:
            raise JiraAdminError("jira_transition_map_invalid", "Jira transition map keys and values must be non-empty.")
        normalized[status] = transition
    return normalized


def normalize_assignee_account_map(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise JiraAdminError("jira_assignee_map_invalid", "Jira assignee account map must be an object.")
    normalized: dict[str, str] = {}
    for key, item in value.items():
        owner_key = str(key or "").strip()
        account_id = str(item or "").strip()
        if not owner_key or not account_id:
            raise JiraAdminError("jira_assignee_map_invalid", "Jira assignee account map entries must be non-empty.")
        normalized[owner_key] = account_id
    return normalized


def jira_health_payload(setting) -> dict[str, object]:
    health = jira_config_json(setting).get(JIRA_HEALTH_KEY)
    return health if isinstance(health, dict) else {}


def update_jira_health(setting, payload: dict[str, object]) -> None:
    config = dict(jira_config_json(setting))
    health = dict(jira_health_payload(setting))
    health.update(payload)
    config[JIRA_HEALTH_KEY] = health
    setting.config_json = config


def build_jira_settings_health(
    setting,
    *,
    last_inbound_at: str | None,
    last_outbound_at: str | None,
    last_provider_error: str | None,
    last_provider_error_at: str | None,
) -> JiraHealthSnapshot:
    health = jira_health_payload(setting)
    return JiraHealthSnapshot(
        status=str(health.get("status") or "unknown"),
        credentials_valid=_bool_or_none(health.get("credentials_valid")),
        project_valid=_bool_or_none(health.get("project_valid")),
        issue_type_valid=_bool_or_none(health.get("issue_type_valid")),
        transition_map_valid=_bool_or_none(health.get("transition_map_valid")),
        webhook_registered=_bool_or_none(health.get("webhook_registered")),
        signed_webhook_enabled=bool(jira_secret_json(setting).get(JIRA_WEBHOOK_SECRET_KEY)),
        webhook_mode=_webhook_mode(setting),
        last_validated_at=_string_or_none(health.get("last_validated_at")),
        last_validation_error=_string_or_none(health.get("last_validation_error")),
        last_inbound_at=last_inbound_at,
        last_outbound_at=last_outbound_at,
        last_provider_error=last_provider_error,
        last_provider_error_at=last_provider_error_at,
        details=_safe_dict(health.get("details")),
    )


def build_jira_webhook_url() -> str:
    return f"{settings.API_PUBLIC_URL.rstrip('/')}/api/integrations/webhooks/jira"


def generate_jira_shared_secret() -> str:
    return secrets.token_hex(32)


def verify_jira_webhook_signature(*, body: bytes, secret: str, signature_header: str | None) -> bool:
    if not secret or not signature_header:
        return False
    method, _, signature = signature_header.partition("=")
    digest_name = method.strip().lower()
    expected = _build_hmac_signature(body=body, secret=secret, digest_name=digest_name)
    if expected is None:
        return False
    return hmac.compare_digest(signature.strip().lower(), expected)


def jira_verified_assignee_account_id(setting, *, owner_type: str | None, owner_key: str | None, existing_assignee_key: str | None) -> str | None:
    if str(owner_type or "").strip().lower() != "user":
        return None
    owner = str(owner_key or "").strip()
    if not owner:
        return None
    if existing_assignee_key and owner == str(existing_assignee_key).strip():
        return owner
    assignee_map = normalize_assignee_account_map(jira_config_json(setting).get(JIRA_ASSIGNEE_ACCOUNT_MAP_KEY))
    mapped = str(assignee_map.get(owner) or "").strip()
    return mapped or None


def validate_jira_configuration(setting) -> JiraHealthSnapshot:
    base_url = _require_text(jira_config_json(setting), "base_url", "jira_base_url_required")
    project_key = _require_text(jira_config_json(setting), "project_key", "jira_project_key_required")
    issue_type = str(jira_config_json(setting).get("issue_type") or "Task").strip()
    headers = _jira_headers(setting)
    _jira_json_request("GET", urljoin(f"{base_url}/", "rest/api/3/myself"), None, headers)
    project = _jira_json_request("GET", urljoin(f"{base_url}/", f"rest/api/3/project/{quote(project_key)}"), None, headers)
    issue_types = _jira_json_request("GET", urljoin(f"{base_url}/", "rest/api/3/issuetype"), None, headers)
    statuses = _jira_json_request("GET", urljoin(f"{base_url}/", f"rest/api/3/project/{quote(project_key)}/statuses"), None, headers)
    snapshot = _validation_snapshot(
        setting,
        project=project,
        issue_type=issue_type,
        issue_types=issue_types,
        statuses=statuses,
    )
    update_jira_health(setting, _validation_payload(snapshot))
    return snapshot


def sync_jira_webhook(setting, *, rotate_secret: bool = False) -> JiraWebhookSyncResult:
    base_url = _require_text(jira_config_json(setting), "base_url", "jira_base_url_required")
    project_key = _require_text(jira_config_json(setting), "project_key", "jira_project_key_required")
    headers = _jira_headers(setting)
    secret = _ensure_webhook_secret(setting, rotate_secret=rotate_secret)
    webhook_url = build_jira_webhook_url()
    name = _webhook_name(setting)
    payload = _webhook_payload(setting, webhook_url=webhook_url, name=name, project_key=project_key, secret=secret)
    existing = _find_existing_webhook(setting, base_url=base_url, headers=headers, webhook_url=webhook_url, name=name)
    created = existing is None
    result = _create_or_update_webhook(base_url=base_url, headers=headers, existing=existing, payload=payload)
    _persist_webhook_state(setting, result, webhook_url=webhook_url, name=name)
    update_jira_health(setting, {"status": "healthy", "webhook_registered": True, "last_validation_error": None})
    return JiraWebhookSyncResult(
        webhook_id=str(result.get("id") or ""),
        created=created,
        rotated_secret=rotate_secret,
        webhook_url=webhook_url,
        details={"is_signed": bool(result.get("isSigned")), "jql": _webhook_jql(project_key)},
    )


def _jira_headers(setting) -> dict[str, str]:
    secret = jira_secret_json(setting)
    email = _require_text(secret, "user_email", "jira_user_email_required")
    token = _require_text(secret, "api_token", "jira_api_token_required")
    basic = f"{email}:{token}".encode("utf-8")
    auth = base64.b64encode(basic).decode("ascii")
    return {"Authorization": f"Basic {auth}", "Accept": "application/json", "Content-Type": "application/json"}


def _jira_json_request(method: str, url: str, payload: dict[str, object] | None, headers: dict[str, str]) -> object:
    body = None if payload is None else json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    request = urllib.request.Request(url, method=method.upper(), data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8") if response.length != 0 else ""
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise _jira_http_error(exc) from exc
    except urllib.error.URLError as exc:
        raise JiraAdminError("jira_provider_unreachable", str(exc.reason or exc))


def _jira_http_error(error: urllib.error.HTTPError) -> JiraAdminError:
    body = error.read().decode("utf-8", errors="replace")
    code = _jira_error_code(error.code, body)
    message = body[:500] or error.reason or f"http_{error.code}"
    return JiraAdminError(code, message)


def _jira_error_code(status_code: int, body: str) -> str:
    lowered = body.lower()
    if status_code == 401:
        return "jira_invalid_auth"
    if status_code == 404:
        return "jira_resource_not_found"
    if status_code == 429:
        return "jira_rate_limited"
    if "assignee" in lowered:
        return "jira_invalid_assignee"
    if "issuetype" in lowered:
        return "jira_invalid_issue_type"
    if "project" in lowered:
        return "jira_invalid_project"
    if 500 <= status_code:
        return "jira_provider_unreachable"
    return f"jira_http_{status_code}"


def _validation_snapshot(setting, *, project: object, issue_type: str, issue_types: object, statuses: object) -> JiraHealthSnapshot:
    status_names = _status_names(statuses)
    transitions = normalize_transition_map(jira_config_json(setting).get("transition_map"))
    transition_valid = all(key in status_names for key in transitions) if transitions else True
    issue_type_valid = issue_type.lower() in _issue_type_names(issue_types)
    return JiraHealthSnapshot(
        status="healthy" if issue_type_valid and transition_valid else "warning",
        credentials_valid=True,
        project_valid=bool(project),
        issue_type_valid=issue_type_valid,
        transition_map_valid=transition_valid,
        webhook_registered=_bool_or_none(jira_health_payload(setting).get("webhook_registered")),
        signed_webhook_enabled=bool(jira_secret_json(setting).get(JIRA_WEBHOOK_SECRET_KEY)),
        webhook_mode=_webhook_mode(setting),
        last_validated_at=utcnow_iso(),
        last_validation_error=None,
        details={"project_name": _string_or_none(_safe_dict(project).get("name")), "available_statuses": sorted(status_names)},
    )


def _validation_payload(snapshot: JiraHealthSnapshot) -> dict[str, object]:
    return {
        "status": snapshot.status,
        "credentials_valid": snapshot.credentials_valid,
        "project_valid": snapshot.project_valid,
        "issue_type_valid": snapshot.issue_type_valid,
        "transition_map_valid": snapshot.transition_map_valid,
        "webhook_registered": snapshot.webhook_registered,
        "last_validated_at": snapshot.last_validated_at,
        "last_validation_error": snapshot.last_validation_error,
        "details": snapshot.details,
    }


def _issue_type_names(payload: object) -> set[str]:
    if not isinstance(payload, list):
        return set()
    return {str(item.get("name") or "").strip().lower() for item in payload if isinstance(item, dict)}


def _status_names(payload: object) -> set[str]:
    if not isinstance(payload, list):
        return set()
    values: set[str] = set()
    for item in payload:
        for status in _safe_dict(item).get("statuses") or []:
            if isinstance(status, dict):
                name = str(status.get("name") or "").strip().lower()
                if name:
                    values.add(name)
    return values


def _ensure_webhook_secret(setting, *, rotate_secret: bool) -> str:
    secret_json = dict(jira_secret_json(setting))
    secret = str(secret_json.get(JIRA_WEBHOOK_SECRET_KEY) or "").strip()
    if secret and not rotate_secret:
        return secret
    secret = generate_jira_shared_secret()
    secret_json[JIRA_WEBHOOK_SECRET_KEY] = secret
    setting.secret_json = secret_json
    return secret


def _webhook_name(setting) -> str:
    config = jira_config_json(setting)
    existing = str(config.get(JIRA_WEBHOOK_NAME_KEY) or "").strip()
    if existing:
        return existing
    return f"aws-security-autopilot-jira-{getattr(setting, 'tenant_id', 'tenant')}"


def _webhook_payload(setting, *, webhook_url: str, name: str, project_key: str, secret: str) -> dict[str, object]:
    return {
        "name": name,
        "description": "AWS Security Autopilot Jira sync webhook",
        "url": webhook_url,
        "excludeBody": False,
        "events": list(JIRA_WEBHOOK_EVENTS),
        "filters": {"issue-related-events-section": _webhook_jql(project_key)},
        "enabled": True,
        "secret": secret,
    }


def _webhook_jql(project_key: str) -> str:
    return f"project = {project_key}"


def _find_existing_webhook(setting, *, base_url: str, headers: dict[str, str], webhook_url: str, name: str) -> dict[str, object] | None:
    config = jira_config_json(setting)
    webhook_id = _string_or_none(config.get(JIRA_WEBHOOK_ID_KEY))
    if webhook_id:
        try:
            result = _jira_json_request(
                "GET",
                urljoin(f"{base_url}/", f"rest/webhooks/1.0/webhook/{quote(webhook_id)}"),
                None,
                headers,
            )
        except JiraAdminError as exc:
            if exc.code != "jira_resource_not_found":
                raise
        else:
            if isinstance(result, dict):
                return result
    result = _jira_json_request("GET", urljoin(f"{base_url}/", "rest/webhooks/1.0/webhook"), None, headers)
    if not isinstance(result, list):
        return None
    for item in result:
        candidate = _safe_dict(item)
        if candidate.get("url") == webhook_url or candidate.get("name") == name:
            return candidate
    return None


def _create_or_update_webhook(*, base_url: str, headers: dict[str, str], existing: dict[str, object] | None, payload: dict[str, object]) -> dict[str, object]:
    if existing is None:
        result = _jira_json_request("POST", urljoin(f"{base_url}/", "rest/webhooks/1.0/webhook"), payload, headers)
        return _safe_dict(result)
    webhook_id = _require_text(existing, "id", "jira_webhook_missing")
    result = _jira_json_request(
        "PUT",
        urljoin(f"{base_url}/", f"rest/webhooks/1.0/webhook/{quote(webhook_id)}"),
        payload,
        headers,
    )
    merged = dict(existing)
    merged.update(_safe_dict(result))
    merged["id"] = webhook_id
    return merged


def _persist_webhook_state(setting, webhook: dict[str, object], *, webhook_url: str, name: str) -> None:
    config = dict(jira_config_json(setting))
    config[JIRA_WEBHOOK_ID_KEY] = _string_or_none(webhook.get("id"))
    config[JIRA_WEBHOOK_NAME_KEY] = name
    config[JIRA_WEBHOOK_URL_KEY] = webhook_url
    config = normalize_jira_config(config)
    setting.config_json = config


def _require_text(source: dict[str, object], key: str, code: str) -> str:
    value = str(source.get(key) or "").strip()
    if value:
        return value
    raise JiraAdminError(code, f"Missing Jira field '{key}'.")


def _safe_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _webhook_mode(setting) -> str:
    secret = jira_secret_json(setting)
    if secret.get(JIRA_WEBHOOK_SECRET_KEY):
        return "signed_admin_webhook"
    if secret.get(JIRA_WEBHOOK_TOKEN_KEY):
        return "shared_token"
    return "unconfigured"


def _build_hmac_signature(*, body: bytes, secret: str, digest_name: str) -> str | None:
    try:
        digestmod = getattr(hashlib, digest_name)
    except AttributeError:
        return None
    return hmac.new(secret.encode("utf-8"), body, digestmod).hexdigest().lower()
