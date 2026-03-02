# S3 bucket control hardening (Block Public Access) - Action: 232870db-8f7d-49ee-8361-8ad1bd79eff2
# Remediation for: S3 general purpose buckets should be encrypted at rest with AWS KMS keys
# Account: 029037611564 | Region: eu-north-1 | Bucket: arch1-bucket-website-a1-029037611564-eu-north-1
# Control: S3.2
# NOTE: This is NOT a full CloudFront + OAC + private S3 migration.
#       Review dependent consumers and bucket policy/KMS requirements before apply.

resource "aws_s3_bucket_public_access_block" "security_autopilot" {
  bucket = "arch1-bucket-website-a1-029037611564-eu-north-1"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
