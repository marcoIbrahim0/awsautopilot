# CloudTrail enabled - Action: 5d8dc746-b3a8-4df8-b931-b2fa5468eff8
# Remediation for: Enable CloudTrail
# Account: 029037611564 | Region: eu-north-1
# Control: CloudTrail.1
# Create an S3 bucket for trail logs and set trail_bucket_name below.

variable "trail_bucket_name" {
  type        = string
  description = "S3 bucket name for CloudTrail logs (create the bucket if it does not exist)"
}

variable "create_bucket_policy" {
  type        = bool
  default     = true
  description = "When true, create required CloudTrail S3 bucket policy statements."
}

resource "aws_cloudtrail" "security_autopilot" {
  name                          = "security-autopilot-trail"
  s3_bucket_name                = var.trail_bucket_name
  is_multi_region_trail          = true
  include_global_service_events = true
  enable_logging                = true
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
    account_id         = "029037611564"
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
TRAIL_BUCKET_NAME="${var.trail_bucket_name}"
AWS_REGION="${var.remediation_region}"
ACCOUNT_ID="029037611564"
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

