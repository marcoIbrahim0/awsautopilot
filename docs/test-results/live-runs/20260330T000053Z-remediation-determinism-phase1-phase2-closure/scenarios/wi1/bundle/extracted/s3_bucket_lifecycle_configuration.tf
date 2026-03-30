# S3 bucket lifecycle configuration - Action: 8d9e8cc1-949a-412d-8db0-98923b513518
# Remediation for: S3 bucket lifecycle rules configured
# Account: 696505809372 | Region: eu-north-1 | Bucket: wi1-noncurrent-lifecycle-696505809372-20260330003655
# Control: S3.11

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {
  bucket = "wi1-noncurrent-lifecycle-696505809372-20260330003655"

  rule {
    id     = "noncurrent-expiration-only"
    status = "Enabled"
    # Preserved from captured lifecycle configuration.
    filter {
      prefix = ""
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days
    }
  }
}
