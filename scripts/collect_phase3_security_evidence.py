#!/usr/bin/env python3
"""
Collect Phase 3 security evidence snapshots from AWS for SEC-010 (edge protections).
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError


DEFAULT_EDGE_STACK = "security-autopilot-edge-protection"
DEFAULT_OUT_DIR = "docs/audit-remediation/evidence"

_UUID_RE = re.compile(r"^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$", re.IGNORECASE)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Phase 3 security evidence artifacts (SEC-010).")
    parser.add_argument("--region", default="", help="AWS region override (defaults to env/profile region).")
    parser.add_argument("--edge-stack", default=DEFAULT_EDGE_STACK)
    parser.add_argument("--scope", default="", help="Optional WAF scope override (REGIONAL or CLOUDFRONT).")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    return parser


def _describe_stack(cf: Any, stack_name: str) -> dict[str, Any] | None:
    try:
        response = cf.describe_stacks(StackName=stack_name)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"ValidationError", "ResourceNotFoundException"}:
            return None
        raise
    stacks = response.get("Stacks") or []
    if not stacks:
        return None
    return stacks[0]


def _stack_outputs(stack: dict[str, Any] | None) -> dict[str, str]:
    if not stack:
        return {}
    outputs = stack.get("Outputs") or []
    return {str(item.get("OutputKey") or ""): str(item.get("OutputValue") or "") for item in outputs}


def _stack_parameters(stack: dict[str, Any] | None) -> dict[str, str]:
    if not stack:
        return {}
    params = stack.get("Parameters") or []
    return {str(item.get("ParameterKey") or ""): str(item.get("ParameterValue") or "") for item in params}


def _normalize_web_acl_id(raw_id: str) -> str:
    """
    CloudFormation returns a composite Ref for AWS::WAFv2::WebACL like:
      <name>|<uuid>|<scope>
    WAFv2 GetWebACL requires the UUID.
    """
    raw = str(raw_id or "").strip()
    if not raw:
        return ""
    if _UUID_RE.match(raw):
        return raw
    if "|" in raw:
        for part in (p.strip() for p in raw.split("|")):
            if _UUID_RE.match(part):
                return part
    return raw


def _describe_alarms(cw: Any, alarm_prefix: str) -> list[dict[str, Any]]:
    if not alarm_prefix:
        return []
    alarms: list[dict[str, Any]] = []
    paginator = cw.get_paginator("describe_alarms")
    for page in paginator.paginate(AlarmNamePrefix=alarm_prefix):
        for alarm in page.get("MetricAlarms") or []:
            alarms.append(
                {
                    "name": str(alarm.get("AlarmName") or ""),
                    "state": str(alarm.get("StateValue") or ""),
                    "reason": str(alarm.get("StateReason") or ""),
                    "metric": str(alarm.get("MetricName") or ""),
                    "namespace": str(alarm.get("Namespace") or ""),
                }
            )
    alarms.sort(key=lambda a: a["name"])
    return alarms


def _get_web_acl(waf: Any, name: str, web_acl_id: str, scope: str) -> dict[str, Any] | None:
    if not name or not web_acl_id or not scope:
        return None
    try:
        resp = waf.get_web_acl(Name=name, Id=web_acl_id, Scope=scope)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        return {"error": f"{code}: {exc}"}

    web_acl = resp.get("WebACL") or {}
    rules = web_acl.get("Rules") or []
    rule_summaries = []
    for rule in rules:
        rule_summaries.append(
            {
                "name": str(rule.get("Name") or ""),
                "priority": int(rule.get("Priority") or 0),
                "statement_keys": sorted(list((rule.get("Statement") or {}).keys())),
            }
        )
    rule_summaries.sort(key=lambda r: r["priority"])
    return {
        "name": str(web_acl.get("Name") or ""),
        "id": str(web_acl.get("Id") or ""),
        "arn": str(web_acl.get("ARN") or ""),
        "scope": scope,
        "default_action_keys": sorted(list((web_acl.get("DefaultAction") or {}).keys())),
        "rules": rule_summaries,
        "managed_by_stack": True,
    }


def _list_web_acl_resources(waf: Any, web_acl_arn: str, resource_type: str) -> dict[str, Any]:
    if not web_acl_arn:
        return {"resource_type": resource_type, "resource_arns": [], "error": "web_acl_arn_unavailable"}
    try:
        response = waf.list_resources_for_web_acl(WebACLArn=web_acl_arn, ResourceType=resource_type)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        return {"resource_type": resource_type, "resource_arns": [], "error": f"{code}: {exc}"}
    return {
        "resource_type": resource_type,
        "resource_arns": sorted([str(item) for item in (response.get("ResourceArns") or [])]),
        "error": "",
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Phase 3 Security Evidence Snapshot (SEC-010)")
    lines.append("")
    lines.append(f"Generated at: `{payload['generated_at']}`")
    lines.append(f"Region: `{payload['region']}`")
    identity = payload.get("identity") or {}
    lines.append(f"AWS Account: `{identity.get('account', 'unknown')}`")
    lines.append(f"AWS Arn: `{identity.get('arn', 'unknown')}`")
    lines.append("")

    stack = payload.get("stack") or {}
    lines.append("## Edge Stack Status")
    lines.append("")
    lines.append(f"- Name: `{stack.get('name', '')}`")
    lines.append(f"- Status: `{stack.get('status', 'NOT_FOUND')}`")
    lines.append(f"- Last Updated: `{stack.get('last_updated', '')}`")
    lines.append("")

    web_acl = payload.get("web_acl") or {}
    lines.append("## Web ACL Summary")
    lines.append("")
    if web_acl and not web_acl.get("error"):
        lines.append(f"- Name: `{web_acl.get('name', '')}`")
        lines.append(f"- Id: `{web_acl.get('id', '')}`")
        lines.append(f"- Arn: `{web_acl.get('arn', '')}`")
        lines.append(f"- Scope: `{web_acl.get('scope', '')}`")
        lines.append(f"- DefaultAction: `{web_acl.get('default_action_keys', [])}`")
        lines.append(f"- Rules: `{len(web_acl.get('rules', []))}`")
    elif web_acl.get("error"):
        lines.append(f"- Error: `{web_acl.get('error')}`")
    else:
        lines.append("- Web ACL not found in stack outputs (stack not deployed yet).")
    lines.append("")

    assoc = payload.get("associations") or {}
    lines.append("## Associations")
    lines.append("")
    lines.append(f"- Configured API Gateway Stage ARN: `{assoc.get('configured_api_gateway_stage_arn', '')}`")
    lines.append(f"- Configured ALB ARN: `{assoc.get('configured_alb_arn', '')}`")
    lines.append(f"- WAF API Gateway associations (list-resources-for-web-acl): `{assoc.get('api_gateway_resource_arns', [])}`")
    lines.append(f"- WAF ALB associations (list-resources-for-web-acl): `{assoc.get('alb_resource_arns', [])}`")

    verification = assoc.get("verification") or {}
    api_gateway_verify = verification.get("api_gateway") or {}
    alb_verify = verification.get("application_load_balancer") or {}
    if api_gateway_verify.get("error"):
        lines.append(f"- API Gateway verification error: `{api_gateway_verify.get('error')}`")
    if alb_verify.get("error"):
        lines.append(f"- ALB verification error: `{alb_verify.get('error')}`")
    lines.append("")

    alarms = payload.get("alarms") or []
    lines.append("## CloudWatch Alarms")
    lines.append("")
    if alarms:
        for alarm in alarms:
            lines.append(f"- `{alarm.get('name')}` state=`{alarm.get('state')}` metric=`{alarm.get('namespace')}/{alarm.get('metric')}`")
    else:
        lines.append("- No alarms found (or stack not deployed yet).")
    lines.append("")

    lines.append("## Artifact Files")
    lines.append("")
    lines.append(f"- JSON: `{payload['json_artifact_path']}`")
    lines.append(f"- Markdown: `{payload['markdown_artifact_path']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _build_parser().parse_args()

    session_kwargs: dict[str, Any] = {}
    if args.region:
        session_kwargs["region_name"] = args.region
    session = boto3.session.Session(**session_kwargs)
    region = session.region_name or "unknown"

    cf = session.client("cloudformation")
    waf = session.client("wafv2")
    cw = session.client("cloudwatch")
    sts = session.client("sts")

    identity_raw = sts.get_caller_identity()
    identity = {
        "account": str(identity_raw.get("Account") or ""),
        "arn": str(identity_raw.get("Arn") or ""),
        "user_id": str(identity_raw.get("UserId") or ""),
    }

    stack_raw = _describe_stack(cf, args.edge_stack)
    outputs = _stack_outputs(stack_raw)
    params = _stack_parameters(stack_raw)

    scope = str(args.scope or params.get("Scope") or "REGIONAL").strip() or "REGIONAL"
    web_acl_id = _normalize_web_acl_id(str(outputs.get("EdgeWebAclId") or "").strip())
    web_acl_name = str(outputs.get("EdgeWebAclName") or "").strip()
    web_acl = _get_web_acl(waf, web_acl_name, web_acl_id, scope)
    web_acl_arn = str((web_acl or {}).get("arn") or "")
    api_gateway_verify = _list_web_acl_resources(waf, web_acl_arn, "API_GATEWAY")
    alb_verify = _list_web_acl_resources(waf, web_acl_arn, "APPLICATION_LOAD_BALANCER")

    alarm_prefix = web_acl_name or "security-autopilot-edge-web-acl"
    alarms = _describe_alarms(cw, f"{alarm_prefix}-")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"phase3-security-{timestamp}.json"
    md_path = out_dir / f"phase3-security-{timestamp}.md"

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region": region,
        "identity": identity,
        "stack": {
            "name": args.edge_stack,
            "status": str(stack_raw.get("StackStatus") if stack_raw else "NOT_FOUND"),
            "last_updated": str(
                (stack_raw.get("LastUpdatedTime") or stack_raw.get("CreationTime") or "")
                if stack_raw
                else ""
            ),
        },
        "stack_outputs": outputs,
        "stack_parameters": params,
        "web_acl": web_acl or {},
        "associations": {
            "configured_api_gateway_stage_arn": str(
                outputs.get("ApiGatewayAssociationArn") or params.get("ApiGatewayStageArn") or ""
            ),
            "configured_alb_arn": str(
                outputs.get("ApplicationLoadBalancerAssociationArn")
                or params.get("ApplicationLoadBalancerArn")
                or ""
            ),
            "api_gateway_resource_arns": api_gateway_verify.get("resource_arns") or [],
            "alb_resource_arns": alb_verify.get("resource_arns") or [],
            "verification": {
                "api_gateway": api_gateway_verify,
                "application_load_balancer": alb_verify,
            },
        },
        "alarms": alarms,
        "json_artifact_path": str(json_path),
        "markdown_artifact_path": str(md_path),
    }

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")

    print(f"Wrote: {md_path}")
    print(f"Wrote: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
