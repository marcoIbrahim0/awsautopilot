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
  description = "AWS region for provider operations."
  type        = string
  default     = "eu-north-1"
}

provider "aws" {
  region = var.region
}

resource "aws_s3_account_public_access_block" "vulnerable" {
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

output "s3_account_public_access_block_state" {
  value = {
    block_public_acls       = aws_s3_account_public_access_block.vulnerable.block_public_acls
    block_public_policy     = aws_s3_account_public_access_block.vulnerable.block_public_policy
    ignore_public_acls      = aws_s3_account_public_access_block.vulnerable.ignore_public_acls
    restrict_public_buckets = aws_s3_account_public_access_block.vulnerable.restrict_public_buckets
  }
}
