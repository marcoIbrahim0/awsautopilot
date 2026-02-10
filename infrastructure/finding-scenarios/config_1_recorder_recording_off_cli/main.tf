terraform {
  required_version = ">= 1.5.0"
}

variable "region" {
  description = "AWS region to disable AWS Config recording in."
  type        = string
  default     = "eu-north-1"
}

# Uses AWS CLI to stop all configuration recorders in the region.
# This is intentionally imperative because recorder names vary by account.
resource "terraform_data" "stop_config_recorders" {
  input = {
    region = var.region
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-lc"]
    command     = <<BASH
set -euo pipefail
REGION="${var.region}"
export AWS_DEFAULT_REGION="$REGION"

recorders=$(aws configservice describe-configuration-recorders --query 'ConfigurationRecorders[].name' --output text 2>/dev/null || true)
if [[ -z "$recorders" ]]; then
  echo "No AWS Config recorders found in $REGION (already non-compliant for Config.1)."
  exit 0
fi

for name in $recorders; do
  echo "Stopping recorder: $name"
  aws configservice stop-configuration-recorder --configuration-recorder-name "$name" >/dev/null 2>&1 || true
done
echo "Done."
BASH
  }
}
