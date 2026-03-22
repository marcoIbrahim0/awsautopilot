from __future__ import annotations

from unittest.mock import MagicMock

from backend.services.aws_config_probe import describe_non_compliant_config_rule_summary


def test_describe_non_compliant_config_rule_summary_omits_unsupported_limit_kwarg() -> None:
    config_client = MagicMock()
    config_client.describe_compliance_by_config_rule.return_value = {
        "ComplianceByConfigRules": [
            {"ConfigRuleName": "required-tags", "Compliance": {"ComplianceType": "NON_COMPLIANT"}}
        ]
    }

    probe = describe_non_compliant_config_rule_summary(
        config_client,
        config_rule_names=["required-tags"],
        limit=1,
    )

    assert probe.unavailable_reason is None
    assert probe.response is not None
    assert config_client.describe_compliance_by_config_rule.call_args.kwargs == {
        "ComplianceTypes": ["NON_COMPLIANT"],
        "ConfigRuleNames": ["required-tags"],
    }


def test_describe_non_compliant_config_rule_summary_reports_missing_runtime_support() -> None:
    probe = describe_non_compliant_config_rule_summary(object())

    assert probe.response is None
    assert probe.unavailable_reason is not None
