# IAM root access key remediation - Action: c8201c18-5054-42ee-99c6-815ea082f2c9
# Remediation for: IAM root user access key should not exist
# Account: 029037611564 | Region: eu-north-1
# Control: IAM.4
# NOTE: This bundle requires AWS root credentials for the target account.
# NOTE: Runbook: docs/prod-readiness/root-credentials-required-iam-root-access-key-absent.md

variable "expected_account_id" {
  type        = string
  default     = "029037611564"
  description = "Target account ID expected by this remediation."
}

variable "delete_root_keys" {
  type        = bool
  default     = false
  description = "When true, delete root keys after disabling. When false, disable only."
}

resource "null_resource" "iam_root_access_key_absent" {
  triggers = {
    action_id           = "c8201c18-5054-42ee-99c6-815ea082f2c9"
    expected_account_id = var.expected_account_id
    delete_root_keys    = tostring(var.delete_root_keys)
  }

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
set -euo pipefail
CALLER_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
CALLER_ARN="$(aws sts get-caller-identity --query Arn --output text)"
if [ "$CALLER_ACCOUNT" != "${var.expected_account_id}" ]; then
  echo "ERROR: caller account does not match expected account ID."
  exit 1
fi
case "$CALLER_ARN" in
  arn:aws:iam::*:root) ;;
  *)
    echo "ERROR: root credentials are required to disable root access keys."
    exit 1
    ;;
esac
KEY_IDS="$(aws iam list-access-keys --query 'AccessKeyMetadata[].AccessKeyId' --output text || true)"
if [ -z "$KEY_IDS" ] || [ "$KEY_IDS" = "None" ]; then
  echo "No root access keys found."
  exit 0
fi
for key_id in $KEY_IDS; do
  aws iam update-access-key --access-key-id "$key_id" --status Inactive >/dev/null
  if [ "${var.delete_root_keys}" = "true" ]; then
    aws iam delete-access-key --access-key-id "$key_id" >/dev/null
  fi
done
EOT
  }
}
