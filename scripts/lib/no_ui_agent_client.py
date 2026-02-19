from __future__ import annotations

import json
import ssl
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SECRET_KEYS = {
    "access_token",
    "password",
    "authorization",
    "token",
    "control_plane_token",
    "csrf",
}


@dataclass
class ApiError(Exception):
    message: str
    status_code: int | None = None
    transient: bool = False
    payload: Any = None

    def __str__(self) -> str:
        return self.message


class SaaSApiClient:
    def __init__(
        self,
        api_base: str,
        timeout_sec: int = 30,
        retries: int = 3,
        retry_backoff_sec: float = 1.0,
    ):
        self.api_base = api_base.rstrip("/")
        self.timeout_sec = timeout_sec
        self.retries = max(0, int(retries))
        self.retry_backoff_sec = max(0.1, float(retry_backoff_sec))
        self.access_token: str | None = None
        self.transcript: list[dict[str, Any]] = []
        self.ssl_context = _build_ssl_context()

    def set_access_token(self, token: str) -> None:
        self.access_token = token

    def get_transcript(self) -> list[dict[str, Any]]:
        return list(self.transcript)

    def login(self, email: str, password: str) -> dict[str, Any]:
        payload = {"email": email, "password": password}
        response = self._request_json("POST", "/api/auth/login", body=payload, include_auth=False)
        token = str(response.get("access_token") or "").strip()
        if not token:
            raise ApiError("Login succeeded but access_token missing", status_code=500)
        self.set_access_token(token)
        return response

    def get_me(self) -> dict[str, Any]:
        return self._request_json("GET", "/api/auth/me")

    def check_service_readiness(self, account_id: str) -> dict[str, Any]:
        return self._request_json("POST", f"/api/aws/accounts/{account_id}/service-readiness")

    def check_control_plane_readiness(self, account_id: str, stale_after_minutes: int = 30) -> dict[str, Any]:
        query = {"stale_after_minutes": stale_after_minutes}
        return self._request_json("GET", f"/api/aws/accounts/{account_id}/control-plane-readiness", query=query)

    def trigger_ingest(self, account_id: str, regions: list[str]) -> dict[str, Any]:
        return self._request_json("POST", f"/api/aws/accounts/{account_id}/ingest", body={"regions": regions})

    def trigger_compute_actions(self, account_id: str, region: str) -> dict[str, Any]:
        body = {"account_id": account_id, "region": region}
        return self._request_json("POST", "/api/actions/compute", body=body)

    def list_findings(
        self,
        account_id: str,
        region: str | None,
        limit: int,
        offset: int,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {
            "account_id": account_id,
            "limit": int(limit),
            "offset": int(offset),
        }
        if region:
            query["region"] = region
        if status_filter:
            query["status"] = status_filter
        return self._request_json("GET", "/api/findings", query=query)

    def get_finding(self, finding_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/api/findings/{finding_id}", query={"include_raw": "false"})

    def get_remediation_options(self, action_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/api/actions/{action_id}/remediation-options")

    def create_pr_bundle_run(self, action_id: str, strategy_id: str | None = None) -> dict[str, Any]:
        body = {
            "action_id": action_id,
            "mode": "pr_only",
            "risk_acknowledged": True,
        }
        if strategy_id:
            body["strategy_id"] = strategy_id
        return self._request_json("POST", "/api/remediation-runs", body=body)

    def get_remediation_run(self, run_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"/api/remediation-runs/{run_id}")

    def resend_remediation_run(self, run_id: str) -> dict[str, Any]:
        return self._request_json("POST", f"/api/remediation-runs/{run_id}/resend")

    def download_pr_bundle_zip(self, run_id: str) -> bytes:
        path = f"/api/remediation-runs/{run_id}/pr-bundle.zip"
        return self._request_bytes("GET", path)

    def _request_json(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        include_auth: bool = True,
    ) -> dict[str, Any]:
        response_bytes = self._request_bytes(method, path, query=query, body=body, include_auth=include_auth)
        if not response_bytes:
            return {}
        decoded = json.loads(response_bytes.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ApiError(f"Expected JSON object from {path}", status_code=500)
        return decoded

    def _request_bytes(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        include_auth: bool = True,
    ) -> bytes:
        url = self._build_url(path, query)
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else None
        headers = self._build_headers(include_auth)
        attempt = 0

        while True:
            started = time.monotonic()
            try:
                request = Request(url=url, data=body_bytes, method=method, headers=headers)
                with urlopen(request, timeout=self.timeout_sec, context=self.ssl_context) as response:
                    data = response.read()
                    status_code = int(response.status)
                self._record_event(method, path, status_code, started, body, None)
                return data
            except HTTPError as exc:
                payload = self._decode_http_error_payload(exc)
                status_code = int(exc.code)
                transient = _is_transient_status(status_code)
                self._record_event(method, path, status_code, started, body, str(exc), payload)
                if transient and attempt < self.retries:
                    self._sleep_before_retry(attempt)
                    attempt += 1
                    continue
                detail = _extract_error_message(payload) or f"HTTP {status_code} on {path}"
                raise ApiError(detail, status_code=status_code, transient=transient, payload=payload) from exc
            except URLError as exc:
                self._record_event(method, path, None, started, body, str(exc), None)
                if attempt < self.retries:
                    self._sleep_before_retry(attempt)
                    attempt += 1
                    continue
                raise ApiError(f"Network error on {path}: {exc.reason}", transient=True) from exc
            except TimeoutError as exc:
                self._record_event(method, path, None, started, body, str(exc), None)
                if attempt < self.retries:
                    self._sleep_before_retry(attempt)
                    attempt += 1
                    continue
                raise ApiError(f"Timeout on {path}", transient=True) from exc

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = min(10.0, self.retry_backoff_sec * (2 ** attempt))
        time.sleep(delay)

    def _build_url(self, path: str, query: dict[str, Any] | None) -> str:
        suffix = path if path.startswith("/") else f"/{path}"
        if not query:
            return f"{self.api_base}{suffix}"
        filtered = {k: v for k, v in query.items() if v is not None and v != ""}
        return f"{self.api_base}{suffix}?{urlencode(filtered, doseq=True)}"

    def _build_headers(self, include_auth: bool) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if include_auth:
            token = str(self.access_token or "").strip()
            if not token:
                raise ApiError("Missing access token", status_code=401)
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _record_event(
        self,
        method: str,
        path: str,
        status_code: int | None,
        started: float,
        request_body: dict[str, Any] | None,
        error: str | None,
        response_payload: Any = None,
    ) -> None:
        duration_ms = int((time.monotonic() - started) * 1000)
        item = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "request_body": redact_payload(request_body) if request_body else None,
            "response_payload": redact_payload(response_payload) if response_payload else None,
            "error": error,
        }
        self.transcript.append(item)

    def _decode_http_error_payload(self, exc: HTTPError) -> Any:
        try:
            body = exc.read()
            if not body:
                return None
            return json.loads(body.decode("utf-8"))
        except Exception:
            return None


def redact_payload(payload: Any) -> Any:
    if payload is None:
        return None
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if not isinstance(payload, dict):
        return payload
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        lower_key = str(key).lower()
        if lower_key in SECRET_KEYS or "token" in lower_key or "password" in lower_key:
            redacted[str(key)] = "***"
            continue
        redacted[str(key)] = redact_payload(value)
    return redacted


def _is_transient_status(status_code: int) -> bool:
    return status_code in {408, 425, 429, 500, 502, 503, 504}


def _extract_error_message(payload: Any) -> str | None:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, dict):
            nested = detail.get("detail")
            if isinstance(nested, str):
                return nested
            error = detail.get("error")
            if isinstance(error, str):
                return error
    return None


def _build_ssl_context() -> ssl.SSLContext | None:
    """
    Build a TLS context pinned to certifi roots when available.
    Falls back to default system trust if certifi is unavailable.
    """
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()
