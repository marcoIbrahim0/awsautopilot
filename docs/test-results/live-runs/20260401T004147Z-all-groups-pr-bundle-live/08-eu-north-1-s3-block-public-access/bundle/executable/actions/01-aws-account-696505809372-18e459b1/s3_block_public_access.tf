# S3 Block Public Access (account-level) - Action: 18e459b1-3bc2-47b4-a520-c955e921c75f
# Remediation for: S3 general purpose buckets should have block public access settings enabled
# Account: 696505809372
# Control: S3.1

resource "aws_s3_account_public_access_block" "security_autopilot" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
