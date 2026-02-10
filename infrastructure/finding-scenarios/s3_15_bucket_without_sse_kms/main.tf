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
  bucket_prefix = local.use_generated_bucket_name ? "security-autopilot-s3-15-" : null
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "locked_down" {
  bucket = aws_s3_bucket.vulnerable.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Intentionally sets SSE-S3 rather than SSE-KMS to target Security Hub S3.15.
resource "aws_s3_bucket_server_side_encryption_configuration" "sse_s3" {
  bucket = aws_s3_bucket.vulnerable.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

output "vulnerable_bucket_name" {
  value = aws_s3_bucket.vulnerable.id
}

