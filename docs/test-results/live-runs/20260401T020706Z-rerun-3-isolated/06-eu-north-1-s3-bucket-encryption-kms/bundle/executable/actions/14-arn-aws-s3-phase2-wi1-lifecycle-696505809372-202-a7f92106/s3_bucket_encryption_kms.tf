# S3 bucket SSE-KMS encryption - Action: a7f92106-2df8-4768-aac0-358250abdb7b
# Remediation for: S3 general purpose buckets should be encrypted at rest with AWS KMS keys
# Account: 696505809372 | Region: eu-north-1 | Bucket: phase2-wi1-lifecycle-696505809372-20260329002042
# Control: S3.15

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN to use for bucket default encryption (override for customer-managed key)"
  default     = "arn:aws:kms:eu-north-1:696505809372:alias/aws/s3"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {
  bucket = "phase2-wi1-lifecycle-696505809372-20260329002042"

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}
