# Enforce SSL-only S3 requests - Action: e4662826-a8f8-4574-a468-120b6af7520b
variable "remediation_region" {
  type        = string
  default     = "eu-north-1"
  description = "Region used by local AWS CLI bucket-policy merge command."
}

resource "null_resource" "s3_ssl_policy_merge" {
  triggers = {
    target_bucket      = "phase2-live-c2-c4-s35-234636z-029037611564"
    remediation_region = var.remediation_region
    exempt_principals  = ""
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
TARGET_BUCKET="phase2-live-c2-c4-s35-234636z-029037611564"
AWS_REGION="${var.remediation_region}"
export TARGET_BUCKET AWS_REGION
python3 - <<'PY'
import json
import os
import subprocess
import sys

bucket = os.environ["TARGET_BUCKET"]
region = os.environ["AWS_REGION"]
exempt_principals = []

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
    if statement.get("Sid") not in {"DenyInsecureTransport", "AllowExemptPrincipals"}
]
preserved.append(
    {
        "Sid": "DenyInsecureTransport",
        "Effect": "Deny",
        "Principal": "*",
        "Action": "s3:*",
        "Resource": [
            "arn:aws:s3:::" + bucket,
            "arn:aws:s3:::" + bucket + "/*",
        ],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
    }
)
if exempt_principals:
    preserved.append(
        {
            "Sid": "AllowExemptPrincipals",
            "Effect": "Allow",
            "Principal": {"AWS": exempt_principals},
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::" + bucket,
                "arn:aws:s3:::" + bucket + "/*",
            ],
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
