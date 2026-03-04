# AWS Config enablement - Action: bc0e1c7e-6c7d-4e24-ba1e-96e079b39aef
# Remediation for: Enable AWS Config (Live Test D1 rerun)
# Account: 029037611564 | Region: eu-central-1
# Control: Config.1

variable "remediation_region" {
  type        = string
  default     = "eu-central-1"
  description = "Region for AWS Config enablement."
}

variable "delivery_bucket_name" {
  type        = string
  default     = "sa-live-d1-config-029037611564-0304013744"
  description = "S3 bucket for AWS Config delivery."
}

variable "config_role_arn" {
  type        = string
  default     = "arn:aws:iam::029037611564:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig"
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
  default     = false
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
REGION="${var.remediation_region}"
BUCKET="${var.delivery_bucket_name}"
ROLE_ARN="${var.config_role_arn}"
KMS_ARN="${var.kms_key_arn}"
CREATE_LOCAL_BUCKET="${var.create_local_bucket}"
OVERWRITE_RECORDING_GROUP="${var.overwrite_recording_group}"
ACCOUNT_ID="029037611564"

if [ "$CREATE_LOCAL_BUCKET" = "true" ]; then
  if ! aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null 2>&1; then
    if [ "$REGION" = "us-east-1" ]; then
      aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
    else
      aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
    fi
  fi

  REQUIRED_CONFIG_BUCKET_POLICY=$(cat <<JSON
{"Version":"2012-10-17","Statement":[{"Sid":"AWSConfigBucketPermissionsCheck","Effect":"Allow","Principal":{"Service":"config.amazonaws.com"},"Action":"s3:GetBucketAcl","Resource":"arn:aws:s3:::$BUCKET"},{"Sid":"AWSConfigBucketDelivery","Effect":"Allow","Principal":{"Service":"config.amazonaws.com"},"Action":"s3:PutObject","Resource":"arn:aws:s3:::$BUCKET/AWSLogs/$ACCOUNT_ID/Config/*","Condition":{"StringEquals":{"s3:x-amz-acl":"bucket-owner-full-control"}}}]}
JSON
)

  set +e
  EXISTING_BUCKET_POLICY_RAW=$(aws s3api get-bucket-policy --bucket "$BUCKET" --region "$REGION" --query 'Policy' --output text 2>&1)
  EXISTING_POLICY_EXIT=$?
  set -e

  if [ $EXISTING_POLICY_EXIT -ne 0 ]; then
    if [[ "$EXISTING_BUCKET_POLICY_RAW" == *"NoSuchBucketPolicy"* ]]; then
      EXISTING_BUCKET_POLICY_RAW=""
    else
      echo "WARNING: Unable to inspect existing bucket policy for '$BUCKET'. Applying required AWS Config statements only." >&2
      EXISTING_BUCKET_POLICY_RAW=""
    fi
  elif [ "$EXISTING_BUCKET_POLICY_RAW" = "None" ] || [ "$EXISTING_BUCKET_POLICY_RAW" = "null" ]; then
    EXISTING_BUCKET_POLICY_RAW=""
  fi

  MERGED_CONFIG_BUCKET_POLICY=$(EXISTING_BUCKET_POLICY_RAW="$EXISTING_BUCKET_POLICY_RAW" REQUIRED_CONFIG_BUCKET_POLICY="$REQUIRED_CONFIG_BUCKET_POLICY" python3 - <<'PY'
import json
import os


def parse_policy(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return dict(Version="2012-10-17", Statement=[])
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return dict(Version="2012-10-17", Statement=[])
    if not isinstance(data, dict):
        return dict(Version="2012-10-17", Statement=[])
    statements = data.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list):
        statements = []
    data["Statement"] = [statement for statement in statements if isinstance(statement, dict)]
    data.setdefault("Version", "2012-10-17")
    return data


def statement_key(statement: dict) -> tuple[str, str]:
    sid = statement.get("Sid")
    if isinstance(sid, str) and sid.strip():
        return ("sid", sid.strip())
    return ("json", json.dumps(statement, sort_keys=True, separators=(",", ":")))


existing = parse_policy(os.environ.get("EXISTING_BUCKET_POLICY_RAW", ""))
required = parse_policy(os.environ.get("REQUIRED_CONFIG_BUCKET_POLICY", ""))

merged_by_key: dict[tuple[str, str], dict] = dict()
for statement in existing.get("Statement", []):
    merged_by_key[statement_key(statement)] = statement
for statement in required.get("Statement", []):
    merged_by_key[statement_key(statement)] = statement

merged = dict(
    Version=existing.get("Version") or "2012-10-17",
    Statement=list(merged_by_key.values()),
)
print(json.dumps(merged, sort_keys=True, separators=(",", ":")))
PY
)

  aws s3api put-bucket-policy --bucket "$BUCKET" --region "$REGION" --policy "$MERGED_CONFIG_BUCKET_POLICY" >/dev/null
else
  if ! aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null 2>&1; then
    echo "ERROR: create_local_bucket=false and delivery bucket '$BUCKET' is unreachable. Provide a reachable delivery_bucket_name or set create_local_bucket=true." >&2
    exit 1
  fi
fi

RECORDER_NAME=$(aws configservice describe-configuration-recorders --region "$REGION" --query 'ConfigurationRecorders[0].name' --output text 2>/dev/null || true)
RECORDER_ALL_SUPPORTED=$(aws configservice describe-configuration-recorders --region "$REGION" --query 'ConfigurationRecorders[0].recordingGroup.allSupported' --output text 2>/dev/null || true)
RECORDER_EXISTS="true"
if [ -z "$RECORDER_NAME" ] || [ "$RECORDER_NAME" = "None" ] || [ "$RECORDER_NAME" = "null" ]; then
  RECORDER_NAME="security-autopilot-recorder"
  RECORDER_EXISTS="false"
fi

if [ "$RECORDER_EXISTS" = "false" ] || [ "$OVERWRITE_RECORDING_GROUP" = "true" ]; then
  RECORDER_PAYLOAD=$(cat <<JSON
{"name":"$RECORDER_NAME","roleARN":"$ROLE_ARN","recordingGroup":{"allSupported":true,"includeGlobalResourceTypes":true}}
JSON
)
  aws configservice put-configuration-recorder --region "$REGION" --configuration-recorder "$RECORDER_PAYLOAD" >/dev/null
elif [ "$RECORDER_ALL_SUPPORTED" = "false" ]; then
  echo "Preserving existing selective AWS Config recorder '$RECORDER_NAME' (overwrite_recording_group=false)." >&2
else
  echo "Preserving existing AWS Config recorder '$RECORDER_NAME' recording group (overwrite_recording_group=false)." >&2
fi

DELIVERY_NAME=$(aws configservice describe-delivery-channels --region "$REGION" --query 'DeliveryChannels[0].name' --output text 2>/dev/null || true)
EXISTING_DELIVERY_BUCKET=$(aws configservice describe-delivery-channels --region "$REGION" --query 'DeliveryChannels[0].s3BucketName' --output text 2>/dev/null || true)
if [ -z "$DELIVERY_NAME" ] || [ "$DELIVERY_NAME" = "None" ] || [ "$DELIVERY_NAME" = "null" ]; then
  DELIVERY_NAME="security-autopilot-delivery-channel"
fi

EXISTING_DELIVERY_BUCKET_STALE="false"
if [ -n "$EXISTING_DELIVERY_BUCKET" ] && [ "$EXISTING_DELIVERY_BUCKET" != "None" ] && [ "$EXISTING_DELIVERY_BUCKET" != "null" ]; then
  if ! aws s3api head-bucket --bucket "$EXISTING_DELIVERY_BUCKET" --region "$REGION" >/dev/null 2>&1; then
    EXISTING_DELIVERY_BUCKET_STALE="true"
  fi
fi

if [ "$EXISTING_DELIVERY_BUCKET_STALE" = "true" ] && [ "$CREATE_LOCAL_BUCKET" = "false" ] && [ "$EXISTING_DELIVERY_BUCKET" = "$BUCKET" ]; then
  echo "ERROR: Existing AWS Config delivery channel '$DELIVERY_NAME' points to unreachable bucket '$EXISTING_DELIVERY_BUCKET' and create_local_bucket=false cannot repair it. Provide a reachable delivery_bucket_name or set create_local_bucket=true." >&2
  exit 1
fi

if [ -n "$EXISTING_DELIVERY_BUCKET" ] && [ "$EXISTING_DELIVERY_BUCKET" != "None" ] && [ "$EXISTING_DELIVERY_BUCKET" != "null" ] && [ "$EXISTING_DELIVERY_BUCKET" != "$BUCKET" ]; then
  if [ "$EXISTING_DELIVERY_BUCKET_STALE" = "true" ]; then
    echo "WARNING: Existing AWS Config delivery channel '$DELIVERY_NAME' currently targets unreachable bucket '$EXISTING_DELIVERY_BUCKET'. This bundle will redirect delivery to '$BUCKET'." >&2
  else
    echo "WARNING: Existing AWS Config delivery channel '$DELIVERY_NAME' currently targets bucket '$EXISTING_DELIVERY_BUCKET'. This bundle will redirect delivery to '$BUCKET'." >&2
  fi
fi

if [ -n "$KMS_ARN" ]; then
  aws configservice put-delivery-channel --region "$REGION" --delivery-channel "name=$DELIVERY_NAME,s3BucketName=$BUCKET,s3KmsKeyArn=$KMS_ARN" >/dev/null
else
  aws configservice put-delivery-channel --region "$REGION" --delivery-channel "name=$DELIVERY_NAME,s3BucketName=$BUCKET" >/dev/null
fi

aws configservice start-configuration-recorder --region "$REGION" --configuration-recorder-name "$RECORDER_NAME" >/dev/null || true
EOT
  }
}
