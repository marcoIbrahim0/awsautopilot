# S3 bucket access logging - Action: 501021f0-ee39-4692-95c1-1d7c07134c71
# Remediation for: S3 general purpose buckets should have server access logging enabled
# Account: 696505809372 | Region: eu-north-1 | Bucket: security-autopilot-w6-envready-s311-exec-696505809372
# Control: S3.9

variable "source_bucket_name" {
  type        = string
  description = "S3 source bucket where server access logging is enabled"
  default     = "security-autopilot-w6-envready-s311-exec-696505809372"
}

variable "log_bucket_name" {
  type        = string
  description = "S3 bucket that will receive access logs"
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

    expiration {
      days = var.log_retention_days
    }
  }
}

data "aws_iam_policy_document" "log_delivery" {
  statement {
    sid    = "AllowS3ServerAccessLogs"
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
      values   = ["arn:aws:s3:::${var.source_bucket_name}"]
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


resource "aws_s3_bucket_logging" "security_autopilot" {
  bucket        = var.source_bucket_name
  target_bucket = var.log_bucket_name
  target_prefix = var.log_prefix
  depends_on = [
    aws_s3_bucket_policy.log_destination,
    aws_s3_bucket_server_side_encryption_configuration.log_destination,
  ]

}
