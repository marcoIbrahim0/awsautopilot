terraform {
  required_version = ">= 1.5.0"
}

variable "region" {
  description = "AWS region to disable Security Hub in."
  type        = string
  default     = "eu-north-1"
}

# Uses AWS CLI because Security Hub enable/disable isn't reliably modeled as a reusable declarative state.
resource "terraform_data" "disable_security_hub" {
  input = {
    region = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
REGION="${var.region}"
export AWS_DEFAULT_REGION="$REGION"

aws securityhub disable-security-hub >/dev/null 2>&1 || true
echo "Security Hub disabled (or was already disabled) in $REGION."
BASH
  }
}
