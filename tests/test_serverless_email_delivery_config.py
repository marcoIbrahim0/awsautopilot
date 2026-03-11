from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_serverless_template_wires_email_delivery_env_vars() -> None:
    text = _read("infrastructure/cloudformation/saas-serverless-httpapi.yaml")

    required_tokens = (
        "EmailFrom:",
        "EmailSmtpHost:",
        "EmailSmtpPort:",
        "EmailSmtpStarttls:",
        "EmailSmtpCredentialsSecretId:",
        "HasEmailSmtpCredentialsSecretId:",
        "EMAIL_FROM: !Ref EmailFrom",
        "EMAIL_SMTP_HOST: !Ref EmailSmtpHost",
        "EMAIL_SMTP_PORT: !Ref EmailSmtpPort",
        "EMAIL_SMTP_STARTTLS: !Ref EmailSmtpStarttls",
        "{{resolve:secretsmanager:${EmailSmtpCredentialsSecretId}:SecretString:user}}",
        "{{resolve:secretsmanager:${EmailSmtpCredentialsSecretId}:SecretString:password}}",
    )

    for token in required_tokens:
        assert token in text


def test_serverless_deploy_script_reads_email_delivery_inputs() -> None:
    text = _read("scripts/deploy_saas_serverless.sh")

    required_tokens = (
        "EMAIL_FROM_VALUE=",
        "EMAIL_SMTP_HOST_VALUE=",
        "EMAIL_SMTP_PORT_VALUE=",
        "EMAIL_SMTP_STARTTLS_VALUE=",
        "EMAIL_SMTP_CREDENTIALS_SECRET_ID_VALUE=",
        "EmailFrom=${EMAIL_FROM_VALUE}",
        "EmailSmtpHost=${EMAIL_SMTP_HOST_VALUE}",
        "EmailSmtpPort=${EMAIL_SMTP_PORT_VALUE}",
        "EmailSmtpStarttls=${EMAIL_SMTP_STARTTLS_VALUE}",
        "EmailSmtpCredentialsSecretId=${EMAIL_SMTP_CREDENTIALS_SECRET_ID_VALUE}",
    )

    for token in required_tokens:
        assert token in text
