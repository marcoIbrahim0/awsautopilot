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
  default     = "eu-north-1"
}

variable "trail_name" {
  description = "Name for the intentionally non-compliant CloudTrail trail."
  type        = string
  default     = "security-autopilot-foundational-noncompliant-trail"
}

variable "cloudtrail_log_bucket_name" {
  description = "Optional globally unique S3 bucket name for CloudTrail logs. Leave empty to auto-generate."
  type        = string
  default     = ""
}

locals {
  use_generated_bucket_name = trimspace(var.cloudtrail_log_bucket_name) == ""
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket        = local.use_generated_bucket_name ? null : var.cloudtrail_log_bucket_name
  bucket_prefix = local.use_generated_bucket_name ? "security-autopilot-ct-foundation-" : null
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSCloudTrailAclCheck"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.cloudtrail_logs.arn
      },
      {
        Sid       = "AWSCloudTrailWrite"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.cloudtrail_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
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
  name                          = var.trail_name
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = false
  is_multi_region_trail         = false
  enable_log_file_validation    = false
}

resource "terraform_data" "disable_security_hub" {
  input = { region = var.region }

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
  input = { region = var.region }

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

resource "terraform_data" "stop_config_recorders" {
  input = { region = var.region }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
export AWS_DEFAULT_REGION="${var.region}"
recorders=$(aws configservice describe-configuration-recorders --query 'ConfigurationRecorders[].name' --output text 2>/dev/null || true)
if [[ -n "$recorders" ]]; then
  for recorder in $recorders; do
    aws configservice stop-configuration-recorder --configuration-recorder-name "$recorder" >/dev/null 2>&1 || true
  done
fi
echo "AWS Config recorders stopped (or none existed) in ${var.region}."
BASH
  }
}

output "foundational_controls_architecture" {
  value = {
    cloudtrail_arn                   = aws_cloudtrail.regional_only.arn
    cloudtrail_log_bucket            = aws_s3_bucket.cloudtrail_logs.id
    securityhub_control_status       = "disabled_or_not_enabled"
    guardduty_detector_status        = "none"
    config_recorder_recording_status = "stopped_or_missing"
  }
}
