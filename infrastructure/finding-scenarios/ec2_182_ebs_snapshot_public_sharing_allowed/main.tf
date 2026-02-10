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

# Intentionally allows public snapshot sharing at the account/region level.
resource "terraform_data" "disable_snapshot_block_public_access" {
  input = {
    region = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
export AWS_DEFAULT_REGION="${var.region}"
aws ec2 disable-snapshot-block-public-access >/dev/null
state=$(aws ec2 get-snapshot-block-public-access-state --query 'State' --output text 2>/dev/null || echo "unknown")
echo "EBS snapshot block public access state in ${var.region}: $state"
BASH
  }
}

output "ebs_snapshot_block_public_access_state" {
  value = "disabled_via_cli"
}
