# S3 bucket lifecycle configuration - Action: deb71e7d-1fc9-4108-a466-859fe51c52ef
# Remediation for: S3 general purpose buckets should have Lifecycle configurations
# Account: 696505809372 | Region: eu-north-1 | Bucket: phase2-wi1-lifecycle-696505809372-20260328224331
# Control: S3.11

locals {
  target_bucket_name = "phase2-wi1-lifecycle-696505809372-20260328224331"
}

variable "remediation_region" {
  type        = string
  description = "Region for lifecycle remediation."
  default     = "eu-north-1"
}

variable "abort_incomplete_multipart_days" {
  type        = number
  description = "Days before incomplete multipart uploads are aborted"
  default     = 7
}

resource "terraform_data" "security_autopilot" {
  triggers_replace = {
    bucket_name                    = local.target_bucket_name
    remediation_region             = var.remediation_region
    abort_incomplete_multipart_days = tostring(var.abort_incomplete_multipart_days)
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
export BUCKET_NAME="${local.target_bucket_name}"
export REGION="${var.remediation_region}"
export ABORT_INCOMPLETE_MULTIPART_DAYS="${var.abort_incomplete_multipart_days}"

python3 ./scripts/s3_lifecycle_merge.py
EOT
  }
}
