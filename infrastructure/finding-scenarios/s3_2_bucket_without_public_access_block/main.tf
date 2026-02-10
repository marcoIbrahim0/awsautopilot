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

locals {
  use_generated_bucket_name = trimspace(var.bucket_name) == ""
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "vulnerable" {
  bucket        = local.use_generated_bucket_name ? null : var.bucket_name
  bucket_prefix = local.use_generated_bucket_name ? "security-autopilot-s3-2-" : null
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "vulnerable" {
  bucket = aws_s3_bucket.vulnerable.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "public_read" {
  bucket = aws_s3_bucket.vulnerable.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowPublicRead"
        Effect    = "Allow"
        Principal = "*"
        Action    = ["s3:GetObject"]
        Resource  = "${aws_s3_bucket.vulnerable.arn}/*"
      }
    ]
  })
}

output "vulnerable_bucket_name" {
  value = aws_s3_bucket.vulnerable.id
}
