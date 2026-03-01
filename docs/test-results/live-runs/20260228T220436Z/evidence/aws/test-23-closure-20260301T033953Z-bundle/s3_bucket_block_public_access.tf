# S3 bucket control hardening (Block Public Access) - Action: 26403d52-eff4-47ce-ab52-49bd237e72f5
# Remediation for: S3 general purpose buckets should block public read access
# Account: 029037611564 | Region: eu-north-1 | Bucket: arch1-bucket-evidence-b1-029037611564-eu-north-1
# Control: S3.2
# NOTE: This is NOT a full CloudFront + OAC + private S3 migration.
#       Review dependent consumers and bucket policy/KMS requirements before apply.

resource "aws_s3_bucket_public_access_block" "security_autopilot" {
  bucket = "arch1-bucket-evidence-b1-029037611564-eu-north-1"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
