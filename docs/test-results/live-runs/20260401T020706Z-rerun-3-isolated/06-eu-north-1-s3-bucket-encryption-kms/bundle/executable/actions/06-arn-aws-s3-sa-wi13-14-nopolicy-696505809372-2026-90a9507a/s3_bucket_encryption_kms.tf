# S3 bucket SSE-KMS encryption - Action: 90a9507a-7a74-4e6f-a2ff-b78712719388
# Remediation for: S3 general purpose buckets should be encrypted at rest with AWS KMS keys
# Account: 696505809372 | Region: eu-north-1 | Bucket: sa-wi13-14-nopolicy-696505809372-20260328201935
# Control: S3.15

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN to use for bucket default encryption (override for customer-managed key)"
  default     = "arn:aws:kms:eu-north-1:696505809372:alias/aws/s3"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {
  bucket = "sa-wi13-14-nopolicy-696505809372-20260328201935"

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}
