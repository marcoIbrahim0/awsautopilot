# Enforce SSL-only S3 requests - Action: 96bd1efb-91ee-4b22-9e1e-29613c8492aa
locals {
  target_bucket_name = "security-autopilot-access-logs-696505809372-r221001"
}

variable "exempt_principal_arns" {
  type        = list(string)
  default     = []
  description = "Optional IAM principal ARNs exempted from strict SSL deny."
}

data "aws_s3_bucket_policy" "existing" {
  bucket = local.target_bucket_name
}

locals {
  existing_policy_document = try(
    jsondecode(data.aws_s3_bucket_policy.existing.policy),
    {
      Version   = "2012-10-17"
      Statement = []
    }
  )
  existing_policy_id = try(local.existing_policy_document.Id, null)
  existing_policy_statements = try(local.existing_policy_document.Statement, [])
  filtered_existing_policy_statements = [
    for stmt in local.existing_policy_statements : stmt
    if !(
      lower(try(tostring(stmt.Sid), "")) == "denyinsecuretransport" ||
      (
        lower(try(tostring(stmt.Effect), "")) == "deny" &&
        lower(try(tostring(stmt.Condition.Bool["aws:SecureTransport"]), "")) == "false"
      )
    )
  ]
  filtered_existing_policy_document = merge(
    {
      Version   = try(tostring(local.existing_policy_document.Version), "2012-10-17")
      Statement = local.filtered_existing_policy_statements
    },
    local.existing_policy_id == null ? {} : { Id = local.existing_policy_id }
  )
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
  source_policy_documents   = [jsonencode(local.filtered_existing_policy_document)]
  override_policy_documents = [data.aws_iam_policy_document.required_ssl.json]
}

resource "aws_s3_bucket_policy" "security_autopilot" {
  bucket = local.target_bucket_name
  policy = data.aws_iam_policy_document.merged_policy.json
}
