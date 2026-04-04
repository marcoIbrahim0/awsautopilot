# S3 bucket SSE-KMS encryption - Action: 00000000-0000-0000-0000-000000000015
# Remediation for: S3 buckets should have default encryption enabled with SSE-KMS
# Account: 696505809372 | Region: eu-north-1 | Bucket: phase2-wi1-lifecycle-696505809372-20260329004157
# Control: S3.15

locals {
  target_bucket_name = "phase2-wi1-lifecycle-696505809372-20260329004157"
}

variable "create_bucket_if_missing" {
  type        = bool
  description = "When true, create the target bucket with a minimal private baseline before enforcing SSE-KMS."
  default     = false
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN to use for bucket default encryption (override for customer-managed key)"
  default     = "arn:aws:kms:eu-north-1:696505809372:alias/aws/s3"
}


resource "aws_s3_bucket" "target_bucket" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = local.target_bucket_name
}

resource "aws_s3_bucket_ownership_controls" "target_bucket" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = aws_s3_bucket.target_bucket[0].id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "target_bucket" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = aws_s3_bucket.target_bucket[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  depends_on = [aws_s3_bucket_ownership_controls.target_bucket]
}


resource "aws_s3_bucket_server_side_encryption_configuration" "security_autopilot" {
  bucket = local.target_bucket_name
  depends_on = [aws_s3_bucket_server_side_encryption_configuration.target_bucket]

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}
