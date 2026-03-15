# CloudTrail enabled - Action: 4c4f4b3b-90d5-4682-a94a-1cfdc673bdc6
# Remediation for: CloudTrail should be enabled and configured with at least one multi-Region trail that includes read and write management events
# Account: 696505809372 | Region: eu-north-1
# Control: CloudTrail.1
# Create an S3 bucket for trail logs and set trail_bucket_name below.

variable "trail_bucket_name" {
  type        = string
  description = "S3 bucket name for CloudTrail logs (create the bucket if it does not exist)"
  default     = "config-bucket-696505809372"

}

variable "trail_name" {
  type        = string
  default     = "security-autopilot-trail"
  description = "CloudTrail trail name."
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

resource "aws_cloudtrail" "security_autopilot" {
  name                          = var.trail_name
  s3_bucket_name                = var.trail_bucket_name
  is_multi_region_trail          = var.multi_region
  include_global_service_events = true
  enable_logging                = true
  kms_key_id                    = var.kms_key_arn != "" ? var.kms_key_arn : null
  depends_on                    = [null_resource.cloudtrail_bucket_policy]
}

variable "remediation_region" {
  type        = string
  default     = "eu-north-1"
  description = "Region used by local AWS CLI bucket-policy merge command."
}

resource "null_resource" "cloudtrail_bucket_policy" {
  count  = var.create_bucket_policy ? 1 : 0

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

