# S3 bucket lifecycle configuration - Action: 53cda243-1815-4864-8cc3-f3e1535a4ff1
# Remediation for: S3 general purpose buckets should have Lifecycle configurations
# Account: 696505809372 | Region: eu-north-1 | Bucket: ocypheris-live-ct-20260323162333-eu-north-1
# Control: S3.11

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {
  bucket = "ocypheris-live-ct-20260323162333-eu-north-1"

  rule {
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days
    }
  }
}
