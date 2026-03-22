# S3 bucket SSE-KMS encryption - Action: 7b9ca8b1-6e78-41ed-96b9-34af5d4a782a
# Remediation for: S3 general purpose buckets should be encrypted at rest with AWS KMS keys
# Account: 696505809372 | Region: eu-north-1 | Bucket: security-autopilot-w6-envready-s315-exec-696505809372
# Control: S3.15

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN to use for bucket default encryption (override for customer-managed key)"
  default     = "arn:aws:kms:eu-north-1:696505809372:alias/aws/s3"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {
  bucket = "security-autopilot-w6-envready-s315-exec-696505809372"

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}
