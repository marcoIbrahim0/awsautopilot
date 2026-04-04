# S3 bucket SSE-KMS encryption - Action: 15891d06-c639-4692-881d-05fdcca5d581
# Remediation for: S3 general purpose buckets should be encrypted at rest with AWS KMS keys
# Account: 696505809372 | Region: eu-north-1 | Bucket: ocypheris-live-ct-20260328t181200z-eu-north-1
# Control: S3.15

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN to use for bucket default encryption (override for customer-managed key)"
  default     = "arn:aws:kms:eu-north-1:696505809372:alias/aws/s3"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {
  bucket = "ocypheris-live-ct-20260328t181200z-eu-north-1"

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}
