#!/usr/bin/env python3
"""
Security Autopilot — CloudFront/OAC adopt-or-create discovery helper.
"""
from __future__ import annotations

import json
import subprocess
import sys

SECURITY_AUTOPILOT_COMMENT_PREFIX = "Security Autopilot migration for "


def fail(message: str) -> None:
    raise SystemExit(message)


def read_query() -> dict[str, str]:
    query = json.load(sys.stdin)
    fields = {
        "bucket_name": str(query.get("bucket_name") or "").strip(),
        "expected_bucket_regional_domain_name": str(
            query.get("expected_bucket_regional_domain_name") or ""
        ).strip(),
        "expected_distribution_comment": str(query.get("expected_distribution_comment") or "").strip(),
        "expected_oac_name": str(query.get("expected_oac_name") or "").strip(),
        "expected_origin_id": str(query.get("expected_origin_id") or "").strip(),
    }
    missing = [name for name, value in fields.items() if not value]
    if missing:
        fail(f"Missing required discovery inputs: {', '.join(sorted(missing))}")
    return fields


def run_aws(*args: str) -> dict[str, object]:
    result = subprocess.run(
        ["aws", *args, "--output", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "AWS CLI command failed"
        fail(f"AWS CLI error: {message}")
    output = (result.stdout or "").strip() or "{}"
    return json.loads(output)


def list_distributions() -> list[dict[str, object]]:
    payload = run_aws("cloudfront", "list-distributions")
    dist_list = payload.get("DistributionList")
    items = dist_list.get("Items") if isinstance(dist_list, dict) else []
    return [item for item in items if isinstance(item, dict)]


def list_oacs() -> list[dict[str, object]]:
    payload = run_aws("cloudfront", "list-origin-access-controls")
    oac_list = payload.get("OriginAccessControlList")
    items = oac_list.get("Items") if isinstance(oac_list, dict) else []
    return [item for item in items if isinstance(item, dict)]


def distribution_origins(distribution: dict[str, object]) -> list[dict[str, object]]:
    origins = distribution.get("Origins")
    items = origins.get("Items") if isinstance(origins, dict) else []
    return [item for item in items if isinstance(item, dict)]


def matches_bucket_distribution(
    distribution: dict[str, object],
    *,
    expected_comment: str,
    expected_domain: str,
    expected_origin_id: str,
) -> bool:
    comment = str(distribution.get("Comment") or "").strip()
    if not comment.startswith(SECURITY_AUTOPILOT_COMMENT_PREFIX):
        return False
    if comment == expected_comment:
        return True
    return any(
        str(origin.get("DomainName") or "").strip() == expected_domain
        or str(origin.get("Id") or "").strip() == expected_origin_id
        for origin in distribution_origins(distribution)
    )


def validate_distribution(
    distribution: dict[str, object],
    *,
    expected_comment: str,
    expected_domain: str,
    expected_origin_id: str,
    oacs_by_id: dict[str, dict[str, object]],
) -> dict[str, str]:
    comment = str(distribution.get("Comment") or "").strip()
    if comment != expected_comment:
        fail(
            "Existing Security Autopilot CloudFront distribution for this bucket has an unexpected "
            f"comment: {comment!r}."
        )
    matching_origins = [
        origin
        for origin in distribution_origins(distribution)
        if str(origin.get("DomainName") or "").strip() == expected_domain
        and str(origin.get("Id") or "").strip() == expected_origin_id
    ]
    if len(matching_origins) != 1:
        fail(
            "Existing Security Autopilot CloudFront distribution for this bucket does not have exactly "
            "one matching S3 origin."
        )
    origin = matching_origins[0]
    oac_id = str(origin.get("OriginAccessControlId") or "").strip()
    if not oac_id:
        fail("Existing Security Autopilot CloudFront distribution is missing OriginAccessControlId.")
    oac = oacs_by_id.get(oac_id)
    if oac is None:
        fail(f"Existing CloudFront distribution references unknown OAC {oac_id}.")
    if str(oac.get("OriginAccessControlOriginType") or "").strip().lower() != "s3":
        fail(f"Existing OAC {oac_id} is not an S3 OAC.")
    if str(oac.get("SigningBehavior") or "").strip().lower() != "always":
        fail(f"Existing OAC {oac_id} does not use signing_behavior=always.")
    if str(oac.get("SigningProtocol") or "").strip().lower() != "sigv4":
        fail(f"Existing OAC {oac_id} does not use signing_protocol=sigv4.")
    return {
        "mode": "reuse_distribution",
        "distribution_id": str(distribution.get("Id") or "").strip(),
        "distribution_arn": str(distribution.get("ARN") or "").strip(),
        "distribution_domain_name": str(distribution.get("DomainName") or "").strip(),
        "oac_id": oac_id,
        "oac_name": str(oac.get("Name") or "").strip(),
    }


def oac_attachment_ids(oac_id: str, distributions: list[dict[str, object]]) -> list[str]:
    attached: list[str] = []
    for distribution in distributions:
        for origin in distribution_origins(distribution):
            if str(origin.get("OriginAccessControlId") or "").strip() == oac_id:
                attached.append(str(distribution.get("Id") or "").strip())
                break
    return sorted(item for item in attached if item)


def validate_named_oac(
    expected_oac_name: str,
    oacs: list[dict[str, object]],
    distributions: list[dict[str, object]],
) -> dict[str, str]:
    matches = [oac for oac in oacs if str(oac.get("Name") or "").strip() == expected_oac_name]
    if not matches:
        return {"mode": "create"}
    if len(matches) != 1:
        fail(f"Multiple existing OACs already use the intended name {expected_oac_name!r}.")
    oac = matches[0]
    oac_id = str(oac.get("Id") or "").strip()
    if str(oac.get("OriginAccessControlOriginType") or "").strip().lower() != "s3":
        fail(f"Existing OAC {expected_oac_name!r} is not an S3 OAC.")
    if str(oac.get("SigningBehavior") or "").strip().lower() != "always":
        fail(f"Existing OAC {expected_oac_name!r} does not use signing_behavior=always.")
    if str(oac.get("SigningProtocol") or "").strip().lower() != "sigv4":
        fail(f"Existing OAC {expected_oac_name!r} does not use signing_protocol=sigv4.")
    attachments = oac_attachment_ids(oac_id, distributions)
    if attachments:
        fail(
            f"Existing OAC {expected_oac_name!r} is already attached to other CloudFront distributions: "
            f"{', '.join(attachments)}."
        )
    return {
        "mode": "reuse_oac_only",
        "oac_id": oac_id,
        "oac_name": expected_oac_name,
    }


def main() -> None:
    query = read_query()
    distributions = list_distributions()
    oacs = list_oacs()
    oacs_by_id = {
        str(oac.get("Id") or "").strip(): oac
        for oac in oacs
        if str(oac.get("Id") or "").strip()
    }

    matching_distributions = [
        distribution
        for distribution in distributions
        if matches_bucket_distribution(
            distribution,
            expected_comment=query["expected_distribution_comment"],
            expected_domain=query["expected_bucket_regional_domain_name"],
            expected_origin_id=query["expected_origin_id"],
        )
    ]
    if len(matching_distributions) > 1:
        fail(
            "Multiple existing Security Autopilot CloudFront distributions appear to target this bucket; "
            "manual review is required before reuse."
        )
    if matching_distributions:
        result = validate_distribution(
            matching_distributions[0],
            expected_comment=query["expected_distribution_comment"],
            expected_domain=query["expected_bucket_regional_domain_name"],
            expected_origin_id=query["expected_origin_id"],
            oacs_by_id=oacs_by_id,
        )
        print(json.dumps(result))
        return

    result = validate_named_oac(
        query["expected_oac_name"],
        oacs,
        distributions,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
