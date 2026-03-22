from __future__ import annotations

import json
from pathlib import Path

from backend.services.trust_package_artifacts import (
    REDACTED_EXTERNAL_ID,
    build_sanitized_assume_role_events,
    redact_external_id,
    render_read_role_documents,
    render_write_role_documents,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
READ_TEMPLATE = PROJECT_ROOT / "infrastructure/cloudformation/read-role-template.yaml"
WRITE_TEMPLATE = PROJECT_ROOT / "infrastructure/cloudformation/write-role-template.yaml"
EXECUTION_ROLE_ARNS = (
    "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-api,"
    "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-worker"
)


def test_render_read_role_documents_split_session_audit_actions() -> None:
    docs = render_read_role_documents(
        READ_TEMPLATE,
        saas_account_id="029037611564",
        external_id="ext-123",
        saas_execution_role_arns=EXECUTION_ROLE_ARNS,
    )

    statements = docs["trust_policy"]["Statement"]
    assume_statement, session_statement = statements

    assert docs["template_version"] == "v1.5.9"
    assert assume_statement["Action"] == "sts:AssumeRole"
    assert assume_statement["Condition"]["StringEquals"]["sts:ExternalId"] == "ext-123"
    assert set(session_statement["Action"]) == {"sts:SetSourceIdentity", "sts:TagSession"}
    assert "StringEquals" not in session_statement.get("Condition", {})
    read_actions = {
        action
        for statement in docs["identity_policy"]["Statement"]
        for action in statement["Action"]
    }
    assert "iam:GetAccountSummaryReport" not in read_actions


def test_render_write_role_documents_split_session_audit_actions() -> None:
    docs = render_write_role_documents(
        WRITE_TEMPLATE,
        saas_account_id="029037611564",
        external_id="ext-123",
        saas_execution_role_arns=EXECUTION_ROLE_ARNS,
    )

    statements = docs["trust_policy"]["Statement"]
    assume_statement, session_statement = statements

    assert docs["template_version"] == "v1.4.7"
    assert assume_statement["Action"] == "sts:AssumeRole"
    assert assume_statement["Condition"]["StringEquals"]["sts:ExternalId"] == "ext-123"
    assert set(session_statement["Action"]) == {"sts:SetSourceIdentity", "sts:TagSession"}
    assert "StringEquals" not in session_statement.get("Condition", {})


def test_redact_external_id_replaces_sensitive_value() -> None:
    policy = {
        "Statement": [
            {"Condition": {"StringEquals": {"sts:ExternalId": "ext-real"}}},
            {"Condition": {"ArnEquals": {"aws:PrincipalArn": "arn:aws:iam::1:role/test"}}},
        ]
    }

    assert redact_external_id(policy) == {
        "Statement": [
            {"Condition": {"StringEquals": {"sts:ExternalId": REDACTED_EXTERNAL_ID}}},
            {"Condition": {"ArnEquals": {"aws:PrincipalArn": "arn:aws:iam::1:role/test"}}},
        ]
    }


def test_build_sanitized_assume_role_events_redacts_credentials() -> None:
    raw_event = {
        "EventId": "evt-1",
        "EventTime": "2026-03-20T02:10:50Z",
        "CloudTrailEvent": json.dumps(
            {
                "awsRegion": "eu-north-1",
                "recipientAccountId": "029037611564",
                "sourceIPAddress": "13.60.52.222",
                "userAgent": "Boto3/1.42.72",
                "requestParameters": {
                    "roleArn": "arn:aws:iam::696505809372:role/SecurityAutopilotReadRole",
                    "roleSessionName": "security-autopilot-dev-api",
                    "externalId": "ext-real",
                },
                "responseElements": {
                    "credentials": {
                        "accessKeyId": "ASIA...",
                        "sessionToken": "token",
                    }
                },
                "userIdentity": {
                    "type": "AssumedRole",
                    "arn": "arn:aws:sts::029037611564:assumed-role/security-autopilot-dev-lambda-api/api",
                    "principalId": "principal",
                    "accessKeyId": "ASIA...",
                    "sessionContext": {
                        "sessionIssuer": {
                            "arn": "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-api",
                            "userName": "security-autopilot-dev-lambda-api",
                        }
                    },
                },
            }
        ),
    }

    sanitized = build_sanitized_assume_role_events(
        [raw_event],
        role_arn="arn:aws:iam::696505809372:role/SecurityAutopilotReadRole",
    )

    assert sanitized == [
        {
            "event_id": "evt-1",
            "event_time": "2026-03-20T02:10:50Z",
            "aws_region": "eu-north-1",
            "recipient_account_id": "029037611564",
            "source_ip_address": "13.60.52.222",
            "user_agent": "Boto3/1.42.72",
            "error_code": None,
            "error_message": None,
            "request_parameters": {
                "role_arn": "arn:aws:iam::696505809372:role/SecurityAutopilotReadRole",
                "role_session_name": "security-autopilot-dev-api",
            },
            "user_identity": {
                "type": "AssumedRole",
                "arn": "arn:aws:sts::029037611564:assumed-role/security-autopilot-dev-lambda-api/api",
                "principal_id": "principal",
                "session_issuer_arn": "arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-api",
                "session_issuer_user_name": "security-autopilot-dev-lambda-api",
            },
        }
    ]
