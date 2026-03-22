from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


CONFIG_COMPLIANCE_SUMMARY_PERMISSION = "config:DescribeComplianceByConfigRule"


@dataclass(frozen=True)
class ConfigComplianceSummaryProbe:
    response: dict[str, Any] | None
    unavailable_reason: str | None = None


def describe_non_compliant_config_rule_summary(
    config_client: Any,
    *,
    config_rule_names: Sequence[str] | None = None,
    limit: int = 1,
) -> ConfigComplianceSummaryProbe:
    describe = getattr(config_client, "describe_compliance_by_config_rule", None)
    if not callable(describe):
        return ConfigComplianceSummaryProbe(
            response=None,
            unavailable_reason=(
                "AWS Config compliance summary probe (describe_compliance_by_config_rule) is unavailable in this "
                "boto3/botocore runtime; "
                f"unable to verify {CONFIG_COMPLIANCE_SUMMARY_PERMISSION}."
            ),
        )

    # describe_compliance_by_config_rule does not accept a Limit argument.
    # Callers use `limit` only as a low-cost probe hint, so we ignore it here.
    _ = limit
    kwargs: dict[str, Any] = {"ComplianceTypes": ["NON_COMPLIANT"]}
    if config_rule_names:
        kwargs["ConfigRuleNames"] = list(config_rule_names)
    return ConfigComplianceSummaryProbe(response=describe(**kwargs))
