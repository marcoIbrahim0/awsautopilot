from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.exc import IntegrityError

from backend.models.action import Action
from backend.models.action_finding import ActionFinding
from backend.models.aws_account import AwsAccount
from backend.models.finding import Finding
from backend.models.tenant import Tenant
from backend.services.action_engine import (
    ExpandedFindingTarget,
    _ActionExpansionContext,
    _upsert_action_and_sync_links,
)
from backend.services.pr_bundle import generate_pr_bundle


class _SingleResultQuery:
    def __init__(self, value):
        self._value = value

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._value


class _ExpansionSessionStub:
    def __init__(self, account: AwsAccount, tenant: Tenant):
        self._account = account
        self._tenant = tenant

    def query(self, model):
        if model is AwsAccount:
            return _SingleResultQuery(self._account)
        if model is Tenant:
            return _SingleResultQuery(self._tenant)
        raise AssertionError(f"unexpected query model: {model}")


class _ActionQuery:
    def __init__(self, existing):
        self._existing = existing

    def options(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._existing


class _LinkQuery:
    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _ActionSessionStub:
    def __init__(self, existing_action: Action | None = None):
        self._existing_action = existing_action
        self.added: list[object] = []

    def query(self, model):
        if model is Action:
            return _ActionQuery(self._existing_action)
        if model is ActionFinding:
            return _LinkQuery()
        raise AssertionError(f"unexpected query model: {model}")

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def begin_nested(self):
        return _NullContextManager()

    def flush(self, objs=None) -> None:  # noqa: ANN001
        return None

    def __contains__(self, obj: object) -> bool:
        return obj in self.added

    def expunge(self, obj: object) -> None:
        if obj in self.added:
            self.added.remove(obj)


class _NullContextManager:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        return False


class _DuplicateInsertActionSessionStub(_ActionSessionStub):
    def __init__(self, existing_action: Action):
        super().__init__(existing_action=None)
        self._recovered_action = existing_action
        self.flush_calls = 0

    def flush(self, objs=None) -> None:  # noqa: ANN001
        self.flush_calls += 1
        if self.flush_calls == 1:
            self._existing_action = self._recovered_action
            raise IntegrityError("insert", {}, Exception("duplicate"))


def _s3_lifecycle_finding(tenant_id: uuid.UUID) -> Finding:
    return Finding(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        account_id="696505809372",
        region="eu-north-1",
        finding_id="finding-s3-lifecycle",
        source="security_hub",
        severity_label="LOW",
        control_id="S3.13",
        resource_id="arn:aws:s3:::config-bucket-696505809372",
        resource_type="AwsS3Bucket",
        severity_normalized=18,
        title="S3 general purpose buckets should have Lifecycle configurations",
        description="Lifecycle configuration missing",
        status="NEW",
        in_scope=True,
        raw_json={},
    )


class _ConfigClientHappy:
    def describe_config_rules(self, **kwargs):
        names = kwargs.get("ConfigRuleNames") or []
        if names and names[0] == "sg-open-admin-ports":
            return {"ConfigRules": [{"ConfigRuleName": "sg-open-admin-ports"}]}
        if names:
            return {"ConfigRules": []}
        return {"ConfigRules": [{"ConfigRuleName": "sg-open-admin-ports"}]}

    def describe_compliance_by_config_rule(self, **kwargs):
        return {"ComplianceByConfigRules": [{"Compliance": {"ComplianceType": "NON_COMPLIANT"}}]}

    def get_compliance_details_by_config_rule(self, **kwargs):
        return {
            "EvaluationResults": [
                {
                    "EvaluationResultIdentifier": {
                        "EvaluationResultQualifier": {
                            "ResourceType": "AWS::EC2::SecurityGroup",
                            "ResourceId": "sg-0de002382892023f5",
                        }
                    }
                },
                {
                    "EvaluationResultIdentifier": {
                        "EvaluationResultQualifier": {
                            "ResourceType": "AWS::EC2::SecurityGroup",
                            "ResourceId": "sg-04c93cf37e5f27d07",
                        }
                    }
                },
            ]
        }


class _ConfigClientNoSG(_ConfigClientHappy):
    def get_compliance_details_by_config_rule(self, **kwargs):
        return {
            "EvaluationResults": [
                {
                    "EvaluationResultIdentifier": {
                        "EvaluationResultQualifier": {
                            "ResourceType": "AWS::EC2::Instance",
                            "ResourceId": "i-0123456789abcdef0",
                        }
                    }
                }
            ]
        }


class _BotoSessionStub:
    def __init__(self, config_client):
        self._config_client = config_client

    def client(self, service_name: str, **kwargs):
        if service_name == "config":
            return self._config_client
        raise AssertionError(f"unexpected boto client: {service_name}")


def _account_scoped_finding(tenant_id: uuid.UUID):
    return Finding(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        account_id="029037611564",
        region="eu-north-1",
        finding_id="finding-account-scope-sg",
        source="security_hub",
        severity_label="HIGH",
        control_id="EC2.53",
        resource_id="AWS::::Account:029037611564",
        resource_type="AwsAccount",
        severity_normalized=75,
        title="Security group allows public admin ports",
        description="Public SSH/RDP is allowed",
        status="NEW",
        in_scope=True,
        raw_json={
            "ProductFields": {
                "aws/securityhub/FindingId": "arn:aws:securityhub:eu-north-1::product/aws/securityhub/arn:aws:config:eu-north-1:029037611564:config-rule/sg-open-admin-ports/finding/abc"
            }
        },
    )


def test_account_scoped_sg_finding_expands_to_sg_targets() -> None:
    tenant_id = uuid.uuid4()
    account = SimpleNamespace(account_id="029037611564", role_read_arn="arn:aws:iam::029037611564:role/SecurityAutopilotReadRole")
    tenant = SimpleNamespace(id=tenant_id, external_id="tenant-ext-id")
    session = _ExpansionSessionStub(account=account, tenant=tenant)
    context = _ActionExpansionContext(session, tenant_id)

    with patch(
        "backend.services.action_engine.assume_role",
        return_value=_BotoSessionStub(_ConfigClientHappy()),
    ):
        expanded = context.expand_finding(_account_scoped_finding(tenant_id))

    assert len(expanded) == 2
    assert {item.resource_id for item in expanded} == {"sg-0de002382892023f5", "sg-04c93cf37e5f27d07"}
    assert all(item.resource_type == "AwsEc2SecurityGroup" for item in expanded)
    assert all(item.allow_multi_action_links for item in expanded)


def test_account_scoped_sg_finding_without_resolved_sgs_fails_closed() -> None:
    tenant_id = uuid.uuid4()
    account = SimpleNamespace(account_id="029037611564", role_read_arn="arn:aws:iam::029037611564:role/SecurityAutopilotReadRole")
    tenant = SimpleNamespace(id=tenant_id, external_id="tenant-ext-id")
    session = _ExpansionSessionStub(account=account, tenant=tenant)
    context = _ActionExpansionContext(session, tenant_id)

    with patch(
        "backend.services.action_engine.assume_role",
        return_value=_BotoSessionStub(_ConfigClientNoSG()),
    ):
        expanded = context.expand_finding(_account_scoped_finding(tenant_id))

    assert expanded == []


def test_expanded_sg_action_generation_and_pr_bundle_regression() -> None:
    tenant_id = uuid.uuid4()
    finding = _account_scoped_finding(tenant_id)
    group = [
        ExpandedFindingTarget(
            finding=finding,
            resource_id="sg-0de002382892023f5",
            resource_type="AwsEc2SecurityGroup",
            allow_multi_action_links=True,
        )
    ]
    session = _ActionSessionStub()

    action, created, finding_ids, allow_multi = _upsert_action_and_sync_links(session, tenant_id, group)

    assert created is True
    assert allow_multi is True
    assert finding_ids == [finding.id]
    assert action.action_type == "sg_restrict_public_ports"
    assert action.resource_id == "sg-0de002382892023f5"
    assert "sg-0de002382892023f5" in action.target_id

    if action.id is None:
        action.id = uuid.uuid4()
    bundle = generate_pr_bundle(action, "terraform")
    sg_file = next(file for file in bundle["files"] if file["path"] == "sg_restrict_public_ports.tf")
    assert "sg-0de002382892023f5" in sg_file["content"]


def test_expanded_sg_action_upsert_is_idempotent() -> None:
    tenant_id = uuid.uuid4()
    finding = _account_scoped_finding(tenant_id)
    existing_action = Action(
        tenant_id=tenant_id,
        action_type="sg_restrict_public_ports",
        target_id="029037611564|eu-north-1|sg-0de002382892023f5|EC2.53",
        account_id="029037611564",
        region="eu-north-1",
        priority=75,
        status="open",
        title="old",
        description="old",
        control_id="EC2.53",
        resource_id="sg-0de002382892023f5",
        resource_type="AwsEc2SecurityGroup",
    )
    session = _ActionSessionStub(existing_action=existing_action)
    group = [
        ExpandedFindingTarget(
            finding=finding,
            resource_id="sg-0de002382892023f5",
            resource_type="AwsEc2SecurityGroup",
            allow_multi_action_links=True,
        )
    ]

    action, created, _, _ = _upsert_action_and_sync_links(session, tenant_id, group)

    assert created is False
    assert action is existing_action
    assert len(session.added) == 1
    assert isinstance(session.added[0], ActionFinding)
    assert action.resource_id == "sg-0de002382892023f5"


def test_upsert_action_recovers_from_duplicate_insert_race() -> None:
    tenant_id = uuid.uuid4()
    finding = _s3_lifecycle_finding(tenant_id)
    existing_action = Action(
        tenant_id=tenant_id,
        action_type="s3_bucket_lifecycle_configuration",
        target_id="696505809372|eu-north-1|arn:aws:s3:::config-bucket-696505809372|S3.11",
        account_id="696505809372",
        region="eu-north-1",
        priority=18,
        status="open",
        title="old",
        description="old",
        control_id="S3.11",
        resource_id="arn:aws:s3:::config-bucket-696505809372",
        resource_type="AwsS3Bucket",
    )
    session = _DuplicateInsertActionSessionStub(existing_action)
    group = [
        ExpandedFindingTarget(
            finding=finding,
            resource_id="arn:aws:s3:::config-bucket-696505809372",
            resource_type="AwsS3Bucket",
        )
    ]
    action_cache: dict[tuple[uuid.UUID, str, str, str, str | None], Action] = {}

    action, created, finding_ids, allow_multi = _upsert_action_and_sync_links(
        session,
        tenant_id,
        group,
        action_cache=action_cache,
    )

    assert created is False
    assert allow_multi is False
    assert finding_ids == [finding.id]
    assert action is existing_action
    assert session.flush_calls == 1
    assert len(session.added) == 1
    assert isinstance(session.added[0], ActionFinding)
    assert existing_action.title == "S3 general purpose buckets should have Lifecycle configurations"
    assert action_cache[(tenant_id, existing_action.action_type, existing_action.target_id, existing_action.account_id, existing_action.region)] is existing_action
