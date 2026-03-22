# S3 bucket lifecycle configuration - Action: e55dca93-6467-4dce-ba6c-16444f259760
# Remediation for: S3 general purpose buckets should have Lifecycle configurations
# Account: 696505809372 | Region: eu-north-1 | Bucket: config-bucket-696505809372
# Control: S3.11

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {
  bucket = "config-bucket-696505809372"

  rule {
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days
    }
  }
}
