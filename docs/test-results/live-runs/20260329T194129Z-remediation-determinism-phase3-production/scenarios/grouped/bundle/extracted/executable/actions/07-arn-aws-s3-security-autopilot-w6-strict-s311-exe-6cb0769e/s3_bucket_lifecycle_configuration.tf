# S3 bucket lifecycle configuration - Action: 6cb0769e-5bd2-48cf-a4c8-0ea00684f44d
# Remediation for: S3 general purpose buckets should have Lifecycle configurations
# Account: 696505809372 | Region: eu-north-1 | Bucket: security-autopilot-w6-strict-s311-exec-696505809372
# Control: S3.11

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {
  bucket = "security-autopilot-w6-strict-s311-exec-696505809372"

  rule {
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days
    }
  }
}
