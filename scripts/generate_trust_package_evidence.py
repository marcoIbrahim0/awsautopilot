#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import boto3

from backend.services.trust_package_artifacts import (
    build_sanitized_assume_role_events,
    redact_external_id,
    render_read_role_documents,
    render_write_role_documents,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ISSUE2_RUN = PROJECT_ROOT / "docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "docs/test-results/trust-package"
READ_ROLE_TEMPLATE = PROJECT_ROOT / "infrastructure/cloudformation/read-role-template.yaml"
WRITE_ROLE_TEMPLATE = PROJECT_ROOT / "infrastructure/cloudformation/write-role-template.yaml"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a buyer-safe trust package evidence bundle.")
    parser.add_argument("--region", default="eu-north-1", help="AWS region for Access Analyzer and CloudTrail lookups.")
    parser.add_argument(
        "--authoritative-run-dir",
        default=str(DEFAULT_ISSUE2_RUN),
        help="Existing retained live run used as the customer-side authoritative source.",
    )
    parser.add_argument(
        "--cloudtrail-max-results",
        type=int,
        default=50,
        help="Maximum CloudTrail AssumeRole events to inspect from the SaaS account.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Optional explicit output directory. Defaults to docs/test-results/trust-package/<timestamp>-buyer-trust-package.",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _latest_matching_file(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No files matched {pattern} under {root}.")
    return matches[-1]


def _authoritative_source_inputs(run_dir: Path) -> dict[str, Any]:
    evidence_root = run_dir / "evidence/aws"
    role_doc = _load_json(_latest_matching_file(evidence_root, "read-role-after-v*.json"))
    stack_doc = _load_json(_latest_matching_file(evidence_root, "read-role-stack-after-v*.json"))
    stack = stack_doc["Stacks"][0]
    parameters = {item["ParameterKey"]: item["ParameterValue"] for item in stack["Parameters"]}
    trust_statement = role_doc["Role"]["AssumeRolePolicyDocument"]["Statement"][0]
    return {
        "authoritative_run_dir": str(run_dir),
        "customer_account_id": stack["StackId"].split(":")[4],
        "customer_read_role_arn": role_doc["Role"]["Arn"],
        "customer_read_role_name": role_doc["Role"]["RoleName"],
        "customer_stack_name": stack["StackName"],
        "customer_stack_last_updated_at": stack["LastUpdatedTime"],
        "saas_account_id": parameters["SaaSAccountId"],
        "saas_execution_role_arns": parameters.get("SaaSExecutionRoleArns", ""),
        "external_id": trust_statement["Condition"]["StringEquals"]["sts:ExternalId"],
    }


def _access_analyzer_validation(
    region: str,
    *,
    policy_document: Mapping[str, Any],
    policy_type: str,
    resource_type: str | None = None,
) -> dict[str, Any]:
    client = boto3.client("accessanalyzer", region_name=region)
    request = {
        "policyDocument": json.dumps(policy_document),
        "policyType": policy_type,
    }
    if resource_type:
        request["validatePolicyResourceType"] = resource_type
    response = client.validate_policy(**request)
    findings = response.get("findings", [])
    return {
        "policy_type": policy_type,
        "resource_type": resource_type,
        "finding_count": len(findings),
        "findings": findings,
    }


def _cloudtrail_lookup(region: str, max_results: int) -> list[dict[str, Any]]:
    client = boto3.client("cloudtrail", region_name=region)
    response = client.lookup_events(
        LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "AssumeRole"}],
        MaxResults=max_results,
    )
    return response.get("Events", [])


def _default_output_dir(output_dir: str) -> Path:
    if output_dir:
        return Path(output_dir).expanduser().resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (DEFAULT_OUTPUT_ROOT / f"{timestamp}-buyer-trust-package").resolve()


def _package_readme(
    *,
    repo_template_version: str,
    customer_account_id: str,
    customer_role_arn: str,
    cloudtrail_event_count: int,
    source_run_dir: str,
) -> str:
    return "\n".join(
        [
            "# Buyer Trust Package Evidence",
            "",
            "This package was generated from the current repo-shipped ReadRole template plus sanitized live/retained evidence.",
            "",
            f"- Repo ReadRole template version: `{repo_template_version}`",
            f"- Customer account in retained authoritative source: `{customer_account_id}`",
            f"- Customer ReadRole ARN in retained authoritative source: `{customer_role_arn}`",
            f"- Fresh sanitized CloudTrail AssumeRole matches captured: `{cloudtrail_event_count}`",
            f"- Customer-side authoritative source run: `{source_run_dir}`",
            "",
            "## Contents",
            "",
            "- `rendered/` — current repo-rendered policy documents derived from the checked-in CloudFormation template",
            "- `validation/` — fresh IAM Access Analyzer validation output for the current ReadRole and the deprecated WriteRole appendix",
            "- `evidence/` — sanitized customer-side retained evidence and fresh SaaS-side CloudTrail AssumeRole extracts",
            "- `summary.json` — machine-readable index of the generated package",
        ]
    ) + "\n"


def main() -> None:
    args = _parse_args()
    output_dir = _default_output_dir(args.output_dir)
    source_inputs = _authoritative_source_inputs(Path(args.authoritative_run_dir).resolve())
    rendered = render_read_role_documents(
        READ_ROLE_TEMPLATE,
        saas_account_id=source_inputs["saas_account_id"],
        external_id=source_inputs["external_id"],
        saas_execution_role_arns=source_inputs["saas_execution_role_arns"],
    )
    write_rendered = render_write_role_documents(
        WRITE_ROLE_TEMPLATE,
        saas_account_id=source_inputs["saas_account_id"],
        external_id=source_inputs["external_id"],
        saas_execution_role_arns=source_inputs["saas_execution_role_arns"],
    )
    rendered_trust_policy = redact_external_id(rendered["trust_policy"])
    rendered_identity_policy = rendered["identity_policy"]
    write_rendered_trust_policy = redact_external_id(write_rendered["trust_policy"])
    write_rendered_identity_policy = write_rendered["identity_policy"]
    trust_validation = _access_analyzer_validation(
        args.region,
        policy_document=rendered["trust_policy"],
        policy_type="RESOURCE_POLICY",
        resource_type="AWS::IAM::AssumeRolePolicyDocument",
    )
    identity_validation = _access_analyzer_validation(
        args.region,
        policy_document=rendered_identity_policy,
        policy_type="IDENTITY_POLICY",
    )
    write_trust_validation = _access_analyzer_validation(
        args.region,
        policy_document=write_rendered["trust_policy"],
        policy_type="RESOURCE_POLICY",
        resource_type="AWS::IAM::AssumeRolePolicyDocument",
    )
    write_identity_validation = _access_analyzer_validation(
        args.region,
        policy_document=write_rendered_identity_policy,
        policy_type="IDENTITY_POLICY",
    )
    cloudtrail_events = _cloudtrail_lookup(args.region, args.cloudtrail_max_results)
    sanitized_assume_role_events = build_sanitized_assume_role_events(
        cloudtrail_events,
        role_arn=source_inputs["customer_read_role_arn"],
    )
    authoritative_role_doc = _load_json(_latest_matching_file(Path(args.authoritative_run_dir) / "evidence/aws", "read-role-after-v*.json"))
    authoritative_role_doc["Role"]["AssumeRolePolicyDocument"] = redact_external_id(
        authoritative_role_doc["Role"]["AssumeRolePolicyDocument"]
    )
    stack_summary = {
        "stack_name": source_inputs["customer_stack_name"],
        "stack_last_updated_at": source_inputs["customer_stack_last_updated_at"],
        "customer_account_id": source_inputs["customer_account_id"],
        "customer_read_role_arn": source_inputs["customer_read_role_arn"],
        "saas_account_id": source_inputs["saas_account_id"],
        "saas_execution_role_arns": source_inputs["saas_execution_role_arns"].split(","),
        "external_id": "<REDACTED_EXTERNAL_ID>",
    }

    _write_json(output_dir / "rendered/read-role-trust-policy.json", rendered_trust_policy)
    _write_json(output_dir / "rendered/read-role-identity-policy.json", rendered_identity_policy)
    _write_json(output_dir / "rendered/write-role-trust-policy.json", write_rendered_trust_policy)
    _write_json(output_dir / "rendered/write-role-identity-policy.json", write_rendered_identity_policy)
    _write_json(
        output_dir / "rendered/template-metadata.json",
        {
            "repo_template_path": str(READ_ROLE_TEMPLATE),
            "repo_template_version": rendered["template_version"],
            "deprecated_write_role_template_path": str(WRITE_ROLE_TEMPLATE),
            "deprecated_write_role_template_version": write_rendered["template_version"],
            "saas_account_id": source_inputs["saas_account_id"],
            "saas_execution_role_arns": source_inputs["saas_execution_role_arns"].split(","),
            "external_id": "<REDACTED_EXTERNAL_ID>",
        },
    )
    _write_json(output_dir / "validation/read-role-trust-policy-access-analyzer.json", trust_validation)
    _write_json(output_dir / "validation/read-role-identity-policy-access-analyzer.json", identity_validation)
    _write_json(output_dir / "validation/write-role-trust-policy-access-analyzer.json", write_trust_validation)
    _write_json(output_dir / "validation/write-role-identity-policy-access-analyzer.json", write_identity_validation)
    _write_json(output_dir / "evidence/aws/cloudtrail-assumerole-sanitized.json", sanitized_assume_role_events)
    _write_json(output_dir / "evidence/aws/authoritative-live-read-role-redacted.json", authoritative_role_doc)
    _write_json(output_dir / "evidence/aws/authoritative-live-stack-summary.json", stack_summary)
    _write_json(
        output_dir / "summary.json",
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "repo_template_version": rendered["template_version"],
            "deprecated_write_role_template_version": write_rendered["template_version"],
            "authoritative_run_dir": source_inputs["authoritative_run_dir"],
            "cloudtrail_event_count": len(sanitized_assume_role_events),
            "trust_policy_finding_count": trust_validation["finding_count"],
            "identity_policy_finding_count": identity_validation["finding_count"],
            "deprecated_write_role_trust_policy_finding_count": write_trust_validation["finding_count"],
            "deprecated_write_role_identity_policy_finding_count": write_identity_validation["finding_count"],
        },
    )
    (output_dir / "README.md").write_text(
        _package_readme(
            repo_template_version=rendered["template_version"],
            customer_account_id=source_inputs["customer_account_id"],
            customer_role_arn=source_inputs["customer_read_role_arn"],
            cloudtrail_event_count=len(sanitized_assume_role_events),
            source_run_dir=source_inputs["authoritative_run_dir"],
        ),
        encoding="utf-8",
    )
    print(output_dir)


if __name__ == "__main__":
    main()
