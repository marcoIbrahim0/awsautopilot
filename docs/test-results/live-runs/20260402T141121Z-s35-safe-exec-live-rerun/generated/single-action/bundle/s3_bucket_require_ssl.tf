# Enforce SSL-only S3 requests - Action: 3970aa2f-edc5-4870-87bd-fa986dad3d98
locals {
  target_bucket_name = "arch1-bucket-evidence-b1-696505809372-eu-north-1"
}

variable "create_bucket_if_missing" {
  type        = bool
  default     = false
  description = "When true, create the target bucket with a minimal private baseline before enforcing SSL-only requests."
}

variable "existing_bucket_policy_json" {
  type        = string
  default     = ""
  description = "Optional existing bucket policy JSON for merge-safe preservation."
}

variable "exempt_principal_arns" {
  type        = list(string)
  default     = []
  description = "Optional IAM principal ARNs exempted from strict SSL deny."
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

resource "aws_s3_bucket_server_side_encryption_configuration" "target_bucket" {
  count  = var.create_bucket_if_missing ? 1 : 0
  bucket = aws_s3_bucket.target_bucket[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = "alias/aws/s3"
    }
    bucket_key_enabled = true
  }

  depends_on = [aws_s3_bucket_public_access_block.target_bucket]
}


data "aws_iam_policy_document" "required_ssl" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::${local.target_bucket_name}",
      "arn:aws:s3:::${local.target_bucket_name}/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  dynamic "statement" {
    for_each = length(var.exempt_principal_arns) == 0 ? [] : [var.exempt_principal_arns]
    content {
      sid    = "AllowExemptPrincipals"
      effect = "Allow"
      principals {
        type        = "AWS"
        identifiers = statement.value
      }
      actions = ["s3:*"]
      resources = [
        "arn:aws:s3:::${local.target_bucket_name}",
        "arn:aws:s3:::${local.target_bucket_name}/*",
      ]
    }
  }
}

data "aws_iam_policy_document" "merged_policy" {
  source_policy_documents   = var.existing_bucket_policy_json == "" ? [] : [var.existing_bucket_policy_json]
  override_policy_documents = [data.aws_iam_policy_document.required_ssl.json]
}

resource "aws_s3_bucket_policy" "security_autopilot" {
  bucket = local.target_bucket_name
  policy = data.aws_iam_policy_document.merged_policy.json
  depends_on = [aws_s3_bucket_ownership_controls.target_bucket]
}
