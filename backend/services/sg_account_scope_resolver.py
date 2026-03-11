from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import ClientError

from backend.services.aws_config_probe import describe_non_compliant_config_rule_summary

_SG_ID_PATTERN = re.compile(r"\bsg-[0-9a-fA-F]{8,17}\b")
_CONFIG_RULE_PATTERN = re.compile(r"config-rule[/:]([A-Za-z0-9_-]{1,256})", re.IGNORECASE)
_VALID_CONFIG_RULE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_ACCESS_DENIED_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedAccess",
    "UnauthorizedOperation",
}
_SG_CONTROL_IDS = frozenset({"EC2.13", "EC2.18", "EC2.19", "EC2.53"})


@dataclass(frozen=True)
class SGAccountScopeResolution:
    security_group_ids: list[str]
    config_rule_name: str | None
    reason: str | None


def is_account_scoped_sg_control(control_id: str | None, resource_type: str | None) -> bool:
    control = str(control_id or "").strip().upper()
    return control in _SG_CONTROL_IDS and str(resource_type or "").strip() == "AwsAccount"


def _error_code(error: ClientError) -> str:
    return str(error.response.get("Error", {}).get("Code") or "ClientError")


def _extract_strings(payload: Any) -> list[str]:
    if isinstance(payload, str):
        token = payload.strip()
        return [token] if token else []
    if isinstance(payload, list):
        out: list[str] = []
        for item in payload:
            out.extend(_extract_strings(item))
        return out
    if isinstance(payload, dict):
        out: list[str] = []
        for key, value in payload.items():
            if isinstance(key, str):
                token = key.strip()
                if token:
                    out.append(token)
            out.extend(_extract_strings(value))
        return out
    return []


def _derive_config_rule_identifiers(finding_payload: dict[str, Any]) -> list[str]:
    candidates: list[str] = []

    product_fields = finding_payload.get("ProductFields")
    if isinstance(product_fields, dict):
        for key, value in product_fields.items():
            key_text = str(key or "")
            value_text = str(value or "").strip()
            if "config" in key_text.lower() and "rule" in key_text.lower() and value_text:
                candidates.append(value_text)

    for text in _extract_strings(
        [
            finding_payload.get("Id"),
            finding_payload.get("GeneratorId"),
            finding_payload.get("ProductFields"),
            finding_payload.get("Resources"),
            finding_payload.get("Compliance"),
        ]
    ):
        candidates.append(text)
        for match in _CONFIG_RULE_PATTERN.findall(text):
            token = match.strip()
            if token:
                candidates.append(token)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        token = str(candidate or "").strip().strip('"').strip("'")
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def _list_config_rules(config_client: Any) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    next_token: str | None = None
    while True:
        kwargs: dict[str, Any] = {}
        if next_token:
            kwargs["NextToken"] = next_token
        response = config_client.describe_config_rules(**kwargs)
        rules.extend(response.get("ConfigRules") or [])
        next_token = response.get("NextToken")
        if not next_token:
            return rules


def _resolve_config_rule_name(config_client: Any, identifiers: list[str]) -> str | None:
    for token in identifiers:
        if not _VALID_CONFIG_RULE_NAME.fullmatch(token):
            continue
        try:
            response = config_client.describe_config_rules(ConfigRuleNames=[token])
        except ClientError:
            continue
        config_rules = response.get("ConfigRules") or []
        if config_rules:
            name = str((config_rules[0] or {}).get("ConfigRuleName") or "").strip()
            if name:
                return name

    try:
        config_rules = _list_config_rules(config_client)
    except ClientError:
        return None

    for rule in config_rules:
        name = str(rule.get("ConfigRuleName") or "").strip()
        arn = str(rule.get("ConfigRuleArn") or "").strip()
        rule_id = str(rule.get("ConfigRuleId") or "").strip()
        source_identifier = str((rule.get("Source") or {}).get("SourceIdentifier") or "").strip()
        values = {name, arn, rule_id, source_identifier}
        for token in identifiers:
            if token in values or (arn and token in arn):
                return name or None
    return None


def _extract_sg_ids_from_evaluation_results(evaluations: list[dict[str, Any]]) -> list[str]:
    sg_ids: list[str] = []
    for item in evaluations:
        qualifier = (item.get("EvaluationResultIdentifier") or {}).get("EvaluationResultQualifier") or {}
        resource_id = str(qualifier.get("ResourceId") or "").strip()
        resource_type = str(qualifier.get("ResourceType") or "").strip()
        if resource_type and resource_type != "AWS::EC2::SecurityGroup":
            continue
        match = _SG_ID_PATTERN.search(resource_id)
        if match:
            sg_ids.append(match.group(0).lower())
    return sorted(set(sg_ids))


def resolve_account_scoped_sg_ids_from_finding(
    config_client: Any,
    finding_payload: dict[str, Any],
) -> SGAccountScopeResolution:
    identifiers = _derive_config_rule_identifiers(finding_payload)
    if not identifiers:
        return SGAccountScopeResolution([], None, "config_rule_identifier_not_found")

    config_rule_name = _resolve_config_rule_name(config_client, identifiers)
    if not config_rule_name:
        return SGAccountScopeResolution([], None, "config_rule_not_found")

    try:
        compliance_probe = describe_non_compliant_config_rule_summary(
            config_client,
            config_rule_names=[config_rule_name],
        )
    except ClientError as error:
        code = _error_code(error)
        reason = "config_access_denied" if code in _ACCESS_DENIED_CODES else f"config_api_error:{code}"
        return SGAccountScopeResolution([], config_rule_name, reason)

    if compliance_probe.unavailable_reason:
        return SGAccountScopeResolution([], config_rule_name, "config_compliance_summary_unavailable")

    compliance_rows = (compliance_probe.response or {}).get("ComplianceByConfigRules") or []
    if not compliance_rows:
        return SGAccountScopeResolution([], config_rule_name, "no_non_compliant_resources")

    next_token: str | None = None
    evaluations: list[dict[str, Any]] = []
    try:
        while True:
            kwargs: dict[str, Any] = {
                "ConfigRuleName": config_rule_name,
                "ComplianceTypes": ["NON_COMPLIANT"],
                "Limit": 100,
            }
            if next_token:
                kwargs["NextToken"] = next_token
            response = config_client.get_compliance_details_by_config_rule(**kwargs)
            evaluations.extend(response.get("EvaluationResults") or [])
            next_token = response.get("NextToken")
            if not next_token:
                break
    except ClientError as error:
        code = _error_code(error)
        reason = "config_access_denied" if code in _ACCESS_DENIED_CODES else f"config_api_error:{code}"
        return SGAccountScopeResolution([], config_rule_name, reason)

    sg_ids = _extract_sg_ids_from_evaluation_results(evaluations)
    if not sg_ids:
        return SGAccountScopeResolution([], config_rule_name, "non_compliant_results_without_security_groups")
    return SGAccountScopeResolution(sg_ids, config_rule_name, None)


__all__ = [
    "SGAccountScopeResolution",
    "is_account_scoped_sg_control",
    "resolve_account_scoped_sg_ids_from_finding",
]
