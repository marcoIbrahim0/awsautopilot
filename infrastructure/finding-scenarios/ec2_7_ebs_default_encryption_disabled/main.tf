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

resource "aws_ebs_encryption_by_default" "vulnerable" {
  enabled = false
}

output "ebs_default_encryption_enabled" {
  value = aws_ebs_encryption_by_default.vulnerable.enabled
}

