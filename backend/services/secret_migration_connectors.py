from __future__ import annotations

import base64
import subprocess
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import ClientError


_RETRYABLE_AWS_ERROR_CODES = {
    "Throttling",
    "ThrottlingException",
    "ServiceUnavailable",
    "InternalFailure",
    "InternalServerError",
    "RequestTimeout",
}


class SecretMigrationConnectorError(RuntimeError):
    """Base class for secret migration connector failures."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class SecretMigrationUnavailableError(SecretMigrationConnectorError):
    """Raised when a backend is temporarily unavailable."""

    def __init__(self, code: str, message: str):
        super().__init__(code, message, retryable=True)


class SecretMigrationValidationError(SecretMigrationConnectorError):
    """Raised when a request is invalid or unsupported."""

    def __init__(self, code: str, message: str):
        super().__init__(code, message, retryable=False)


class SecretMigrationRollbackError(SecretMigrationConnectorError):
    """Raised when rollback fails or cannot be guaranteed."""

    def __init__(self, code: str, message: str):
        super().__init__(code, message, retryable=False)


@dataclass(frozen=True)
class SourceSecretValue:
    value: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class TargetWriteReceipt:
    rollback_supported: bool
    rollback_token: dict[str, Any] | None
    target_version: str | None
    message: str


def _client_error_code(error: ClientError) -> str:
    return str(error.response.get("Error", {}).get("Code") or "ClientError")


def _as_aws_connector_error(service: str, operation: str, error: ClientError) -> SecretMigrationConnectorError:
    code = _client_error_code(error)
    normalized = f"{service}_{operation}_{code}".lower()
    if code in _RETRYABLE_AWS_ERROR_CODES:
        return SecretMigrationUnavailableError(
            normalized,
            f"{service} connector temporarily unavailable during {operation} ({code}).",
        )
    return SecretMigrationValidationError(
        normalized,
        f"{service} connector rejected {operation} ({code}).",
    )


class AwsSecretsManagerConnector:
    """Read/write connector for AWS Secrets Manager."""

    connector_name = "aws_secrets_manager"

    def __init__(self, *, session: Any, region: str):
        self._client = session.client("secretsmanager", region_name=region)

    def read_secret(self, secret_ref: str) -> SourceSecretValue:
        try:
            response = self._client.get_secret_value(SecretId=secret_ref)
        except ClientError as error:
            raise _as_aws_connector_error("secrets_manager", "read_secret", error) from error
        secret_string = response.get("SecretString")
        if isinstance(secret_string, str):
            value = secret_string
        else:
            secret_binary = response.get("SecretBinary")
            if isinstance(secret_binary, (bytes, bytearray)):
                value = bytes(secret_binary).decode("utf-8")
            elif isinstance(secret_binary, str):
                value = base64.b64decode(secret_binary).decode("utf-8")
            else:
                raise SecretMigrationValidationError(
                    "secrets_manager_read_missing_secret_value",
                    "Secrets Manager response did not contain a usable secret value.",
                )
        return SourceSecretValue(
            value=value,
            metadata={
                "version_id": response.get("VersionId"),
            },
        )

    def upsert_secret(self, secret_ref: str, value: str, *, dry_run: bool) -> TargetWriteReceipt:
        previous_exists = True
        previous_version_id: str | None = None
        try:
            previous = self._client.get_secret_value(SecretId=secret_ref)
            previous_version_id = str(previous.get("VersionId") or "") or None
        except ClientError as error:
            code = _client_error_code(error)
            if code == "ResourceNotFoundException":
                previous_exists = False
            else:
                raise _as_aws_connector_error("secrets_manager", "load_previous", error) from error

        rollback_token = {
            "secret_ref": secret_ref,
            "previous_exists": previous_exists,
            "previous_version_id": previous_version_id,
            "new_version_id": None,
        }
        if dry_run:
            return TargetWriteReceipt(
                rollback_supported=True,
                rollback_token=rollback_token,
                target_version=None,
                message="dry_run_no_write",
            )

        try:
            if previous_exists:
                response = self._client.put_secret_value(SecretId=secret_ref, SecretString=value)
            else:
                response = self._client.create_secret(Name=secret_ref, SecretString=value)
        except ClientError as error:
            raise _as_aws_connector_error("secrets_manager", "upsert_secret", error) from error

        target_version = str(response.get("VersionId") or "") or None
        rollback_token["new_version_id"] = target_version
        return TargetWriteReceipt(
            rollback_supported=True,
            rollback_token=rollback_token,
            target_version=target_version,
            message="applied",
        )

    def rollback_secret(self, secret_ref: str, rollback_token: dict[str, Any] | None) -> None:
        if not rollback_token:
            raise SecretMigrationRollbackError(
                "secrets_manager_missing_rollback_token",
                "Rollback token is required for Secrets Manager rollback.",
            )
        previous_exists = bool(rollback_token.get("previous_exists"))
        previous_version_id = str(rollback_token.get("previous_version_id") or "") or None
        new_version_id = str(rollback_token.get("new_version_id") or "") or None
        try:
            if previous_exists:
                if not previous_version_id or not new_version_id:
                    raise SecretMigrationRollbackError(
                        "secrets_manager_incomplete_rollback_token",
                        "Rollback token is incomplete for Secrets Manager version rollback.",
                    )
                self._client.update_secret_version_stage(
                    SecretId=secret_ref,
                    VersionStage="AWSCURRENT",
                    MoveToVersionId=previous_version_id,
                    RemoveFromVersionId=new_version_id,
                )
                return
            self._client.delete_secret(SecretId=secret_ref, ForceDeleteWithoutRecovery=True)
        except SecretMigrationRollbackError:
            raise
        except ClientError as error:
            raise SecretMigrationRollbackError(
                f"secrets_manager_rollback_{_client_error_code(error).lower()}",
                "Secrets Manager rollback failed.",
            ) from error


class AwsSsmParameterStoreConnector:
    """Read/write connector for SSM Parameter Store."""

    connector_name = "aws_ssm_parameter_store"

    def __init__(self, *, session: Any, region: str, default_parameter_type: str = "SecureString"):
        self._client = session.client("ssm", region_name=region)
        self._default_parameter_type = default_parameter_type

    def read_secret(self, parameter_ref: str) -> SourceSecretValue:
        try:
            response = self._client.get_parameter(Name=parameter_ref, WithDecryption=True)
        except ClientError as error:
            raise _as_aws_connector_error("ssm_parameter_store", "read_secret", error) from error
        parameter = response.get("Parameter") or {}
        value = str(parameter.get("Value") or "")
        return SourceSecretValue(
            value=value,
            metadata={"version": parameter.get("Version")},
        )

    def upsert_secret(
        self,
        parameter_ref: str,
        value: str,
        *,
        dry_run: bool,
        parameter_type: str | None = None,
    ) -> TargetWriteReceipt:
        previous_exists = True
        previous_version: int | None = None
        try:
            previous = self._client.get_parameter(Name=parameter_ref, WithDecryption=True)
            parameter = previous.get("Parameter") or {}
            previous_version = int(parameter.get("Version") or 0) or None
        except ClientError as error:
            code = _client_error_code(error)
            if code == "ParameterNotFound":
                previous_exists = False
            else:
                raise _as_aws_connector_error("ssm_parameter_store", "load_previous", error) from error

        rollback_token = {
            "parameter_ref": parameter_ref,
            "previous_exists": previous_exists,
            "previous_version": previous_version,
            "new_version": None,
        }
        if dry_run:
            return TargetWriteReceipt(
                rollback_supported=True,
                rollback_token=rollback_token,
                target_version=None,
                message="dry_run_no_write",
            )

        try:
            response = self._client.put_parameter(
                Name=parameter_ref,
                Value=value,
                Type=(parameter_type or self._default_parameter_type),
                Overwrite=True,
            )
        except ClientError as error:
            raise _as_aws_connector_error("ssm_parameter_store", "upsert_secret", error) from error
        version = int(response.get("Version") or 0) or None
        rollback_token["new_version"] = version
        return TargetWriteReceipt(
            rollback_supported=True,
            rollback_token=rollback_token,
            target_version=str(version) if version else None,
            message="applied",
        )

    def rollback_secret(self, parameter_ref: str, rollback_token: dict[str, Any] | None) -> None:
        if not rollback_token:
            raise SecretMigrationRollbackError(
                "ssm_parameter_store_missing_rollback_token",
                "Rollback token is required for SSM Parameter Store rollback.",
            )
        previous_exists = bool(rollback_token.get("previous_exists"))
        previous_version = rollback_token.get("previous_version")
        try:
            if previous_exists:
                history = self._client.get_parameter_history(Name=parameter_ref, WithDecryption=True)
                history_items = history.get("Parameters") or []
                previous_item = next(
                    (item for item in history_items if int(item.get("Version") or 0) == int(previous_version or 0)),
                    None,
                )
                if not previous_item:
                    raise SecretMigrationRollbackError(
                        "ssm_parameter_store_previous_version_missing",
                        "Previous SSM parameter version was not found during rollback.",
                    )
                previous_value = str(previous_item.get("Value") or "")
                previous_type = str(previous_item.get("Type") or self._default_parameter_type)
                self._client.put_parameter(
                    Name=parameter_ref,
                    Value=previous_value,
                    Type=previous_type,
                    Overwrite=True,
                )
                return
            self._client.delete_parameter(Name=parameter_ref)
        except SecretMigrationRollbackError:
            raise
        except ClientError as error:
            raise SecretMigrationRollbackError(
                f"ssm_parameter_store_rollback_{_client_error_code(error).lower()}",
                "SSM Parameter Store rollback failed.",
            ) from error


class GithubActionsConnector:
    """Target connector for GitHub Actions repository secrets via `gh` CLI."""

    connector_name = "github_actions"

    def __init__(self, *, repo: str, gh_bin: str = "gh"):
        normalized_repo = repo.strip()
        if not normalized_repo:
            raise SecretMigrationValidationError(
                "github_actions_repo_required",
                "GitHub Actions connector requires a repository identifier.",
            )
        self._repo = normalized_repo
        self._gh_bin = gh_bin.strip() or "gh"

    def read_secret(self, secret_ref: str) -> SourceSecretValue:
        raise SecretMigrationValidationError(
            "github_actions_read_not_supported",
            "GitHub Actions secrets are write-only and cannot be used as a source connector.",
        )

    def upsert_secret(self, secret_ref: str, value: str, *, dry_run: bool) -> TargetWriteReceipt:
        normalized_ref = secret_ref.strip()
        if not normalized_ref:
            raise SecretMigrationValidationError(
                "github_actions_secret_ref_required",
                "GitHub Actions secret reference is required.",
            )
        previous_exists = self._secret_exists(normalized_ref)
        rollback_token = {
            "repo": self._repo,
            "secret_ref": normalized_ref,
            "previous_exists": previous_exists,
        }
        if previous_exists:
            raise SecretMigrationValidationError(
                "github_actions_existing_secret_rollback_not_supported",
                "GitHub Actions connector cannot guarantee rollback for existing secrets.",
            )
        if dry_run:
            return TargetWriteReceipt(
                rollback_supported=True,
                rollback_token=rollback_token,
                target_version=None,
                message="dry_run_no_write",
            )
        completed = self._run_gh(
            [self._gh_bin, "secret", "set", normalized_ref, "--repo", self._repo],
            input_text=value,
        )
        if completed.returncode != 0:
            raise SecretMigrationUnavailableError(
                "github_actions_write_failed",
                "GitHub Actions secret write failed.",
            )
        return TargetWriteReceipt(
            rollback_supported=True,
            rollback_token=rollback_token,
            target_version=None,
            message="applied",
        )

    def rollback_secret(self, secret_ref: str, rollback_token: dict[str, Any] | None) -> None:
        if not rollback_token:
            raise SecretMigrationRollbackError(
                "github_actions_missing_rollback_token",
                "Rollback token is required for GitHub Actions rollback.",
            )
        if bool(rollback_token.get("previous_exists")):
            raise SecretMigrationRollbackError(
                "github_actions_existing_secret_rollback_not_supported",
                "GitHub Actions rollback is unsupported for pre-existing secret values.",
            )
        completed = self._run_gh(
            [self._gh_bin, "secret", "delete", secret_ref, "--repo", self._repo],
            input_text=None,
        )
        if completed.returncode != 0:
            raise SecretMigrationRollbackError(
                "github_actions_delete_failed",
                "GitHub Actions rollback delete failed.",
            )

    def _secret_exists(self, secret_ref: str) -> bool:
        completed = self._run_gh([self._gh_bin, "secret", "list", "--repo", self._repo], input_text=None)
        if completed.returncode != 0:
            raise SecretMigrationUnavailableError(
                "github_actions_list_failed",
                "GitHub Actions secret listing failed.",
            )
        names: set[str] = set()
        for line in (completed.stdout or "").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.lower().startswith("name"):
                continue
            names.add(stripped.split()[0])
        return secret_ref in names

    def _run_gh(self, args: list[str], *, input_text: str | None) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                args,
                input=input_text,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise SecretMigrationUnavailableError(
                "github_actions_cli_not_found",
                "GitHub CLI binary is not available for connector execution.",
            ) from error
