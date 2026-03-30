from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import UserRole


def _mock_admin_user(role: UserRole = UserRole.admin) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        role=role,
        email="admin@example.com",
    )


def _mock_group_finding() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        control_id="S3.1",
        resource_type="AWS::S3::Bucket",
        account_id="123456789012",
        region="us-east-1",
        risk_acknowledged=False,
        risk_acknowledged_at=None,
        risk_acknowledged_by_user_id=None,
        risk_acknowledged_group_key=None,
        updated_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )


def _result_with_scalars(items: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _override_dependencies(user: object, session: MagicMock) -> None:
    async def _override_get_current_user() -> object:
        return user

    async def _override_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_db] = _override_get_db


def _clear_dependencies() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_group_action_requires_admin() -> None:
    user = _mock_admin_user(UserRole.member)
    session = MagicMock()
    session.execute = AsyncMock()

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/findings/group-actions",
            json={"action": "acknowledge_risk", "group_key": "S3.1|AWS::S3::Bucket|123456789012|us-east-1"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Only admins can apply grouped findings actions."
    finally:
        _clear_dependencies()


def test_group_action_acknowledge_risk_persists_fields() -> None:
    user = _mock_admin_user()
    finding = _mock_group_finding()
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[_result_with_scalars([finding])])
    session.commit = AsyncMock()

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/findings/group-actions",
            json={"action": "acknowledge_risk", "group_key": "S3.1|AWS::S3::Bucket|123456789012|us-east-1"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["acknowledged_findings"] == 1
        assert payload["status_updates"] == 1
        assert finding.risk_acknowledged is True
        assert finding.risk_acknowledged_by_user_id == user.id
        assert finding.risk_acknowledged_group_key == "S3.1|AWS::S3::Bucket|123456789012|us-east-1"
        assert finding.risk_acknowledged_at is not None
    finally:
        _clear_dependencies()


def test_group_action_false_positive_creates_exception_with_default_reason() -> None:
    user = _mock_admin_user()
    finding = _mock_group_finding()
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result_with_scalars([finding]),
            _result_with_scalars([]),
        ]
    )
    session.commit = AsyncMock()
    session.add = MagicMock()

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/findings/group-actions",
            json={"action": "false_positive", "group_key": "S3.1|AWS::S3::Bucket|123456789012|us-east-1"},
        )
        assert response.status_code == 200
        added_exception = session.add.call_args.args[0]
        assert added_exception.reason.startswith("False positive recorded from grouped findings review")
        assert added_exception.approval_metadata["classification"] == "false_positive"
        assert added_exception.approval_metadata["group_action"] == "false_positive"
        assert response.json()["exceptions_created"] == 1
    finally:
        _clear_dependencies()


def test_group_action_suppress_requires_reason_and_expiry() -> None:
    user = _mock_admin_user()
    finding = _mock_group_finding()
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[_result_with_scalars([finding])])

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/findings/group-actions",
            json={"action": "suppress", "group_key": "S3.1|AWS::S3::Bucket|123456789012|us-east-1"},
        )
        assert response.status_code == 400
        assert response.json()["detail"]["error"] == "Invalid reason"
    finally:
        _clear_dependencies()
