# CloudTrail enabled - Action: 2ea6f141-6134-4dcd-8c82-4f0d0b6e582d
# Remediation for: CloudTrail should be enabled and configured with at least one multi-Region trail that includes read and write management events
# Account: 696505809372 | Region: eu-north-1
# Control: CloudTrail.1
# Review trail_bucket_name below. Toggle create_bucket_if_missing to create the bucket in this bundle.

variable "trail_bucket_name" {
  type        = string
  description = "S3 bucket name for CloudTrail logs."
  default     = "ocypheris-live-ct-20260323162333-eu-north-1"

}

variable "trail_name" {
  type        = string
  default     = "security-autopilot-trail"
  description = "CloudTrail trail name."
}

variable "create_bucket_if_missing" {
  type        = bool
  default     = true
  description = "When true, create the CloudTrail log bucket and baseline controls in this bundle."
}

variable "multi_region" {
  type        = bool
  default     = true
  description = "When true, enables multi-region CloudTrail logging."
}

variable "create_bucket_policy" {
  type        = bool
  default     = true
  description = "When true, create required CloudTrail S3 bucket policy statements."
}

variable "kms_key_arn" {
  type        = string
  default     = ""
  description = "Optional KMS key ARN for CloudTrail log encryption."
}

locals {
  cloudtrail_bucket_name = var.create_bucket_if_missing ? aws_s3_bucket.cloudtrail_logs[0].bucket : var.trail_bucket_name
  cloudtrail_bucket_arn  = "arn:aws:s3:::${local.cloudtrail_bucket_name}"
}

resource "aws_cloudtrail" "security_autopilot" {
  name                          = var.trail_name
  s3_bucket_name                = local.cloudtrail_bucket_name
  is_multi_region_trail          = var.multi_region
  include_global_service_events = true
  enable_logging                = true
  kms_key_id                    = var.kms_key_arn != "" ? var.kms_key_arn : null
  depends_on                    = [aws_s3_bucket_policy.cloudtrail_managed, null_resource.cloudtrail_bucket_policy]
}

variable "remediation_region" {
  type        = string
  default     = "eu-north-1"
  description = "Region used by local AWS CLI bucket-policy merge command."
}

data "aws_iam_policy_document" "cloudtrail_delivery" {
  statement {
    sid     = "AWSCloudTrailAclCheck"
    effect  = "Allow"
    actions = ["s3:GetBucketAcl"]

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    resources = [local.cloudtrail_bucket_arn]
  }

  statement {
    sid     = "AWSCloudTrailWrite"
    effect  = "Allow"
    actions = ["s3:PutObject"]

    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }

    resources = ["${local.cloudtrail_bucket_arn}/AWSLogs/696505809372/CloudTrail/*"]

    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }
}

resource "null_resource" "cloudtrail_bucket_policy" {
  count  = var.create_bucket_policy && !var.create_bucket_if_missing ? 1 : 0

  triggers = {
    trail_bucket_name  = var.trail_bucket_name
    remediation_region = var.remediation_region
    account_id         = "696505809372"
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
TRAIL_BUCKET_NAME="${var.trail_bucket_name}"
AWS_REGION="${var.remediation_region}"
ACCOUNT_ID="696505809372"
export TRAIL_BUCKET_NAME AWS_REGION ACCOUNT_ID
python3 - <<'PY'
import json
import os
import subprocess
import sys

bucket = os.environ["TRAIL_BUCKET_NAME"]
region = os.environ["AWS_REGION"]
account_id = os.environ["ACCOUNT_ID"]

def run(cmd):
    return subprocess.run(cmd, check=True, text=True, capture_output=True)

existing = {"Version": "2012-10-17", "Statement": []}
try:
    response = run(
        [
            "aws",
            "s3api",
            "get-bucket-policy",
            "--bucket",
            bucket,
            "--region",
            region,
            "--output",
            "json",
        ]
    )
    policy_doc = json.loads(response.stdout).get("Policy", "")
    if policy_doc:
        existing = json.loads(policy_doc)
except subprocess.CalledProcessError as exc:
    if "NoSuchBucketPolicy" not in (exc.stderr or ""):
        print(exc.stderr, file=sys.stderr)
        raise

statements = existing.get("Statement", [])
if not isinstance(statements, list):
    statements = []

preserved = [
    statement
    for statement in statements
    if statement.get("Sid") not in {"AWSCloudTrailAclCheck", "AWSCloudTrailWrite"}
]

preserved.append(
    {
        "Sid": "AWSCloudTrailAclCheck",
        "Effect": "Allow",
        "Principal": {"Service": "cloudtrail.amazonaws.com"},
        "Action": "s3:GetBucketAcl",
        "Resource": "arn:aws:s3:::" + bucket,
    }
)
preserved.append(
    {
        "Sid": "AWSCloudTrailWrite",
        "Effect": "Allow",
        "Principal": {"Service": "cloudtrail.amazonaws.com"},
        "Action": "s3:PutObject",
        "Resource": "arn:aws:s3:::" + bucket + "/AWSLogs/" + account_id + "/CloudTrail/*",
        "Condition": {"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}},
    }
)

merged = {
    "Version": existing.get("Version", "2012-10-17"),
    "Statement": preserved,
}
run(
    [
        "aws",
        "s3api",
        "put-bucket-policy",
        "--bucket",
        bucket,
        "--region",
        region,
        "--policy",
        json.dumps(merged, separators=(",", ":")),
    ]
)
PY
EOT
  }
}
resource "aws_s3_bucket" "cloudtrail_logs" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = var.trail_bucket_name
}

resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = aws_s3_bucket.cloudtrail_logs[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail_logs" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = aws_s3_bucket.cloudtrail_logs[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  count                   = var.create_bucket_if_missing ? 1 : 0
  bucket                  = aws_s3_bucket.cloudtrail_logs[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "cloudtrail_managed" {
  count  = var.create_bucket_policy && var.create_bucket_if_missing ? 1 : 0
  bucket = aws_s3_bucket.cloudtrail_logs[0].id
  policy = data.aws_iam_policy_document.cloudtrail_delivery.json
}

