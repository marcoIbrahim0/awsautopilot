from __future__ import annotations

import io
import json
from urllib.error import HTTPError, URLError

import scripts.lib.no_ui_agent_client as client_mod
from scripts.lib.no_ui_agent_client import ApiError, SaaSApiClient, redact_payload


def test_redact_payload_masks_secret_fields() -> None:
    payload = {
        "email": "user@example.com",
        "password": "secret",
        "access_token": "abc",
        "nested": {
            "Authorization": "Bearer 123",
            "regular": "ok",
        },
    }

    redacted = redact_payload(payload)
    assert redacted["email"] == "user@example.com"
    assert redacted["password"] == "***"
    assert redacted["access_token"] == "***"
    assert redacted["nested"]["Authorization"] == "***"
    assert redacted["nested"]["regular"] == "ok"


class _FakeResponse:
    def __init__(self, payload: bytes, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


def _http_error(code: int, payload: dict | None = None) -> HTTPError:
    fp = io.BytesIO(json.dumps(payload or {}).encode("utf-8"))
    return HTTPError(
        url="https://api.valensjewelry.com/api/test",
        code=code,
        msg=f"HTTP {code}",
        hdrs=None,
        fp=fp,
    )


def test_client_retries_transient_urlerror_then_succeeds(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_urlopen(*args, **kwargs):
        del args, kwargs
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise URLError("temporary dns error")
        return _FakeResponse(b"{}")

    monkeypatch.setattr(client_mod, "urlopen", fake_urlopen)
    monkeypatch.setattr(client_mod.time, "sleep", lambda *_: None)

    client = SaaSApiClient("https://api.valensjewelry.com", retries=3, retry_backoff_sec=0.1)
    payload = client._request_json("GET", "/api/test", include_auth=False)

    assert payload == {}
    assert attempts["count"] == 3
    assert len(client.get_transcript()) == 3


def test_client_retries_transient_http_error_then_raises(monkeypatch) -> None:
    attempts = {"count": 0}

    def fake_urlopen(*args, **kwargs):
        del args, kwargs
        attempts["count"] += 1
        raise _http_error(503, {"detail": "service unavailable"})

    monkeypatch.setattr(client_mod, "urlopen", fake_urlopen)
    monkeypatch.setattr(client_mod.time, "sleep", lambda *_: None)

    client = SaaSApiClient("https://api.valensjewelry.com", retries=2, retry_backoff_sec=0.1)

    try:
        client._request_json("GET", "/api/test", include_auth=False)
        raise AssertionError("Expected ApiError")
    except ApiError as exc:
        assert exc.transient is True
        assert exc.status_code == 503

    assert attempts["count"] == 3
