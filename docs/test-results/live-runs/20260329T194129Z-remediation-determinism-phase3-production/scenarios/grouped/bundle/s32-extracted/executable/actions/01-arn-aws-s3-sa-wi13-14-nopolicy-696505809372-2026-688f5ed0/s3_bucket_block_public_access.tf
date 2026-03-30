# S3 bucket control hardening (Block Public Access) - Action: 688f5ed0-9594-4df1-9883-cc17feca62f8
# Remediation for: S3 general purpose buckets should block public access
# Account: 696505809372 | Region: eu-north-1 | Bucket: sa-wi13-14-nopolicy-696505809372-20260328201935
# Control: S3.2
# NOTE: This is NOT a full CloudFront + OAC + private S3 migration.
#       Review dependent consumers and bucket policy/KMS requirements before apply.

resource "aws_s3_bucket_public_access_block" "security_autopilot" {
  bucket = "sa-wi13-14-nopolicy-696505809372-20260328201935"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
