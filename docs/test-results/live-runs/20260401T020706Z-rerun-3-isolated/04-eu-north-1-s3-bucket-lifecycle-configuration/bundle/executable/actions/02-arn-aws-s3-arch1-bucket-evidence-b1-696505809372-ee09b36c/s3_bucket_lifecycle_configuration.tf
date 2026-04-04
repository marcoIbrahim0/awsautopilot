# S3 bucket lifecycle configuration - Action: ee09b36c-33ad-4af9-8faa-92794fc7ebc1
# Remediation for: S3 bucket lifecycle rules configured
# Account: 696505809372 | Region: eu-north-1 | Bucket: arch1-bucket-evidence-b1-696505809372-eu-north-1
# Control: S3.11

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}

resource "aws_s3_bucket_lifecycle_configuration" "security_autopilot" {
  bucket = "arch1-bucket-evidence-b1-696505809372-eu-north-1"

  rule {
    id     = "security-autopilot-abort-incomplete-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_multipart_days
    }
  }
}
