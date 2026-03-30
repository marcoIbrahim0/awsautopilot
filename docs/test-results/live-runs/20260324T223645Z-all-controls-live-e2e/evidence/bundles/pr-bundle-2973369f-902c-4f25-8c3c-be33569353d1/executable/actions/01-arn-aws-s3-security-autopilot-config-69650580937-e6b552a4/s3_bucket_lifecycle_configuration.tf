# S3 bucket lifecycle configuration - Action: e6b552a4-4461-4de5-9a7b-15ff0a1b4485
# Remediation for: S3 general purpose buckets should have Lifecycle configurations
# Account: 696505809372 | Region: us-east-1 | Bucket: security-autopilot-config-696505809372-us-east-1
# Control: S3.11

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {
  bucket = "security-autopilot-config-696505809372-us-east-1"

  rule {
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days
    }
  }
}
