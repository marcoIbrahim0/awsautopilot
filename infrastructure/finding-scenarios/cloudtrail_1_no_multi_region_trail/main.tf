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
  description = "AWS region where the non-compliant trail is created."
  type        = string
  default     = "eu-north-1"
}

variable "trail_name" {
  description = "CloudTrail name."
  type        = string
  default     = "security-autopilot-noncompliant-trail"
}

variable "log_bucket_name" {
  description = "Optional globally unique S3 bucket name used for CloudTrail logs. Leave empty to auto-generate."
  type        = string
  default     = ""
}

locals {
  use_generated_bucket_name = trimspace(var.log_bucket_name) == ""
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "trail_logs" {
  bucket        = local.use_generated_bucket_name ? null : var.log_bucket_name
  bucket_prefix = local.use_generated_bucket_name ? "security-autopilot-ct-1-" : null
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "trail_logs" {
  bucket = aws_s3_bucket.trail_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "trail_logs" {
  bucket = aws_s3_bucket.trail_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSCloudTrailAclCheck"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.trail_logs.arn
      },
      {
        Sid       = "AWSCloudTrailWrite"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.trail_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      }
    ]
  })
}

resource "aws_cloudtrail" "non_compliant" {
  name                          = var.trail_name
  s3_bucket_name                = aws_s3_bucket.trail_logs.id
  include_global_service_events = false
  is_multi_region_trail         = false
  enable_log_file_validation    = false
}

output "non_compliant_trail_arn" {
  value = aws_cloudtrail.non_compliant.arn
}
