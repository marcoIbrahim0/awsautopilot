# S3 bucket SSE-KMS encryption - Action: b74b1748-222a-44f5-bd02-93d1e3ea5d34
# Remediation for: S3 general purpose buckets should be encrypted at rest with AWS KMS keys
# Account: 696505809372 | Region: eu-north-1 | Bucket: security-autopilot-access-logs-696505809372-r222018
# Control: S3.15

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN to use for bucket default encryption (override for customer-managed key)"
  default     = "arn:aws:kms:eu-north-1:696505809372:alias/aws/s3"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {
  bucket = "security-autopilot-access-logs-696505809372-r222018"

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}
