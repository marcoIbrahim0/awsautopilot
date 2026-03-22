# S3 bucket lifecycle configuration - Action: c533dff3-a0f0-4d76-8dd3-19315fb3e47d
# Remediation for: S3 general purpose buckets should have Lifecycle configurations
# Account: 696505809372 | Region: eu-north-1 | Bucket: security-autopilot-w6-strict-s315-exec-696505809372
# Control: S3.11

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {
  bucket = "security-autopilot-w6-strict-s315-exec-696505809372"

  rule {
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days
    }
  }
}
