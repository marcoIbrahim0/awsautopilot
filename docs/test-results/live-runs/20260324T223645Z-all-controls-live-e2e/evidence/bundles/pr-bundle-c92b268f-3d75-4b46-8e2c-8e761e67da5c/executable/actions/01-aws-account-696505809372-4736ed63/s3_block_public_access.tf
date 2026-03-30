# S3 Block Public Access (account-level) - Action: 4736ed63-fa17-45ea-ab33-5b7c514b31f4
# Remediation for: S3 general purpose buckets should have block public access settings enabled
# Account: 696505809372
# Control: S3.1

resource "aws_s3_account_public_access_block" "security_autopilot" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
