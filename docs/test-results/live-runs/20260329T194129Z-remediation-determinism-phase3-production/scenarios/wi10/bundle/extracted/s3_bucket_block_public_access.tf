# S3 bucket public-policy scrub review bundle - Action: 688f5ed0-9594-4df1-9883-cc17feca62f8
# Remediation for: S3 general purpose buckets should block public access
# Account: 696505809372 | Region: eu-north-1 | Bucket: sa-wi13-14-nopolicy-696505809372-20260328201935
# Control: S3.2
# NOTE: Review this plan carefully. It removes only unconditional public Allow statements,
#       preserves Deny statements and conditional wildcard statements, and then enables
#       S3 Block Public Access on the bucket.

data "aws_s3_bucket_policy" "existing" {
  bucket = "sa-wi13-14-nopolicy-696505809372-20260328201935"
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
  existing_policy_statements_candidate = try(local.existing_policy_document.Statement, null)
  existing_policy_statements = jsondecode(
    local.existing_policy_statements_candidate == null ? "[]" : (
      can(local.existing_policy_statements_candidate.Effect) ? format(
        "[%s]",
        jsonencode(local.existing_policy_statements_candidate)
      ) : jsonencode(local.existing_policy_statements_candidate)
    )
  )
  existing_policy_statement_metadata = [
    for idx, statement in local.existing_policy_statements : {
      identifier = trimspace(try(tostring(statement.Sid), "")) != "" ? trimspace(tostring(statement.Sid)) : "statement-index-${idx}"
      statement  = statement
      remove = (
        lower(trimspace(try(tostring(statement.Effect), ""))) == "allow" &&
        !can(statement.Condition) &&
        (
          trimspace(try(tostring(statement.Principal), "")) == "*" ||
          trimspace(try(tostring(statement.Principal.AWS), "")) == "*" ||
          contains(
            [for identifier in try(statement.Principal.AWS, []) : trimspace(tostring(identifier))],
            "*"
          )
        )
      )
    }
  ]
  removed_statement_identifiers = [
    for item in local.existing_policy_statement_metadata : item.identifier
    if item.remove
  ]
  preserved_policy_statements = [
    for item in local.existing_policy_statement_metadata : item.statement
    if !item.remove
  ]
  scrubbed_policy_document = merge(
    {
      Version   = try(tostring(local.existing_policy_document.Version), "2012-10-17")
      Statement = local.preserved_policy_statements
    },
    local.existing_policy_id == null ? {} : { Id = local.existing_policy_id }
  )
}

resource "aws_s3_bucket_policy" "security_autopilot" {
  count  = length(local.preserved_policy_statements) > 0 ? 1 : 0
  bucket = "sa-wi13-14-nopolicy-696505809372-20260328201935"
  policy = jsonencode(local.scrubbed_policy_document)
}

resource "terraform_data" "delete_bucket_policy" {
  count = length(local.preserved_policy_statements) == 0 ? 1 : 0

  triggers_replace = {
    bucket_name            = "sa-wi13-14-nopolicy-696505809372-20260328201935"
    scrubbed_policy_sha256 = sha256(jsonencode(local.scrubbed_policy_document))
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
aws s3api delete-bucket-policy --bucket "sa-wi13-14-nopolicy-696505809372-20260328201935"
EOT
  }
}

resource "aws_s3_bucket_public_access_block" "security_autopilot" {
  bucket = "sa-wi13-14-nopolicy-696505809372-20260328201935"

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  depends_on = [
    aws_s3_bucket_policy.security_autopilot,
    terraform_data.delete_bucket_policy,
  ]
}

output "removed_statement_count" {
  value       = length(local.removed_statement_identifiers)
  description = "Number of unconditional public Allow statements removed before enabling Block Public Access."
}

output "removed_statement_identifiers" {
  value       = local.removed_statement_identifiers
  description = "Statement Sids or synthetic statement indexes removed by the scrub."
}
