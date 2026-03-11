from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from backend.services.aws_account_orchestration import run_validation_probes


def _access_denied(operation: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
        operation,
    )


class _SecurityHubClient:
    def get_findings(self, **kwargs):
        return {"Findings": []}


class _EC2Client:
    def describe_security_groups(self, **kwargs):
        return {"SecurityGroups": []}


class _S3Client:
    def list_buckets(self):
        return {"Buckets": []}


class _STSClient:
    def get_caller_identity(self):
        return {"Account": "123456789012"}


class _ConfigClientMissingDescribe:
    def describe_configuration_recorders(self, **kwargs):
        return {"ConfigurationRecorders": []}

    def describe_delivery_channels(self, **kwargs):
        return {"DeliveryChannels": []}

    def describe_config_rules(self, **kwargs):
        raise _access_denied("DescribeConfigRules")

    def describe_compliance_by_config_rule(self, **kwargs):
        raise _access_denied("DescribeComplianceByConfigRule")


class _ConfigClientMissingDetails:
    def describe_configuration_recorders(self, **kwargs):
        return {"ConfigurationRecorders": []}

    def describe_delivery_channels(self, **kwargs):
        return {"DeliveryChannels": []}

    def describe_config_rules(self, **kwargs):
        return {"ConfigRules": [{"ConfigRuleName": "sg-open-admin-ports"}]}

    def describe_compliance_by_config_rule(self, **kwargs):
        return {"ComplianceByConfigRules": []}

    def get_compliance_details_by_config_rule(self, **kwargs):
        raise _access_denied("GetComplianceDetailsByConfigRule")


class _ConfigClientMissingRecorderAndDelivery:
    def describe_configuration_recorders(self, **kwargs):
        raise _access_denied("DescribeConfigurationRecorders")

    def describe_delivery_channels(self, **kwargs):
        raise _access_denied("DescribeDeliveryChannels")

    def describe_config_rules(self, **kwargs):
        return {"ConfigRules": []}

    def describe_compliance_by_config_rule(self, **kwargs):
        return {"ComplianceByConfigRules": []}


class _ConfigClientMissingComplianceSummaryOperation:
    def describe_configuration_recorders(self, **kwargs):
        return {"ConfigurationRecorders": []}

    def describe_delivery_channels(self, **kwargs):
        return {"DeliveryChannels": []}

    def describe_config_rules(self, **kwargs):
        return {"ConfigRules": [{"ConfigRuleName": "sg-open-admin-ports"}]}

    def get_compliance_details_by_config_rule(self, **kwargs):
        return {"EvaluationResults": []}


class _SessionStub:
    def __init__(self, config_client: Any):
        self._config_client = config_client

    def client(self, service_name: str, **kwargs):
        if service_name == "sts":
            return _STSClient()
        if service_name == "securityhub":
            return _SecurityHubClient()
        if service_name == "ec2":
            return _EC2Client()
        if service_name == "s3":
            return _S3Client()
        if service_name == "config":
            return self._config_client
        raise AssertionError(f"unexpected service: {service_name}")


def test_run_validation_probes_surfaces_missing_config_describe_permissions() -> None:
    result = run_validation_probes(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        tenant_external_id="tenant-ext-id",
        configured_regions=["us-east-1"],
        default_region="us-east-1",
        assume_role_fn=lambda **kwargs: _SessionStub(_ConfigClientMissingDescribe()),
    )

    assert result.permissions_ok is False
    assert "config:DescribeConfigRules" in result.missing_permissions
    assert "config:DescribeComplianceByConfigRule" in result.missing_permissions


def test_run_validation_probes_surfaces_missing_config_recorder_delivery_permissions() -> None:
    result = run_validation_probes(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        tenant_external_id="tenant-ext-id",
        configured_regions=["us-east-1"],
        default_region="us-east-1",
        assume_role_fn=lambda **kwargs: _SessionStub(_ConfigClientMissingRecorderAndDelivery()),
    )

    assert result.permissions_ok is False
    assert "config:DescribeConfigurationRecorders" in result.missing_permissions
    assert "config:DescribeDeliveryChannels" in result.missing_permissions


def test_run_validation_probes_surfaces_missing_config_details_permission() -> None:
    result = run_validation_probes(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        tenant_external_id="tenant-ext-id",
        configured_regions=["us-east-1"],
        default_region="us-east-1",
        assume_role_fn=lambda **kwargs: _SessionStub(_ConfigClientMissingDetails()),
    )

    assert result.permissions_ok is False
    assert "config:GetComplianceDetailsByConfigRule" in result.missing_permissions


def test_run_validation_probes_fails_closed_when_config_summary_probe_unavailable() -> None:
    result = run_validation_probes(
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        tenant_external_id="tenant-ext-id",
        configured_regions=["us-east-1"],
        default_region="us-east-1",
        assume_role_fn=lambda **kwargs: _SessionStub(_ConfigClientMissingComplianceSummaryOperation()),
    )

    assert result.permissions_ok is False
    assert result.missing_permissions == []
    assert any("describe_compliance_by_config_rule" in warning for warning in result.warnings)
    assert result.block_reasons == [
        "Unable to verify required ReadRole probe config:DescribeComplianceByConfigRule; authoritative mode remains blocked."
    ]
