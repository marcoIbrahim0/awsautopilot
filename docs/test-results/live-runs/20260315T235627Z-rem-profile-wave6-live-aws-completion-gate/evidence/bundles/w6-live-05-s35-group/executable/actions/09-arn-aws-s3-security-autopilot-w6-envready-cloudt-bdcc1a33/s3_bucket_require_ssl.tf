# Enforce SSL-only S3 requests - Action: bdcc1a33-8d37-4d01-8ac8-5bfa39b11a1d
locals {
  target_bucket_name = "security-autopilot-w6-envready-cloudtrail-696505809372"
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
}
