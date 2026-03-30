# Shared S3 access logging destination setup
# Account: 696505809372
# Control: S3.9

variable "log_bucket_name" {
  type        = string
  description = "Shared S3 bucket that will receive server access logs"
  default     = "security-autopilot-access-logs-696505809372"
}

variable "log_prefix" {
  type        = string
  description = "Prefix for delivered access logs"
  default     = "s3-access-logs/"
}

variable "log_retention_days" {
  type        = number
  description = "Retention period in days for delivered server access logs"
  default     = 180
}

locals {
  allowed_source_bucket_arns = [
    "arn:aws:s3:::config-bucket-696505809372",
    "arn:aws:s3:::security-autopilot-w6-strict-s311-manual-696505809372",
    "arn:aws:s3:::security-autopilot-w6-envready-accesslogs-696505809372",
    "arn:aws:s3:::security-autopilot-w6-strict-s315-manual-696505809372",
    "arn:aws:s3:::security-autopilot-config-696505809372-eu-north-1",
    "arn:aws:s3:::security-autopilot-w6-envready-config-696505809372",
    "arn:aws:s3:::security-autopilot-w6-envready-s311-exec-696505809372",
    "arn:aws:s3:::security-autopilot-w6-strict-s315-exec-696505809372",
    "arn:aws:s3:::security-autopilot-w6-envready-cloudtrail-696505809372",
    "arn:aws:s3:::ocypheris-live-ct-20260323162333-eu-north-1",
    "arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372",
    "arn:aws:s3:::security-autopilot-w6-strict-s311-exec-696505809372",
    "arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372",
  ]
}

resource "aws_s3_bucket" "log_destination" {
  bucket = var.log_bucket_name
}

resource "aws_s3_bucket_public_access_block" "log_destination" {
  bucket                  = aws_s3_bucket.log_destination.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "log_destination" {
  bucket = aws_s3_bucket.log_destination.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "log_destination" {
  bucket = aws_s3_bucket.log_destination.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = var.log_retention_days
    }
  }
}

data "aws_iam_policy_document" "log_delivery" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["logging.s3.amazonaws.com"]
    }

    actions = ["s3:PutObject"]
    resources = [
      "arn:aws:s3:::${var.log_bucket_name}/${var.log_prefix}*",
    ]

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = local.allowed_source_bucket_arns
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = ["696505809372"]
    }
  }
}

resource "aws_s3_bucket_policy" "log_destination" {
  bucket = aws_s3_bucket.log_destination.id
  policy = data.aws_iam_policy_document.log_delivery.json
}
