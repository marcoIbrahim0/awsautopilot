# AWS Config enablement - Action: 80499866-2447-4d0d-bcb4-88e903797ca1
# Remediation for: AWS Config should be enabled and use the service-linked role for resource recording
# Account: 696505809372 | Region: eu-north-1
# Control: Config.1

variable "remediation_region" {
  type        = string
  default     = "eu-north-1"
  description = "Region for AWS Config enablement."
}

variable "delivery_bucket_name" {
  type        = string
  default     = "security-autopilot-config-696505809372-eu-north-1"
  description = "S3 bucket for AWS Config delivery."
}

variable "config_role_arn" {
  type        = string
  default     = "arn:aws:iam::696505809372:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig"
  description = "IAM role ARN used by AWS Config recorder."
}

variable "kms_key_arn" {
  type        = string
  default     = ""
  description = "Optional KMS key ARN for Config delivery channel."
}

variable "create_local_bucket" {
  type        = bool
  default     = true
  description = "When true, create delivery bucket in this account if missing."
}

variable "overwrite_recording_group" {
  type        = bool
  default     = true
  description = "When true, overwrite an existing recorder recordingGroup with all-supported mode."
}

resource "null_resource" "aws_config_enablement" {
  triggers = {
    region                    = var.remediation_region
    delivery_bucket           = var.delivery_bucket_name
    config_role_arn           = var.config_role_arn
    kms_key_arn               = var.kms_key_arn
    create_local_bucket       = tostring(var.create_local_bucket)
    overwrite_recording_group = tostring(var.overwrite_recording_group)
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
export REGION="${var.remediation_region}"
export BUCKET="${var.delivery_bucket_name}"
export ROLE_ARN="${var.config_role_arn}"
export KMS_ARN="${var.kms_key_arn}"
export CREATE_LOCAL_BUCKET="${var.create_local_bucket}"
export OVERWRITE_RECORDING_GROUP="${var.overwrite_recording_group}"
export ACCOUNT_ID="696505809372"
export ROLLBACK_DIR=".aws-config-rollback"

python3 ./scripts/aws_config_apply.py
EOT
  }
}
