terraform {
  required_version = ">= 1.5.0"
}

variable "region" {
  description = "AWS region to delete GuardDuty detector(s) in."
  type        = string
  default     = "eu-north-1"
}

# Uses AWS CLI because GuardDuty detectors are singletons and may already exist unmanaged.
resource "terraform_data" "delete_guardduty_detectors" {
  input = {
    region = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
REGION="${var.region}"
export AWS_DEFAULT_REGION="$REGION"

detectors=$(aws guardduty list-detectors --query 'DetectorIds[]' --output text 2>/dev/null || true)
if [[ -z "$detectors" ]]; then
  echo "No GuardDuty detectors in $REGION (already non-compliant for GuardDuty.1)."
  exit 0
fi

for det in $detectors; do
  echo "Deleting detector: $det"
  aws guardduty delete-detector --detector-id "$det" >/dev/null 2>&1 || true
done
echo "Done."
BASH
  }
}
