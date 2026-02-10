terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "region" {
  description = "AWS region where foundational controls are intentionally misconfigured."
  type        = string
}

variable "name_prefix" {
  description = "Prefix used for naming foundational resources."
  type        = string
}

locals {
  sanitized_prefix     = trim(substr(replace(lower(var.name_prefix), "_", "-"), 0, 24), "-")
  config_recorder_name = "${local.sanitized_prefix}-recorder"
  config_channel_name  = "${local.sanitized_prefix}-delivery"
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "audit_logs" {
  bucket_prefix = "${local.sanitized_prefix}-audit-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "CloudTrailAclCheck"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.audit_logs.arn
      },
      {
        Sid       = "CloudTrailWrite"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.audit_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Sid       = "ConfigAclCheck"
        Effect    = "Allow"
        Principal = { Service = "config.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.audit_logs.arn
      },
      {
        Sid       = "ConfigBucketList"
        Effect    = "Allow"
        Principal = { Service = "config.amazonaws.com" }
        Action    = "s3:ListBucket"
        Resource  = aws_s3_bucket.audit_logs.arn
      },
      {
        Sid       = "ConfigWrite"
        Effect    = "Allow"
        Principal = { Service = "config.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.audit_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/Config/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      }
    ]
  })
}

resource "aws_cloudtrail" "regional_only" {
  name                          = "${local.sanitized_prefix}-regional-trail"
  s3_bucket_name                = aws_s3_bucket.audit_logs.id
  include_global_service_events = false
  is_multi_region_trail         = false
  enable_log_file_validation    = false
}

resource "aws_iam_role" "config_service_role" {
  name = "${local.sanitized_prefix}-config-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "config_managed_policy" {
  role       = aws_iam_role.config_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

resource "terraform_data" "ensure_config_non_compliant" {
  input = {
    region = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
export AWS_DEFAULT_REGION="${var.region}"
RECORDER_NAME="${local.config_recorder_name}"
CHANNEL_NAME="${local.config_channel_name}"
ROLE_ARN="${aws_iam_role.config_service_role.arn}"
S3_BUCKET="${aws_s3_bucket.audit_logs.id}"

existing_recorder=$(aws configservice describe-configuration-recorders --query 'ConfigurationRecorders[0].name' --output text 2>/dev/null || true)
if [[ -z "$existing_recorder" || "$existing_recorder" == "None" ]]; then
  aws configservice put-configuration-recorder \
    --configuration-recorder "{\"name\":\"$RECORDER_NAME\",\"roleARN\":\"$ROLE_ARN\",\"recordingGroup\":{\"allSupported\":true,\"includeGlobalResourceTypes\":true}}" \
    >/dev/null
  recorder_to_stop="$RECORDER_NAME"
else
  recorder_to_stop="$existing_recorder"
fi

existing_channel=$(aws configservice describe-delivery-channels --query 'DeliveryChannels[0].name' --output text 2>/dev/null || true)
if [[ -z "$existing_channel" || "$existing_channel" == "None" ]]; then
  aws configservice put-delivery-channel \
    --delivery-channel "{\"name\":\"$CHANNEL_NAME\",\"s3BucketName\":\"$S3_BUCKET\",\"s3KeyPrefix\":\"config\"}" \
    >/dev/null
fi

aws configservice stop-configuration-recorder --configuration-recorder-name "$recorder_to_stop" >/dev/null 2>&1 || true
echo "AWS Config recorder '$recorder_to_stop' is stopped in ${var.region}."
BASH
  }

  depends_on = [
    aws_iam_role_policy_attachment.config_managed_policy,
    aws_s3_bucket_policy.audit_logs
  ]
}

resource "terraform_data" "disable_security_hub" {
  input = {
    region = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
export AWS_DEFAULT_REGION="${var.region}"
aws securityhub disable-security-hub >/dev/null 2>&1 || true
echo "Security Hub disabled (or already disabled) in ${var.region}."
BASH
  }
}

resource "terraform_data" "delete_guardduty_detectors" {
  input = {
    region = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
export AWS_DEFAULT_REGION="${var.region}"
detectors=$(aws guardduty list-detectors --query 'DetectorIds[]' --output text 2>/dev/null || true)
if [[ -n "$detectors" ]]; then
  for detector in $detectors; do
    aws guardduty delete-detector --detector-id "$detector" >/dev/null 2>&1 || true
  done
fi
echo "GuardDuty detectors removed (or none existed) in ${var.region}."
BASH
  }
}

output "architecture_name" {
  value = "foundational_controls_gaps"
}

output "audit_bucket_name" {
  value = aws_s3_bucket.audit_logs.id
}

output "regional_cloudtrail_arn" {
  value = aws_cloudtrail.regional_only.arn
}

output "config_recorder_name" {
  value = local.config_recorder_name
}

output "config_delivery_channel_name" {
  value = local.config_channel_name
}
