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
  description = "AWS region where the vulnerable bucket is created."
  type        = string
  default     = "eu-north-1"
}

variable "bucket_name" {
  description = "Optional globally unique S3 bucket name. Leave empty to auto-generate."
  type        = string
  default     = ""
}

provider "aws" {
  region = var.region
}

locals {
  use_generated_bucket_name = trimspace(var.bucket_name) == ""
}

resource "aws_s3_bucket" "vulnerable" {
  bucket        = local.use_generated_bucket_name ? null : var.bucket_name
  bucket_prefix = local.use_generated_bucket_name ? "security-autopilot-s3-5-" : null
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "locked_down" {
  bucket = aws_s3_bucket.vulnerable.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Intentionally does NOT include a "Deny aws:SecureTransport = false" statement.
# This aims to trigger Security Hub S3.5 (require SSL-only requests).
resource "aws_s3_bucket_policy" "no_ssl_deny" {
  bucket = aws_s3_bucket.vulnerable.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowAccountRootList"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.vulnerable.arn
      }
    ]
  })
}

data "aws_caller_identity" "current" {}

output "vulnerable_bucket_name" {
  value = aws_s3_bucket.vulnerable.id
}

