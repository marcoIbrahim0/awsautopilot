# S3 bucket SSE-KMS encryption - Action: 39732b9a-956a-4deb-913d-d652cad22526
# Remediation for: S3 bucket uses SSE-KMS by default
# Account: 696505809372 | Region: eu-north-1 | Bucket: wi1-noncurrent-lifecycle-696505809372-20260330003655
# Control: S3.15

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN to use for bucket default encryption (override for customer-managed key)"
  default     = "arn:aws:kms:eu-north-1:696505809372:alias/aws/s3"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {
  bucket = "wi1-noncurrent-lifecycle-696505809372-20260330003655"

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}
