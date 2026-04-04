# S3 bucket access logging - Action: f704085e-6481-4304-af67-d7358aa6de30
# Remediation for: S3 general purpose buckets should have server access logging enabled
# Account: 696505809372 | Region: eu-north-1 | Bucket: phase2-wi1-lifecycle-696505809372-20260328224331
# Control: S3.9

variable "source_bucket_name" {
  type        = string
  description = "S3 source bucket where server access logging is enabled"
  default     = "phase2-wi1-lifecycle-696505809372-20260328224331"
}

variable "log_bucket_name" {
  type        = string
  description = "S3 bucket that will receive access logs"
  default     = "phase2-wi1-lifecycle-696505809372-20260328224331-access-logs"
}

variable "create_log_bucket" {
  type        = bool
  description = "When true, create the destination bucket with the shared support-bucket baseline."
  default     = true
}

variable "log_prefix" {
  type        = string
  description = "Prefix for delivered access logs"
  default     = "s3-access-logs/"
}

resource "aws_s3_bucket" "access_logs" {
  count  = var.create_log_bucket ? 1 : 0
  bucket = var.log_bucket_name
}


resource "aws_s3_bucket_public_access_block" "access_logs" {
  count      = var.create_log_bucket ? 1 : 0
  bucket                  = aws_s3_bucket.access_logs[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
  depends_on = [aws_s3_bucket.access_logs]
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  count      = var.create_log_bucket ? 1 : 0
  bucket = aws_s3_bucket.access_logs[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = "alias/aws/s3"
    }
    bucket_key_enabled = true
  }
  depends_on = [aws_s3_bucket.access_logs]
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  count      = var.create_log_bucket ? 1 : 0
  bucket = aws_s3_bucket.access_logs[0].id

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
  depends_on = [aws_s3_bucket.access_logs]
}

data "aws_iam_policy_document" "ssl_only_access_logs" {

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      local.arn_prefix_access_logs,
      "${local.arn_prefix_access_logs}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

locals {
  arn_prefix_access_logs = "arn:aws:s3:::${var.log_bucket_name}"
}

resource "aws_s3_bucket_policy" "access_logs" {
  count      = var.create_log_bucket ? 1 : 0
  bucket = aws_s3_bucket.access_logs[0].id
  policy = data.aws_iam_policy_document.ssl_only_access_logs.json
  depends_on = [aws_s3_bucket.access_logs]
}


resource "aws_s3_bucket_logging" "security_autopilot" {
  bucket        = var.source_bucket_name
  target_bucket = var.log_bucket_name
  target_prefix = var.log_prefix
  depends_on    = [aws_s3_bucket_policy.access_logs]
}
