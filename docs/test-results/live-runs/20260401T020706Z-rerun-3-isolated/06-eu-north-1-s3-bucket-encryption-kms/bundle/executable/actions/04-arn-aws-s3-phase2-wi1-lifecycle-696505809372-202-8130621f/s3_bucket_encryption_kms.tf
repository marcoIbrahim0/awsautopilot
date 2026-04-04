# S3 bucket SSE-KMS encryption - Action: 8130621f-9c7c-4b7c-83cb-9397fb14c7cd
# Remediation for: S3 bucket uses SSE-KMS by default
# Account: 696505809372 | Region: eu-north-1 | Bucket: phase2-wi1-lifecycle-696505809372-20260329004157
# Control: S3.15

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN to use for bucket default encryption (override for customer-managed key)"
  default     = "arn:aws:kms:eu-north-1:696505809372:alias/aws/s3"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {
  bucket = "phase2-wi1-lifecycle-696505809372-20260329004157"

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}
