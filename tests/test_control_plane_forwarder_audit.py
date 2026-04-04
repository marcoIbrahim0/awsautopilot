from __future__ import annotations

import pytest

from scripts.lib.control_plane_forwarder_audit import (
    control_plane_token_fingerprint,
    extract_connection_api_key,
    extract_connection_api_key_fingerprint,
)


def test_extract_connection_api_key_from_flat_eventbridge_secret() -> None:
    secret_payload = """
    {
      "api_key_name": "X-Control-Plane-Token",
      "api_key_value": "cptok-example-token-value"
    }
    """

    assert extract_connection_api_key(secret_payload) == "cptok-example-token-value"
    assert extract_connection_api_key_fingerprint(secret_payload) == control_plane_token_fingerprint(
        "cptok-example-token-value"
    )


def test_extract_connection_api_key_from_nested_eventbridge_secret() -> None:
    secret_payload = """
    {
      "AuthParameters": {
        "ApiKeyAuthParameters": {
          "ApiKeyName": "X-Control-Plane-Token",
          "ApiKeyValue": "cptok-nested-token-value"
        }
      }
    }
    """

    assert extract_connection_api_key(secret_payload) == "cptok-nested-token-value"


def test_extract_connection_api_key_rejects_missing_value() -> None:
    with pytest.raises(ValueError, match="does not contain an API key value"):
        extract_connection_api_key('{"api_key_name":"X-Control-Plane-Token"}')
