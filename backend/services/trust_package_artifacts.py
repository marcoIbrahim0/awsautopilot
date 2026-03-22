from __future__ import annotations

import copy
import json
import sys
import types
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

REDACTED_EXTERNAL_ID = "<REDACTED_EXTERNAL_ID>"


class _CloudFormationLoader(yaml.SafeLoader):
    pass


def _construct_cfn_node(loader: yaml.SafeLoader, _tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_CloudFormationLoader.add_multi_constructor("!", _construct_cfn_node)


def _load_template(path: Path) -> dict[str, Any]:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_CloudFormationLoader)


def _template_resource(template: Mapping[str, Any], resource_name: str) -> Mapping[str, Any]:
    resources = template.get("Resources")
    if not isinstance(resources, Mapping) or resource_name not in resources:
        raise KeyError(f"Resource '{resource_name}' not found in template.")
    resource = resources[resource_name]
    if not isinstance(resource, Mapping):
        raise TypeError(f"Resource '{resource_name}' was not a mapping.")
    return resource


def _resource_properties(resource: Mapping[str, Any]) -> Mapping[str, Any]:
    properties = resource.get("Properties")
    if not isinstance(properties, Mapping):
        raise TypeError("CloudFormation resource Properties must be a mapping.")
    return properties


def _load_helper_namespace(template: Mapping[str, Any], helper_resource_name: str) -> dict[str, Any]:
    code = _resource_properties(_template_resource(template, helper_resource_name)).get("Code", {})
    if not isinstance(code, Mapping) or not isinstance(code.get("ZipFile"), str):
        raise TypeError(f"Inline helper code missing on resource '{helper_resource_name}'.")
    sys.modules["cfnresponse"] = types.SimpleNamespace(
        SUCCESS="SUCCESS",
        FAILED="FAILED",
        send=lambda *args, **kwargs: None,
    )
    namespace: dict[str, Any] = {}
    exec(code["ZipFile"], namespace)
    return namespace


def _template_version(template: Mapping[str, Any], custom_resource_name: str) -> str:
    properties = _resource_properties(_template_resource(template, custom_resource_name))
    version = properties.get("TemplateVersion")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"TemplateVersion missing on resource '{custom_resource_name}'.")
    return version


def _render_role_documents(
    *,
    template_path: Path,
    helper_resource_name: str,
    custom_resource_name: str,
    policy_function_name: str,
    saas_account_id: str,
    external_id: str,
    saas_execution_role_arns: str,
    partition: str,
) -> dict[str, Any]:
    template = _load_template(template_path)
    namespace = _load_helper_namespace(template, helper_resource_name)
    trust_policy = namespace["trust_policy"](saas_account_id, external_id, saas_execution_role_arns, partition)
    identity_policy = namespace[policy_function_name]()
    return {
        "template_version": _template_version(template, custom_resource_name),
        "trust_policy": trust_policy,
        "identity_policy": identity_policy,
    }


def render_read_role_documents(
    template_path: Path,
    *,
    saas_account_id: str,
    external_id: str,
    saas_execution_role_arns: str,
    partition: str = "aws",
) -> dict[str, Any]:
    return _render_role_documents(
        template_path=template_path,
        helper_resource_name="ReadRoleHelperFunction",
        custom_resource_name="ReadRoleCustomResource",
        policy_function_name="read_policy_document",
        saas_account_id=saas_account_id,
        external_id=external_id,
        saas_execution_role_arns=saas_execution_role_arns,
        partition=partition,
    )


def render_write_role_documents(
    template_path: Path,
    *,
    saas_account_id: str,
    external_id: str,
    saas_execution_role_arns: str,
    partition: str = "aws",
) -> dict[str, Any]:
    return _render_role_documents(
        template_path=template_path,
        helper_resource_name="WriteRoleHelperFunction",
        custom_resource_name="WriteRoleCustomResource",
        policy_function_name="policy_document",
        saas_account_id=saas_account_id,
        external_id=external_id,
        saas_execution_role_arns=saas_execution_role_arns,
        partition=partition,
    )


def redact_external_id(document: Mapping[str, Any]) -> dict[str, Any]:
    redacted = copy.deepcopy(document)
    statements = redacted.get("Statement")
    if not isinstance(statements, list):
        return redacted
    for statement in statements:
        if not isinstance(statement, dict):
            continue
        conditions = statement.get("Condition")
        if not isinstance(conditions, dict):
            continue
        string_equals = conditions.get("StringEquals")
        if not isinstance(string_equals, dict) or "sts:ExternalId" not in string_equals:
            continue
        string_equals["sts:ExternalId"] = REDACTED_EXTERNAL_ID
    return redacted


def _parsed_cloudtrail_event(event: Mapping[str, Any]) -> dict[str, Any] | None:
    raw_event = event.get("CloudTrailEvent")
    if not isinstance(raw_event, str) or not raw_event.strip():
        return None
    return json.loads(raw_event)


def _sanitized_assume_role_event(
    event: Mapping[str, Any],
    parsed: Mapping[str, Any],
    request_parameters: Mapping[str, Any],
) -> dict[str, Any]:
    user_identity = parsed.get("userIdentity") if isinstance(parsed.get("userIdentity"), Mapping) else {}
    session_context = user_identity.get("sessionContext") if isinstance(user_identity, Mapping) else {}
    session_issuer = session_context.get("sessionIssuer") if isinstance(session_context, Mapping) else {}
    event_time = event.get("EventTime")
    if hasattr(event_time, "isoformat"):
        event_time = event_time.isoformat()
    return {
        "event_id": event.get("EventId"),
        "event_time": event_time,
        "aws_region": parsed.get("awsRegion"),
        "recipient_account_id": parsed.get("recipientAccountId"),
        "source_ip_address": parsed.get("sourceIPAddress"),
        "user_agent": parsed.get("userAgent"),
        "error_code": parsed.get("errorCode"),
        "error_message": parsed.get("errorMessage"),
        "request_parameters": {
            "role_arn": request_parameters.get("roleArn"),
            "role_session_name": request_parameters.get("roleSessionName"),
        },
        "user_identity": {
            "type": user_identity.get("type") if isinstance(user_identity, Mapping) else None,
            "arn": user_identity.get("arn") if isinstance(user_identity, Mapping) else None,
            "principal_id": user_identity.get("principalId") if isinstance(user_identity, Mapping) else None,
            "session_issuer_arn": session_issuer.get("arn") if isinstance(session_issuer, Mapping) else None,
            "session_issuer_user_name": session_issuer.get("userName") if isinstance(session_issuer, Mapping) else None,
        },
    }


def build_sanitized_assume_role_events(
    events: Sequence[Mapping[str, Any]],
    *,
    role_arn: str,
) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for event in events:
        parsed = _parsed_cloudtrail_event(event)
        if parsed is None:
            continue
        request_parameters = parsed.get("requestParameters")
        if not isinstance(request_parameters, Mapping):
            continue
        if str(request_parameters.get("roleArn") or "") != role_arn:
            continue
        sanitized.append(_sanitized_assume_role_event(event, parsed, request_parameters))
    return sanitized
