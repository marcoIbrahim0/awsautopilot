from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


def control_plane_token_fingerprint(token: str) -> str:
    normalized = (token or "").strip()
    if len(normalized) <= 12:
        return normalized
    return f"{normalized[:8]}...{normalized[-4:]}"


def extract_connection_api_key(secret_payload: str) -> str:
    parsed = json.loads(secret_payload)
    api_key = _find_api_key_value(parsed)
    if not api_key:
        raise ValueError("EventBridge connection secret does not contain an API key value")
    return api_key


def extract_connection_api_key_fingerprint(secret_payload: str) -> str:
    return control_plane_token_fingerprint(extract_connection_api_key(secret_payload))


def _find_api_key_value(node: Any) -> str | None:
    if isinstance(node, Mapping):
        for key in ("api_key_value", "ApiKeyValue"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        prioritized_children = (
            "AuthParameters",
            "authParameters",
            "auth_parameters",
            "ApiKeyAuthParameters",
            "apiKeyAuthParameters",
            "api_key_auth_parameters",
        )
        for key in prioritized_children:
            if key in node:
                found = _find_api_key_value(node[key])
                if found:
                    return found

        for value in node.values():
            found = _find_api_key_value(value)
            if found:
                return found

    if isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
        for item in node:
            found = _find_api_key_value(item)
            if found:
                return found

    return None
