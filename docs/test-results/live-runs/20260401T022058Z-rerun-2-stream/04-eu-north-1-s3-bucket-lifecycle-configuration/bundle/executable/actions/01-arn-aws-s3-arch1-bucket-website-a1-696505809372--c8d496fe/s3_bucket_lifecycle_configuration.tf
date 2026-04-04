# S3 bucket lifecycle configuration - Action: c8d496fe-3431-4a44-bc08-74646b5f2572
# Remediation for: S3 bucket lifecycle rules configured
# Account: 696505809372 | Region: eu-north-1 | Bucket: arch1-bucket-website-a1-696505809372-eu-north-1
# Control: S3.11

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {
  bucket = "arch1-bucket-website-a1-696505809372-eu-north-1"

  rule {
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days
    }
  }
}
