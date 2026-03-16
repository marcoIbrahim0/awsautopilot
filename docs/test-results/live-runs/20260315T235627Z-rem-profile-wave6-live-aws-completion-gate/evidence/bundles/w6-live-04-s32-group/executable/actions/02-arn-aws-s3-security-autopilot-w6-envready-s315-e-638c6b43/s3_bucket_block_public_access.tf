# S3 bucket control hardening (Block Public Access) - Action: 638c6b43-32ab-4104-a1da-29be5cd9a35a
# Remediation for: S3 general purpose buckets should block public access
# Account: 696505809372 | Region: eu-north-1 | Bucket: security-autopilot-w6-envready-s315-exec-696505809372
# Control: S3.2
# NOTE: This is NOT a full CloudFront + OAC + private S3 migration.
#       Review dependent consumers and bucket policy/KMS requirements before apply.

resource "aws_s3_bucket_public_access_block" "security_autopilot" {
  bucket = "security-autopilot-w6-envready-s315-exec-696505809372"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
