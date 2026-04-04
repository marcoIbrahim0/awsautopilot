"""
Shared support-bucket baseline for product-created helper buckets.

Any remediation path that creates or reuses an internal support bucket
(S3.9 destination, CloudTrail.1 trail bucket, Config.1 delivery bucket)
MUST use the helpers in this module instead of hand-rolling per-family
bucket hardening.  This prevents the helper bucket itself from surfacing
as a new Security Hub finding after remediation.

Canonical baseline (six attributes):
  1. Public-access block  — all four flags enabled
  2. SSE-KMS encryption   — aws:kms + alias/aws/s3 (avoids S3.15 drift on AES256)
  3. SSL-only policy      — DenyInsecureTransport on s3:* for all principals
  4. Abort-incomplete     — lifecycle rule, 7-day window
  5. Log-retention        — optional expiration rule for log-sink buckets
  6. Versioning           — optional, required for CloudTrail/Config delivery buckets

Role-specific runtime hardening:
  - `aws-config-delivery` also enables EventBridge notifications and Object Lock
  - `cloudtrail-logs` and `aws-config-delivery` enable bucket versioning

Callers that need to apply additional service-write statements (e.g.
CloudTrail PutObject) must merge those statements *on top* of the
baseline — they must not replace it.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from botocore.exceptions import ClientError


# ---------------------------------------------------------------------------
# Canonical baseline profile (declares what "safe" means)
# ---------------------------------------------------------------------------

class SupportBucketBaselineProfile(TypedDict):
    """Required posture for all internal helper buckets."""

    public_access_block: bool
    ssl_only_policy: bool
    default_encryption: bool   # SSE-S3 or SSE-KMS counts; alias/aws/s3 preferred
    lifecycle_abort_incomplete: bool
    versioning_enabled: bool   # mandatory for log-retaining buckets


# Default KMS alias — AWS-managed S3 key; avoids S3.15 / KMS-key-rotation drift.
SUPPORT_BUCKET_KMS_MASTER_KEY_ID = "alias/aws/s3"
SUPPORT_BUCKET_SSE_ALGORITHM = "aws:kms"
SUPPORT_BUCKET_MANAGED_TAG_KEY = "security-autopilot:managed-support-bucket"
SUPPORT_BUCKET_MANAGED_TAG_VALUE = "true"
SUPPORT_BUCKET_ROLE_TAG_KEY = "security-autopilot:support-bucket-role"
SUPPORT_BUCKET_ROLE_S3_ACCESS_LOGS = "s3-access-logs"
SUPPORT_BUCKET_ROLE_CLOUDTRAIL_LOGS = "cloudtrail-logs"
SUPPORT_BUCKET_ROLE_AWS_CONFIG_DELIVERY = "aws-config-delivery"
SUPPORT_BUCKET_LOG_SINK_ROLES = frozenset(
    {
        SUPPORT_BUCKET_ROLE_S3_ACCESS_LOGS,
        SUPPORT_BUCKET_ROLE_CLOUDTRAIL_LOGS,
        SUPPORT_BUCKET_ROLE_AWS_CONFIG_DELIVERY,
    }
)

SUPPORT_BUCKET_BASELINE_PROFILE: SupportBucketBaselineProfile = {
    "public_access_block": True,
    "ssl_only_policy": True,
    "default_encryption": True,
    "lifecycle_abort_incomplete": True,
    "versioning_enabled": False,  # callers opt in for audit-log buckets
}


# ---------------------------------------------------------------------------
# Runtime probe result
# ---------------------------------------------------------------------------

class SupportBucketAttributeResult(TypedDict):
    """Result for one baseline attribute."""

    name: str
    passed: bool
    detail: str


class SupportBucketProbeResult(TypedDict):
    """Aggregated probe result for all baseline attributes of one bucket."""

    bucket_name: str
    safe: bool
    attributes: list[SupportBucketAttributeResult]
    raw: dict[str, Any]


def _attr(name: str, passed: bool, detail: str) -> SupportBucketAttributeResult:
    return {"name": name, "passed": passed, "detail": detail}


def _err(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", "")).strip() or "ClientError"


def support_bucket_tag_map(*, support_bucket_role: str) -> dict[str, str]:
    """Return the canonical tag map for a product-managed support bucket."""
    role = str(support_bucket_role or "").strip()
    if not role:
        raise ValueError("support_bucket_role is required")
    return {
        SUPPORT_BUCKET_MANAGED_TAG_KEY: SUPPORT_BUCKET_MANAGED_TAG_VALUE,
        SUPPORT_BUCKET_ROLE_TAG_KEY: role,
    }


def is_product_managed_support_bucket(tag_map: dict[str, str] | None) -> bool:
    if not isinstance(tag_map, dict):
        return False
    return str(tag_map.get(SUPPORT_BUCKET_MANAGED_TAG_KEY) or "").strip().lower() == SUPPORT_BUCKET_MANAGED_TAG_VALUE


def support_bucket_role_from_tags(tag_map: dict[str, str] | None) -> str | None:
    if not is_product_managed_support_bucket(tag_map):
        return None
    role = str((tag_map or {}).get(SUPPORT_BUCKET_ROLE_TAG_KEY) or "").strip()
    return role or None


def is_product_managed_support_log_sink(tag_map: dict[str, str] | None) -> bool:
    role = support_bucket_role_from_tags(tag_map)
    return role in SUPPORT_BUCKET_LOG_SINK_ROLES


# ---------------------------------------------------------------------------
# Runtime probe (uses a boto3 S3 client)
# ---------------------------------------------------------------------------

def probe_support_bucket_safety(
    s3_client: Any,
    bucket_name: str,
    *,
    check_versioning: bool = False,
) -> SupportBucketProbeResult:
    """
    Check baseline posture attributes on an existing support bucket.

    Returns a ``SupportBucketProbeResult``.  Callers should check ``safe``
    and use ``downgrade_reason()`` when switching to review_required_bundle.

    Args:
        s3_client:       Boto3 S3 client scoped to the correct account/region.
        bucket_name:     Bucket to probe.
        check_versioning: When True, also checks that versioning is Enabled.
    """
    attrs: list[SupportBucketAttributeResult] = []
    raw: dict[str, Any] = {}

    # 1. Ownership / reachability (early exit when unowned)
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as exc:
        attrs.append(_attr("bucket_owned", False, f"HeadBucket failed: {_err(exc)}"))
        return {"bucket_name": bucket_name, "safe": False, "attributes": attrs, "raw": raw}

    # 2. Public-access block
    try:
        block = s3_client.get_public_access_block(Bucket=bucket_name).get(
            "PublicAccessBlockConfiguration", {}
        )
        all_set = all(
            bool(block.get(k))
            for k in ("BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets")
        )
        raw["public_access_block"] = block
        attrs.append(_attr("public_access_block", all_set,
            "All four PAB flags enabled" if all_set else "One or more PAB flags missing"))
    except ClientError as exc:
        attrs.append(_attr("public_access_block", False, f"GetPublicAccessBlock: {_err(exc)}"))

    # 3. Default encryption (SSE-S3 or SSE-KMS both pass)
    try:
        rules = s3_client.get_bucket_encryption(Bucket=bucket_name).get(
            "ServerSideEncryptionConfiguration", {}
        ).get("Rules", [])
        has_enc = any(
            r.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") in ("AES256", "aws:kms")
            for r in rules
        )
        raw["encryption_rules"] = rules
        attrs.append(_attr("default_encryption", has_enc,
            "SSE enabled" if has_enc else "No SSE rule found"))
    except ClientError as exc:
        code = _err(exc)
        is_missing = code == "ServerSideEncryptionConfigurationNotFoundError"
        attrs.append(_attr("default_encryption", False,
            "No default encryption" if is_missing else f"GetBucketEncryption: {code}"))

    # 4. SSL-only deny policy
    try:
        policy_str = s3_client.get_bucket_policy(Bucket=bucket_name).get("Policy", "{}")
        raw["policy_present"] = bool(policy_str)
        has_ssl = _policy_enforces_ssl_only(policy_str)
        attrs.append(_attr("ssl_only_policy", has_ssl,
            "DenyInsecureTransport present" if has_ssl else "Missing DenyInsecureTransport statement"))
    except ClientError as exc:
        code = _err(exc)
        if code == "NoSuchBucketPolicy":
            attrs.append(_attr("ssl_only_policy", False, "No bucket policy — ssl-only absent"))
        else:
            attrs.append(_attr("ssl_only_policy", False, f"GetBucketPolicy: {code}"))

    # 5. AbortIncompleteMultipartUpload lifecycle rule
    try:
        lc_rules = s3_client.get_bucket_lifecycle_configuration(Bucket=bucket_name).get("Rules", [])
        raw["lifecycle_rule_count"] = len(lc_rules)
        has_abort = any(
            r.get("AbortIncompleteMultipartUpload") and r.get("Status") == "Enabled"
            for r in lc_rules
        )
        attrs.append(_attr("lifecycle_abort_incomplete", has_abort,
            "AbortIncomplete rule present" if has_abort else "Missing AbortIncompleteMultipartUpload rule"))
    except ClientError as exc:
        code = _err(exc)
        if code == "NoSuchLifecycleConfiguration":
            attrs.append(_attr("lifecycle_abort_incomplete", False, "No lifecycle configuration"))
        else:
            attrs.append(_attr("lifecycle_abort_incomplete", False, f"GetBucketLifecycleConfiguration: {code}"))

    # 6. Versioning (optional — only checked when caller requests it)
    if check_versioning:
        try:
            status = s3_client.get_bucket_versioning(Bucket=bucket_name).get("Status", "")
            enabled = str(status).strip() == "Enabled"
            raw["versioning_status"] = status
            attrs.append(_attr("versioning_enabled", enabled,
                "Versioning Enabled" if enabled else f"Versioning status: {status or 'Disabled'}"))
        except ClientError as exc:
            attrs.append(_attr("versioning_enabled", False, f"GetBucketVersioning: {_err(exc)}"))

    safe = all(a["passed"] for a in attrs)
    return {"bucket_name": bucket_name, "safe": safe, "attributes": attrs, "raw": raw}


def downgrade_reason(probe: SupportBucketProbeResult) -> str:
    """Return a one-line downgrade reason for the given probe result, or '' when safe."""
    failed = [a["name"] for a in probe["attributes"] if not a["passed"]]
    if not failed:
        return ""
    return (
        f"Support bucket '{probe['bucket_name']}' is missing required baseline "
        f"attributes: {', '.join(failed)}. Downgrading to review_required_bundle."
    )


# ---------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------

def _policy_enforces_ssl_only(policy_json: str | None) -> bool:
    """Return True when the policy contains a DenyInsecureTransport statement."""
    if not isinstance(policy_json, str) or not policy_json.strip():
        return False
    try:
        parsed = json.loads(policy_json)
    except ValueError:
        return False
    statements = parsed.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    for stmt in statements if isinstance(statements, list) else []:
        if not isinstance(stmt, dict):
            continue
        if str(stmt.get("Effect", "")).lower() != "deny":
            continue
        condition = stmt.get("Condition", {})
        secure = condition.get("Bool", {}).get("aws:SecureTransport")
        if str(secure).strip().lower() == "false":
            return True
    return False


def ssl_only_policy_statement(bucket_name: str) -> dict[str, Any]:
    """Return a canonical DenyInsecureTransport statement for the given bucket."""
    return {
        "Sid": "DenyInsecureTransport",
        "Effect": "Deny",
        "Principal": "*",
        "Action": "s3:*",
        "Resource": [
            f"arn:aws:s3:::{bucket_name}",
            f"arn:aws:s3:::{bucket_name}/*",
        ],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
    }


def merge_ssl_only_into_policy(
    existing_policy_json: str | None,
    bucket_name: str,
) -> str:
    """
    Return a JSON policy string with DenyInsecureTransport merged in.

    Any existing statement with Sid == 'DenyInsecureTransport' is replaced
    with the canonical version. Other statements are preserved.
    """
    if existing_policy_json and existing_policy_json.strip() not in ("", "None", "null"):
        try:
            doc = json.loads(existing_policy_json)
        except ValueError:
            doc = {}
    else:
        doc = {}
    version = doc.get("Version") or "2012-10-17"
    stmts = list(doc.get("Statement") or [])
    stmts = [s for s in stmts if not (isinstance(s, dict) and s.get("Sid") == "DenyInsecureTransport")]
    stmts.append(ssl_only_policy_statement(bucket_name))
    return json.dumps({"Version": version, "Statement": stmts}, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Terraform resource-block generator
# ---------------------------------------------------------------------------

def terraform_support_bucket_blocks(
    *,
    resource_suffix: str,
    bucket_id_ref: str,
    bucket_name_ref: str,
    count_expr: str | None = None,
    enable_versioning: bool = False,
    log_retention_days: int | None = None,
    service_write_data_source: str | None = None,
    support_bucket_role: str | None = None,
) -> str:
    """
    Return Terraform HCL resource blocks that fully harden a support bucket.

    This generates the six baseline resources and a merged bucket policy.
    Callers must NOT define their own ``aws_s3_bucket_public_access_block``,
    ``aws_s3_bucket_server_side_encryption_configuration``,
    ``aws_s3_bucket_lifecycle_configuration``, or ``aws_s3_bucket_policy``
    for the same resource suffix — use this function instead.

    Args:
        resource_suffix:          Suffix for every resource label (e.g. ``log_destination``).
        bucket_id_ref:            Terraform expr for the **id** (e.g. ``aws_s3_bucket.log_destination[0].id``).
        bucket_name_ref:          Terraform expr for the **name** (e.g. ``var.log_bucket_name``).
        count_expr:               Optional Terraform count expression (e.g. ``var.create_log_bucket ? 1 : 0``).
        enable_versioning:        Add aws_s3_bucket_versioning with status = Enabled.
        log_retention_days:       When set, add an expiration lifecycle rule.
        service_write_data_source: When set (e.g. ``data.aws_iam_policy_document.cloudtrail_delivery``),
                                  use it as a ``source_policy_documents`` input so the SSL-only
                                  deny is merged with the service-write statements in one policy resource.
    """
    count_line = f"  count      = {count_expr}\n" if count_expr else ""
    dep = f"aws_s3_bucket.{resource_suffix}" if count_expr else ""
    dep_line = f"  depends_on = [{dep}]\n" if dep else ""

    versioning_block = ""
    if enable_versioning:
        versioning_block = f"""
resource "aws_s3_bucket_versioning" "{resource_suffix}" {{
{count_line}  bucket = {bucket_id_ref}

  versioning_configuration {{
    status = "Enabled"
  }}
{dep_line}}}
"""

    retention_rule = ""
    if log_retention_days is not None:
        retention_rule = f"""
  rule {{
    id     = "expire-support-logs"
    status = "Enabled"
    filter {{}}
    expiration {{
      days = {log_retention_days}
    }}
  }}
"""

    source_docs = ""
    if service_write_data_source:
        source_docs = f"  source_policy_documents = [{service_write_data_source}.json]\n"

    tagging_block = ""
    if support_bucket_role:
        tag_set_blocks = "\n".join(
            [
                "  tag_set {",
                f'    key   = "{SUPPORT_BUCKET_MANAGED_TAG_KEY}"',
                f'    value = "{SUPPORT_BUCKET_MANAGED_TAG_VALUE}"',
                "  }",
                "  tag_set {",
                f'    key   = "{SUPPORT_BUCKET_ROLE_TAG_KEY}"',
                f'    value = "{support_bucket_role}"',
                "  }",
            ]
        )
        tagging_block = f"""

resource "aws_s3_bucket_tagging" "{resource_suffix}" {{
{count_line}  bucket = {bucket_id_ref}

{tag_set_blocks}
{dep_line}}}
"""

    return f"""
resource "aws_s3_bucket_public_access_block" "{resource_suffix}" {{
{count_line}  bucket                  = {bucket_id_ref}
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
{dep_line}}}

resource "aws_s3_bucket_server_side_encryption_configuration" "{resource_suffix}" {{
{count_line}  bucket = {bucket_id_ref}

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm     = "{SUPPORT_BUCKET_SSE_ALGORITHM}"
      kms_master_key_id = "{SUPPORT_BUCKET_KMS_MASTER_KEY_ID}"
    }}
    bucket_key_enabled = true
  }}
{dep_line}}}

resource "aws_s3_bucket_lifecycle_configuration" "{resource_suffix}" {{
{count_line}  bucket = {bucket_id_ref}

  rule {{
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {{}}
    abort_incomplete_multipart_upload {{
      days_after_initiation = 7
    }}
  }}
{retention_rule}{dep_line}}}

data "aws_iam_policy_document" "ssl_only_{resource_suffix}" {{
{source_docs}
  statement {{
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      local.arn_prefix_{resource_suffix},
      "${{local.arn_prefix_{resource_suffix}}}/*",
    ]
    principals {{
      type        = "*"
      identifiers = ["*"]
    }}
    condition {{
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }}
  }}
}}

locals {{
  arn_prefix_{resource_suffix} = "arn:aws:s3:::${{{bucket_name_ref.replace('"', '')}}}"
}}

resource "aws_s3_bucket_policy" "{resource_suffix}" {{
{count_line}  bucket = {bucket_id_ref}
  policy = data.aws_iam_policy_document.ssl_only_{resource_suffix}.json
{dep_line}}}
{versioning_block}{tagging_block}"""


# ---------------------------------------------------------------------------
# Python apply-snippet (embedded in apply/restore helper scripts in bundles)
# ---------------------------------------------------------------------------

SUPPORT_BUCKET_APPLY_SNIPPET: str = '''
def apply_support_bucket_baseline(bucket: str, region: str, helper_bucket_role: str | None = None) -> None:
    """Apply the canonical support-bucket baseline via AWS CLI (idempotent).

    Applies in order: public-access block → SSE-KMS → lifecycle
    → helper-bucket tags → SSL-only policy merged with any existing statements.
    """
    import json as _json
    import subprocess
    import tempfile
    from pathlib import Path

    def _run(args: list) -> None:
        r = subprocess.run(args, text=True, capture_output=True)
        if r.returncode != 0:
            raise SystemExit(f"{' '.join(args)}: {r.stderr.strip() or r.stdout.strip()}")

    # 1. Public-access block
    _run([
        "aws", "s3api", "put-public-access-block",
        "--bucket", bucket, "--region", region,
        "--public-access-block-configuration",
        "BlockPublicAcls=true,IgnorePublicAcls=true,"
        "BlockPublicPolicy=true,RestrictPublicBuckets=true",
    ])

    # 2. SSE-KMS with AWS-managed S3 key (alias/aws/s3 avoids S3.15 drift)
    sse = _json.dumps({
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "aws:kms",
                "KMSMasterKeyID": "alias/aws/s3",
            },
            "BucketKeyEnabled": True,
        }]
    })
    _run([
        "aws", "s3api", "put-bucket-encryption",
        "--bucket", bucket, "--region", region,
        "--server-side-encryption-configuration", sse,
    ])

    # 3. Lifecycle: abort-incomplete-multipart (7 days)
    # NOTE: this replaces any existing lifecycle configuration.
    # Callers that need to preserve existing rules must read + merge first.
    lc = _json.dumps({
        "Rules": [{
            "ID": "abort-incomplete-multipart",
            "Status": "Enabled",
            "Filter": {},
            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
        }]
    })
    _run([
        "aws", "s3api", "put-bucket-lifecycle-configuration",
        "--bucket", bucket, "--region", region,
        "--lifecycle-configuration", lc,
    ])

    # 4. Role-specific baseline extensions
    if helper_bucket_role in ("cloudtrail-logs", "aws-config-delivery"):
        _run([
            "aws", "s3api", "put-bucket-versioning",
            "--bucket", bucket, "--region", region,
            "--versioning-configuration", "Status=Enabled",
        ])

    if helper_bucket_role == "aws-config-delivery":
        notifications = _json.dumps({"EventBridgeConfiguration": {}})
        _run([
            "aws", "s3api", "put-bucket-notification-configuration",
            "--bucket", bucket, "--region", region,
            "--notification-configuration", notifications,
        ])
        object_lock = _json.dumps({"ObjectLockEnabled": "Enabled"})
        _run([
            "aws", "s3api", "put-object-lock-configuration",
            "--bucket", bucket, "--region", region,
            "--object-lock-configuration", object_lock,
        ])

    # 5. Product-managed helper tags — only when the caller declares a helper role
    if helper_bucket_role:
        tagging = _json.dumps({
            "TagSet": [
                {
                    "Key": "security-autopilot:managed-support-bucket",
                    "Value": "true",
                },
                {
                    "Key": "security-autopilot:support-bucket-role",
                    "Value": helper_bucket_role,
                },
            ]
        })
        _run([
            "aws", "s3api", "put-bucket-tagging",
            "--bucket", bucket, "--region", region,
            "--tagging", tagging,
        ])

    # 6. SSL-only deny policy — merged with any existing statements
    get_r = subprocess.run(
        ["aws", "s3api", "get-bucket-policy",
         "--bucket", bucket, "--region", region,
         "--query", "Policy", "--output", "text"],
        text=True, capture_output=True,
    )
    existing_stmts: list = []
    if get_r.returncode == 0:
        raw = (get_r.stdout or "").strip()
        if raw and raw not in ("None", "null"):
            try:
                existing_stmts = _json.loads(raw).get("Statement", [])
            except (ValueError, AttributeError):
                pass
    ssl_stmt = {
        "Sid": "DenyInsecureTransport",
        "Effect": "Deny",
        "Principal": "*",
        "Action": "s3:*",
        "Resource": [
            f"arn:aws:s3:::{bucket}",
            f"arn:aws:s3:::{bucket}/*",
        ],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
    }
    merged_stmts = [
        s for s in existing_stmts if s.get("Sid") != "DenyInsecureTransport"
    ] + [ssl_stmt]
    policy = _json.dumps({"Version": "2012-10-17", "Statement": merged_stmts})
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(policy)
        tmp = f.name
    try:
        _run([
            "aws", "s3api", "put-bucket-policy",
            "--bucket", bucket, "--region", region,
            "--policy", f"file://{tmp}",
        ])
    finally:
        Path(tmp).unlink(missing_ok=True)
'''
