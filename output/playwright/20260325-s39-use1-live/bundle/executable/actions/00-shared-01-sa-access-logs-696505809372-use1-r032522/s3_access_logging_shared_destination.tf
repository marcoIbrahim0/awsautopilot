# Shared S3 access logging destination setup
# Account: 696505809372
# Control: S3.9

variable "log_bucket_name" {
  type        = string
  description = "Shared S3 bucket that will receive server access logs"
  default     = "sa-access-logs-696505809372-use1-r0325225420"
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

variable "create_log_bucket" {
  type        = bool
  description = "Whether this shared setup should create the destination bucket or reuse an existing owned bucket"
  default     = true
}

locals {
  allowed_source_bucket_arns = [
    "arn:aws:s3:::security-autopilot-config-696505809372-us-east-1",
  ]
}

resource "aws_s3_bucket" "log_destination" {
  count  = var.create_log_bucket ? 1 : 0
  bucket = var.log_bucket_name
}

resource "aws_s3_bucket_public_access_block" "log_destination" {
  bucket                  = var.log_bucket_name
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
  depends_on              = [aws_s3_bucket.log_destination]
}

resource "aws_s3_bucket_server_side_encryption_configuration" "log_destination" {
  bucket = var.log_bucket_name

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
  depends_on = [aws_s3_bucket.log_destination]
}

resource "aws_s3_bucket_lifecycle_configuration" "log_destination" {
  bucket = var.log_bucket_name

  rule {
    id     = "expire-access-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = var.log_retention_days
    }
  }
  depends_on = [aws_s3_bucket.log_destination]
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
  bucket = var.log_bucket_name
  policy = data.aws_iam_policy_document.log_delivery.json
  depends_on = [aws_s3_bucket.log_destination]
}
