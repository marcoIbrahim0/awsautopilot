from __future__ import annotations

from typing import Any

from backend.services.sg_account_scope_resolver import (
    is_account_scoped_sg_control,
    resolve_account_scoped_sg_ids_from_finding,
)


class _ConfigClientStub:
    def __init__(self) -> None:
        self._rules = [{"ConfigRuleName": "sg-open-admin-ports"}]

    def describe_config_rules(self, **kwargs: Any) -> dict[str, Any]:
        names = kwargs.get("ConfigRuleNames") or []
        if names and names[0] == "sg-open-admin-ports":
            return {
                "ConfigRules": [
                    {
                        "ConfigRuleName": "sg-open-admin-ports",
                        "ConfigRuleArn": "arn:aws:config:eu-north-1:029037611564:config-rule/sg-open-admin-ports",
                        "ConfigRuleId": "config-rule-abc123",
                        "Source": {"SourceIdentifier": "VPC_SG_OPEN_ONLY_TO_AUTHORIZED_PORTS"},
                    }
                ]
            }
        if names:
            return {"ConfigRules": []}
        return {"ConfigRules": list(self._rules)}

    def describe_compliance_by_config_rules(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "ComplianceByConfigRules": [
                {"ConfigRuleName": "sg-open-admin-ports", "Compliance": {"ComplianceType": "NON_COMPLIANT"}}
            ]
        }

    def get_compliance_details_by_config_rule(self, **kwargs: Any) -> dict[str, Any]:
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
                            "ResourceId": "arn:aws:ec2:eu-north-1:029037611564:security-group/sg-0de002382892023f5",
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


class _NoSGConfigClientStub(_ConfigClientStub):
    def get_compliance_details_by_config_rule(self, **kwargs: Any) -> dict[str, Any]:
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


def test_is_account_scoped_sg_control_detects_aliases() -> None:
    assert is_account_scoped_sg_control("EC2.53", "AwsAccount") is True
    assert is_account_scoped_sg_control("ec2.19", "AwsAccount") is True
    assert is_account_scoped_sg_control("EC2.53", "AwsEc2SecurityGroup") is False
    assert is_account_scoped_sg_control("S3.2", "AwsAccount") is False


def test_resolver_happy_path_returns_deduped_sg_ids() -> None:
    payload = {
        "Id": "arn:aws:securityhub:eu-north-1:029037611564:finding/account-scope-sg",
        "GeneratorId": "security-control/EC2.53",
        "ProductFields": {
            "aws/securityhub/FindingId": "arn:aws:securityhub:eu-north-1::product/aws/securityhub/arn:aws:config:eu-north-1:029037611564:config-rule/sg-open-admin-ports/finding/abc"
        },
    }

    resolution = resolve_account_scoped_sg_ids_from_finding(_ConfigClientStub(), payload)

    assert resolution.reason is None
    assert resolution.config_rule_name == "sg-open-admin-ports"
    assert resolution.security_group_ids == [
        "sg-04c93cf37e5f27d07",
        "sg-0de002382892023f5",
    ]


def test_resolver_no_sg_result_returns_clear_reason() -> None:
    payload = {
        "Id": "arn:aws:securityhub:eu-north-1:029037611564:finding/account-scope-sg",
        "ProductFields": {
            "aws/securityhub/FindingId": "arn:aws:securityhub:eu-north-1::product/aws/securityhub/arn:aws:config:eu-north-1:029037611564:config-rule/sg-open-admin-ports/finding/abc"
        },
    }

    resolution = resolve_account_scoped_sg_ids_from_finding(_NoSGConfigClientStub(), payload)

    assert resolution.security_group_ids == []
    assert resolution.config_rule_name == "sg-open-admin-ports"
    assert resolution.reason == "non_compliant_results_without_security_groups"
