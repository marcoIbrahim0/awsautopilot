from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

from backend.services.secret_migration_connectors import (
    AwsSecretsManagerConnector,
    AwsSsmParameterStoreConnector,
    GithubActionsConnector,
    SecretMigrationUnavailableError,
    SecretMigrationValidationError,
)


def _client_error(code: str, operation: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, operation)


@dataclass
class _SecretState:
    current: str
    versions: dict[str, str]


class _FakeSecretsManagerClient:
    def __init__(self) -> None:
        self._counter = 1
        self._store: dict[str, _SecretState] = {
            "app/db/password": _SecretState(current="v1", versions={"v1": "old-db-password"})
        }

    def _next_version(self) -> str:
        self._counter += 1
        return f"v{self._counter}"

    def get_secret_value(self, *, SecretId: str) -> dict[str, str]:
        state = self._store.get(SecretId)
        if state is None:
            raise _client_error("ResourceNotFoundException", "GetSecretValue")
        return {"SecretString": state.versions[state.current], "VersionId": state.current}

    def put_secret_value(self, *, SecretId: str, SecretString: str) -> dict[str, str]:
        state = self._store.get(SecretId)
        if state is None:
            raise _client_error("ResourceNotFoundException", "PutSecretValue")
        version = self._next_version()
        state.versions[version] = SecretString
        state.current = version
        return {"VersionId": version}

    def create_secret(self, *, Name: str, SecretString: str) -> dict[str, str]:
        version = self._next_version()
        self._store[Name] = _SecretState(current=version, versions={version: SecretString})
        return {"VersionId": version}

    def update_secret_version_stage(
        self,
        *,
        SecretId: str,
        VersionStage: str,
        MoveToVersionId: str,
        RemoveFromVersionId: str,
    ) -> None:
        del VersionStage
        del RemoveFromVersionId
        state = self._store.get(SecretId)
        if state is None or MoveToVersionId not in state.versions:
            raise _client_error("ResourceNotFoundException", "UpdateSecretVersionStage")
        state.current = MoveToVersionId

    def delete_secret(self, *, SecretId: str, ForceDeleteWithoutRecovery: bool) -> None:
        del ForceDeleteWithoutRecovery
        self._store.pop(SecretId, None)


class _FakeSecretsManagerUnavailableClient(_FakeSecretsManagerClient):
    def put_secret_value(self, *, SecretId: str, SecretString: str) -> dict[str, str]:
        del SecretId, SecretString
        raise _client_error("ServiceUnavailable", "PutSecretValue")


class _FakeSsmClient:
    def __init__(self) -> None:
        self._store: dict[str, list[dict[str, int | str]]] = {
            "/app/token": [{"Version": 1, "Value": "old-token", "Type": "SecureString"}]
        }

    def _current(self, name: str) -> dict[str, int | str]:
        versions = self._store.get(name)
        if not versions:
            raise _client_error("ParameterNotFound", "GetParameter")
        return versions[-1]

    def get_parameter(self, *, Name: str, WithDecryption: bool) -> dict[str, object]:
        del WithDecryption
        current = self._current(Name)
        return {"Parameter": current}

    def put_parameter(self, *, Name: str, Value: str, Type: str, Overwrite: bool) -> dict[str, int]:
        del Overwrite
        versions = self._store.setdefault(Name, [])
        version = int(versions[-1].get("Version", 0)) + 1 if versions else 1
        versions.append({"Version": version, "Value": Value, "Type": Type})
        return {"Version": version}

    def get_parameter_history(self, *, Name: str, WithDecryption: bool) -> dict[str, object]:
        del WithDecryption
        versions = self._store.get(Name)
        if not versions:
            raise _client_error("ParameterNotFound", "GetParameterHistory")
        return {"Parameters": list(versions)}

    def delete_parameter(self, *, Name: str) -> None:
        self._store.pop(Name, None)


class _FakeSession:
    def __init__(self, sm_client: object | None = None, ssm_client: object | None = None) -> None:
        self._sm = sm_client or _FakeSecretsManagerClient()
        self._ssm = ssm_client or _FakeSsmClient()

    def client(self, service_name: str, region_name: str) -> object:
        del region_name
        if service_name == "secretsmanager":
            return self._sm
        if service_name == "ssm":
            return self._ssm
        raise AssertionError(f"unexpected service_name={service_name}")


def test_aws_secrets_manager_connector_happy_path_with_rollback() -> None:
    connector = AwsSecretsManagerConnector(session=_FakeSession(), region="eu-north-1")
    before = connector.read_secret("app/db/password")
    assert before.value == "old-db-password"

    receipt = connector.upsert_secret("app/db/password", "new-db-password", dry_run=False)
    assert receipt.message == "applied"
    after = connector.read_secret("app/db/password")
    assert after.value == "new-db-password"

    connector.rollback_secret("app/db/password", receipt.rollback_token)
    rolled_back = connector.read_secret("app/db/password")
    assert rolled_back.value == "old-db-password"


def test_aws_ssm_parameter_store_connector_happy_path_with_rollback() -> None:
    connector = AwsSsmParameterStoreConnector(session=_FakeSession(), region="eu-north-1")
    before = connector.read_secret("/app/token")
    assert before.value == "old-token"

    receipt = connector.upsert_secret("/app/token", "new-token", dry_run=False)
    assert receipt.message == "applied"
    after = connector.read_secret("/app/token")
    assert after.value == "new-token"

    connector.rollback_secret("/app/token", receipt.rollback_token)
    rolled_back = connector.read_secret("/app/token")
    assert rolled_back.value == "old-token"


def test_github_actions_connector_happy_path_for_new_secret() -> None:
    list_result = _completed(returncode=0, stdout="NAME UPDATED\n")
    set_result = _completed(returncode=0, stdout="")
    delete_result = _completed(returncode=0, stdout="")
    with patch(
        "backend.services.secret_migration_connectors.subprocess.run",
        side_effect=[list_result, set_result, delete_result],
    ):
        connector = GithubActionsConnector(repo="owner/repo", gh_bin="gh")
        receipt = connector.upsert_secret("NEW_SECRET", "value-123", dry_run=False)
        assert receipt.message == "applied"
        connector.rollback_secret("NEW_SECRET", receipt.rollback_token)


def test_github_actions_connector_rejects_existing_secret_fail_closed() -> None:
    list_result = _completed(returncode=0, stdout="NAME UPDATED\nEXISTING_SECRET 2026-03-02\n")
    with patch(
        "backend.services.secret_migration_connectors.subprocess.run",
        side_effect=[list_result],
    ):
        connector = GithubActionsConnector(repo="owner/repo", gh_bin="gh")
        with pytest.raises(SecretMigrationValidationError) as error:
            connector.upsert_secret("EXISTING_SECRET", "value-123", dry_run=False)
    assert error.value.code == "github_actions_existing_secret_rollback_not_supported"


def test_target_unavailable_behavior_is_classified_retryable() -> None:
    connector = AwsSecretsManagerConnector(
        session=_FakeSession(sm_client=_FakeSecretsManagerUnavailableClient()),
        region="eu-north-1",
    )
    with pytest.raises(SecretMigrationUnavailableError) as error:
        connector.upsert_secret("app/db/password", "new-db-password", dry_run=False)
    assert error.value.retryable is True


@dataclass
class _Completed:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _completed(*, returncode: int, stdout: str = "", stderr: str = "") -> _Completed:
    return _Completed(returncode=returncode, stdout=stdout, stderr=stderr)
