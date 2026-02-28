#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# SAFETY WARNING
# ==============================================================================
# This script deploys Architecture 2 resources in dependency order for
# production-readiness validation.
#
# - This script creates and mutates real AWS resources.
# - Run only in an isolated test account you control.
# - Root-principal state (arch2_root_credentials_state_c) is MANUAL-GATE ONLY.
# - No reset/teardown logic is included in this script by design.
#
# To proceed intentionally, export:
#   ENABLE_ARCH2_DEPLOY=true
# ==============================================================================

if [[ "${ENABLE_ARCH2_DEPLOY:-}" != "true" ]]; then
  echo "Refusing to run. Set ENABLE_ARCH2_DEPLOY=true to acknowledge the safety warning." >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required but not installed." >&2
  exit 1
fi

export AWS_PAGER=""

require_non_placeholder() {
  local var_name="$1"
  local var_value="$2"
  local placeholder="$3"
  if [[ -z "$var_value" || "$var_value" == "$placeholder" ]]; then
    echo "Missing required value for ${var_name}. Current value: '${var_value}'" >&2
    exit 1
  fi
}

log_step() {
  local step="$1"
  local resource="$2"
  local aws_type="$3"
  echo
  echo "------------------------------------------------------------------------------"
  echo "STEP ${step} | ${resource} | ${aws_type}"
  echo "------------------------------------------------------------------------------"
}

# ==============================================================================
# SECTION: Shared Variables Block (Architecture 2)
# ==============================================================================
ACCOUNT_ID="${ACCOUNT_ID:-<YOUR_ACCOUNT_ID_HERE>}"
AWS_REGION="${AWS_REGION:-<YOUR_AWS_REGION_HERE>}"

ARCH2_VPC_MAIN_NAME="${ARCH2_VPC_MAIN_NAME:-arch2_vpc_main}"
ARCH2_PRIVATE_SUBNET_A_NAME="${ARCH2_PRIVATE_SUBNET_A_NAME:-arch2_private_subnet_a}"
ARCH2_PRIVATE_SUBNET_B_NAME="${ARCH2_PRIVATE_SUBNET_B_NAME:-arch2_private_subnet_b}"
ARCH2_EKS_CLUSTER_C_NAME="${ARCH2_EKS_CLUSTER_C_NAME:-arch2_eks_cluster_c}"
ARCH2_RDS_PRIMARY_C_NAME="${ARCH2_RDS_PRIMARY_C_NAME:-arch2_rds_primary_c}"
ARCH2_SECURITYHUB_ACCOUNT_C_NAME="${ARCH2_SECURITYHUB_ACCOUNT_C_NAME:-arch2_securityhub_account_c}"
ARCH2_GUARDDUTY_DETECTOR_C_NAME="${ARCH2_GUARDDUTY_DETECTOR_C_NAME:-arch2_guardduty_detector_c}"
ARCH2_CLOUDTRAIL_MAIN_C_NAME="${ARCH2_CLOUDTRAIL_MAIN_C_NAME:-arch2_cloudtrail_main_c}"
ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_NAME="${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_NAME:-arch2_cloudtrail_logs_bucket_c}"
ARCH2_CONFIG_BUCKET_C_NAME="${ARCH2_CONFIG_BUCKET_C_NAME:-arch2_config_bucket_c}"
ARCH2_CONFIG_RECORDER_C_NAME="${ARCH2_CONFIG_RECORDER_C_NAME:-arch2_config_recorder_c}"
ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME="${ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME:-arch2_config_delivery_channel_c}"
ARCH2_SSM_SHARING_BLOCK_C_NAME="${ARCH2_SSM_SHARING_BLOCK_C_NAME:-arch2_ssm_sharing_block_c}"
ARCH2_EBS_DEFAULT_ENCRYPTION_C_NAME="${ARCH2_EBS_DEFAULT_ENCRYPTION_C_NAME:-arch2_ebs_default_encryption_c}"
ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_NAME="${ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_NAME:-arch2_snapshot_block_public_access_c}"
ARCH2_ROOT_CREDENTIALS_STATE_C_NAME="${ARCH2_ROOT_CREDENTIALS_STATE_C_NAME:-arch2_root_credentials_state_c}"
ARCH2_SHARED_COMPUTE_ROLE_A3_NAME="${ARCH2_SHARED_COMPUTE_ROLE_A3_NAME:-arch2_shared_compute_role_a3}"
ARCH2_MIXED_POLICY_ROLE_B3_NAME="${ARCH2_MIXED_POLICY_ROLE_B3_NAME:-arch2_mixed_policy_role_b3}"

ARCH2_VPC_CIDR="${ARCH2_VPC_CIDR:-10.20.0.0/16}"
ARCH2_PRIVATE_SUBNET_A_CIDR="${ARCH2_PRIVATE_SUBNET_A_CIDR:-10.20.11.0/24}"
ARCH2_PRIVATE_SUBNET_B_CIDR="${ARCH2_PRIVATE_SUBNET_B_CIDR:-10.20.12.0/24}"
ARCH2_AZ_A="${ARCH2_AZ_A:-${AWS_REGION}a}"
ARCH2_AZ_B="${ARCH2_AZ_B:-${AWS_REGION}b}"

ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET="${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET:-${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}}"
ARCH2_CONFIG_BUCKET_C_BUCKET="${ARCH2_CONFIG_BUCKET_C_BUCKET:-${ARCH2_CONFIG_BUCKET_C_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}}"

ARCH2_CONFIG_SERVICE_ROLE_ARN="${ARCH2_CONFIG_SERVICE_ROLE_ARN:-arn:aws:iam::${ACCOUNT_ID}:role/aws-service-role/config.amazonaws.com/AWSServiceRoleForConfig}"
ARCH2_SSM_PUBLIC_SHARING_SETTING_ID="${ARCH2_SSM_PUBLIC_SHARING_SETTING_ID:-/ssm/documents/console/public-sharing-permission}"
ARCH2_EBS_DEFAULT_KMS_KEY_ID="${ARCH2_EBS_DEFAULT_KMS_KEY_ID:-alias/aws/ebs}"
ARCH2_MIXED_POLICY_ROLE_B3_MANAGED_POLICY_ARN="${ARCH2_MIXED_POLICY_ROLE_B3_MANAGED_POLICY_ARN:-arn:aws:iam::aws:policy/ReadOnlyAccess}"

ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER="${ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER:-${ARCH2_RDS_PRIMARY_C_NAME//_/-}}"
ARCH2_RDS_DB_SUBNET_GROUP_NAME="${ARCH2_RDS_DB_SUBNET_GROUP_NAME:-${ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER}-subnet-group}"
ARCH2_RDS_INSTANCE_CLASS="${ARCH2_RDS_INSTANCE_CLASS:-db.t4g.micro}"
ARCH2_RDS_ENGINE="${ARCH2_RDS_ENGINE:-postgres}"
ARCH2_RDS_ENGINE_VERSION="${ARCH2_RDS_ENGINE_VERSION:-16.3}"
ARCH2_RDS_ALLOCATED_STORAGE="${ARCH2_RDS_ALLOCATED_STORAGE:-20}"
ARCH2_RDS_MASTER_USERNAME="${ARCH2_RDS_MASTER_USERNAME:-}"
ARCH2_RDS_MASTER_PASSWORD="${ARCH2_RDS_MASTER_PASSWORD:-}"

ARCH2_EKS_CLUSTER_C_CLUSTER_NAME="${ARCH2_EKS_CLUSTER_C_CLUSTER_NAME:-${ARCH2_EKS_CLUSTER_C_NAME//_/-}}"
ARCH2_EKS_KUBERNETES_VERSION="${ARCH2_EKS_KUBERNETES_VERSION:-1.31}"

TAG_PROJECT_VALUE="AWS-Security-Autopilot"
TAG_ENVIRONMENT_VALUE="prod-readiness"
TAG_MANAGED_BY_VALUE="aws-cli"
TAG_ARCHITECTURE_VALUE="architecture-2"

require_non_placeholder "ACCOUNT_ID" "$ACCOUNT_ID" "<YOUR_ACCOUNT_ID_HERE>"
require_non_placeholder "AWS_REGION" "$AWS_REGION" "<YOUR_AWS_REGION_HERE>"
require_non_placeholder "ARCH2_RDS_MASTER_USERNAME" "$ARCH2_RDS_MASTER_USERNAME" ""
require_non_placeholder "ARCH2_RDS_MASTER_PASSWORD" "$ARCH2_RDS_MASTER_PASSWORD" ""

# ==============================================================================
# SECTION: Architecture 2 Create Order
# ==============================================================================

# 1) arch2_vpc_main — AWS::EC2::VPC
log_step "01" "arch2_vpc_main" "AWS::EC2::VPC"
ARCH2_VPC_MAIN_ID="$(aws ec2 describe-vpcs \
  --region "$AWS_REGION" \
  --filters "Name=tag:Name,Values=${ARCH2_VPC_MAIN_NAME}" "Name=tag:Architecture,Values=${TAG_ARCHITECTURE_VALUE}" \
  --query 'Vpcs[0].VpcId' \
  --output text 2>/dev/null || true)"
if [[ -z "$ARCH2_VPC_MAIN_ID" || "$ARCH2_VPC_MAIN_ID" == "None" ]]; then
  ARCH2_VPC_MAIN_ID="$(aws ec2 create-vpc \
    --region "$AWS_REGION" \
    --cidr-block "$ARCH2_VPC_CIDR" \
    --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=${ARCH2_VPC_MAIN_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}},{Key=Tier,Value=processing-orchestration},{Key=ResourceGroup,Value=C}]" \
    --query 'Vpc.VpcId' \
    --output text)"
  aws ec2 modify-vpc-attribute --region "$AWS_REGION" --vpc-id "$ARCH2_VPC_MAIN_ID" --enable-dns-support "{\"Value\":true}"
  aws ec2 modify-vpc-attribute --region "$AWS_REGION" --vpc-id "$ARCH2_VPC_MAIN_ID" --enable-dns-hostnames "{\"Value\":true}"
fi
echo "ARCH2_VPC_MAIN_ID=$ARCH2_VPC_MAIN_ID"

# 2) arch2_private_subnet_a — AWS::EC2::Subnet
log_step "02" "arch2_private_subnet_a" "AWS::EC2::Subnet"
ARCH2_PRIVATE_SUBNET_A_ID="$(aws ec2 describe-subnets \
  --region "$AWS_REGION" \
  --filters "Name=vpc-id,Values=${ARCH2_VPC_MAIN_ID}" "Name=tag:Name,Values=${ARCH2_PRIVATE_SUBNET_A_NAME}" \
  --query 'Subnets[0].SubnetId' \
  --output text 2>/dev/null || true)"
if [[ -z "$ARCH2_PRIVATE_SUBNET_A_ID" || "$ARCH2_PRIVATE_SUBNET_A_ID" == "None" ]]; then
  ARCH2_PRIVATE_SUBNET_A_ID="$(aws ec2 create-subnet \
    --region "$AWS_REGION" \
    --vpc-id "$ARCH2_VPC_MAIN_ID" \
    --cidr-block "$ARCH2_PRIVATE_SUBNET_A_CIDR" \
    --availability-zone "$ARCH2_AZ_A" \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${ARCH2_PRIVATE_SUBNET_A_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}},{Key=Tier,Value=processing-orchestration},{Key=ResourceGroup,Value=C}]" \
    --query 'Subnet.SubnetId' \
    --output text)"
  aws ec2 modify-subnet-attribute --region "$AWS_REGION" --subnet-id "$ARCH2_PRIVATE_SUBNET_A_ID" --no-map-public-ip-on-launch
fi
echo "ARCH2_PRIVATE_SUBNET_A_ID=$ARCH2_PRIVATE_SUBNET_A_ID"

# 3) arch2_private_subnet_b — AWS::EC2::Subnet
log_step "03" "arch2_private_subnet_b" "AWS::EC2::Subnet"
ARCH2_PRIVATE_SUBNET_B_ID="$(aws ec2 describe-subnets \
  --region "$AWS_REGION" \
  --filters "Name=vpc-id,Values=${ARCH2_VPC_MAIN_ID}" "Name=tag:Name,Values=${ARCH2_PRIVATE_SUBNET_B_NAME}" \
  --query 'Subnets[0].SubnetId' \
  --output text 2>/dev/null || true)"
if [[ -z "$ARCH2_PRIVATE_SUBNET_B_ID" || "$ARCH2_PRIVATE_SUBNET_B_ID" == "None" ]]; then
  ARCH2_PRIVATE_SUBNET_B_ID="$(aws ec2 create-subnet \
    --region "$AWS_REGION" \
    --vpc-id "$ARCH2_VPC_MAIN_ID" \
    --cidr-block "$ARCH2_PRIVATE_SUBNET_B_CIDR" \
    --availability-zone "$ARCH2_AZ_B" \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${ARCH2_PRIVATE_SUBNET_B_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}},{Key=Tier,Value=data-retention},{Key=ResourceGroup,Value=C}]" \
    --query 'Subnet.SubnetId' \
    --output text)"
  aws ec2 modify-subnet-attribute --region "$AWS_REGION" --subnet-id "$ARCH2_PRIVATE_SUBNET_B_ID" --no-map-public-ip-on-launch
fi
echo "ARCH2_PRIVATE_SUBNET_B_ID=$ARCH2_PRIVATE_SUBNET_B_ID"

# 4) arch2_cloudtrail_logs_bucket_c — AWS::S3::Bucket
log_step "04" "arch2_cloudtrail_logs_bucket_c" "AWS::S3::Bucket"
if ! aws s3api head-bucket --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" 2>/dev/null; then
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET"
  else
    aws s3api create-bucket \
      --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
      --region "$AWS_REGION" \
      --create-bucket-configuration "LocationConstraint=${AWS_REGION}"
  fi
fi
aws s3api put-bucket-tagging \
  --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
  --tagging "TagSet=[{Key=Name,Value=${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}},{Key=Tier,Value=data-retention},{Key=ResourceGroup,Value=C}]"
ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_ARN="arn:aws:s3:::${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET}"
ARCH2_CLOUDTRAIL_BUCKET_POLICY_FILE="$(mktemp)"
cat >"$ARCH2_CLOUDTRAIL_BUCKET_POLICY_FILE" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSCloudTrailAclCheck",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:GetBucketAcl",
      "Resource": "arn:aws:s3:::${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET}"
    },
    {
      "Sid": "AWSCloudTrailWrite",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudtrail.amazonaws.com"
      },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET}/AWSLogs/${ACCOUNT_ID}/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": "bucket-owner-full-control"
        }
      }
    }
  ]
}
EOF
aws s3api put-bucket-policy \
  --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
  --policy "file://${ARCH2_CLOUDTRAIL_BUCKET_POLICY_FILE}"
rm -f "$ARCH2_CLOUDTRAIL_BUCKET_POLICY_FILE"
echo "ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET=$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET"
echo "ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_ARN=$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_ARN"

# 5) arch2_config_bucket_c — AWS::S3::Bucket
log_step "05" "arch2_config_bucket_c" "AWS::S3::Bucket"
if ! aws s3api head-bucket --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" 2>/dev/null; then
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET"
  else
    aws s3api create-bucket \
      --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
      --region "$AWS_REGION" \
      --create-bucket-configuration "LocationConstraint=${AWS_REGION}"
  fi
fi
aws s3api put-bucket-tagging \
  --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
  --tagging "TagSet=[{Key=Name,Value=${ARCH2_CONFIG_BUCKET_C_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}},{Key=Tier,Value=data-retention},{Key=ResourceGroup,Value=C}]"
ARCH2_CONFIG_BUCKET_C_ARN="arn:aws:s3:::${ARCH2_CONFIG_BUCKET_C_BUCKET}"
ARCH2_CONFIG_BUCKET_POLICY_FILE="$(mktemp)"
cat >"$ARCH2_CONFIG_BUCKET_POLICY_FILE" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSConfigBucketPermissionsCheck",
      "Effect": "Allow",
      "Principal": {
        "Service": "config.amazonaws.com"
      },
      "Action": "s3:GetBucketAcl",
      "Resource": "arn:aws:s3:::${ARCH2_CONFIG_BUCKET_C_BUCKET}",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "${ACCOUNT_ID}"
        }
      }
    },
    {
      "Sid": "AWSConfigBucketDelivery",
      "Effect": "Allow",
      "Principal": {
        "Service": "config.amazonaws.com"
      },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::${ARCH2_CONFIG_BUCKET_C_BUCKET}/AWSLogs/${ACCOUNT_ID}/Config/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": "bucket-owner-full-control",
          "aws:SourceAccount": "${ACCOUNT_ID}"
        }
      }
    }
  ]
}
EOF
aws s3api put-bucket-policy \
  --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
  --policy "file://${ARCH2_CONFIG_BUCKET_POLICY_FILE}"
rm -f "$ARCH2_CONFIG_BUCKET_POLICY_FILE"
echo "ARCH2_CONFIG_BUCKET_C_BUCKET=$ARCH2_CONFIG_BUCKET_C_BUCKET"
echo "ARCH2_CONFIG_BUCKET_C_ARN=$ARCH2_CONFIG_BUCKET_C_ARN"

# 6) arch2_securityhub_account_c — securityhub:EnableSecurityHub
log_step "06" "arch2_securityhub_account_c" "securityhub:EnableSecurityHub (account setting)"
if ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN="$(aws securityhub describe-hub --region "$AWS_REGION" --query 'HubArn' --output text 2>/dev/null)"; then
  true
else
  ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN="$(aws securityhub enable-security-hub \
    --region "$AWS_REGION" \
    --enable-default-standards \
    --tags "Project=${TAG_PROJECT_VALUE},Environment=${TAG_ENVIRONMENT_VALUE},ManagedBy=${TAG_MANAGED_BY_VALUE},Architecture=${TAG_ARCHITECTURE_VALUE},Tier=governance-admin,ResourceGroup=C" \
    --query 'HubArn' \
    --output text)"
fi
echo "ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN=$ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN"

# 7) arch2_guardduty_detector_c — AWS::GuardDuty::Detector
log_step "07" "arch2_guardduty_detector_c" "AWS::GuardDuty::Detector"
ARCH2_GUARDDUTY_DETECTOR_C_ID="$(aws guardduty list-detectors --region "$AWS_REGION" --query 'DetectorIds[0]' --output text)"
if [[ -z "$ARCH2_GUARDDUTY_DETECTOR_C_ID" || "$ARCH2_GUARDDUTY_DETECTOR_C_ID" == "None" ]]; then
  ARCH2_GUARDDUTY_DETECTOR_C_ID="$(aws guardduty create-detector \
    --region "$AWS_REGION" \
    --enable \
    --tags "Name=${ARCH2_GUARDDUTY_DETECTOR_C_NAME},Project=${TAG_PROJECT_VALUE},Environment=${TAG_ENVIRONMENT_VALUE},ManagedBy=${TAG_MANAGED_BY_VALUE},Architecture=${TAG_ARCHITECTURE_VALUE},Tier=governance-admin,ResourceGroup=C" \
    --query 'DetectorId' \
    --output text)"
fi
echo "ARCH2_GUARDDUTY_DETECTOR_C_ID=$ARCH2_GUARDDUTY_DETECTOR_C_ID"

# 8) arch2_config_recorder_c — AWS::Config::ConfigurationRecorder
log_step "08" "arch2_config_recorder_c" "AWS::Config::ConfigurationRecorder"
ARCH2_EXISTING_CONFIG_RECORDER_C_NAME="$(aws configservice describe-configuration-recorders \
  --region "$AWS_REGION" \
  --query 'ConfigurationRecorders[0].name' \
  --output text 2>/dev/null || true)"
if [[ -n "$ARCH2_EXISTING_CONFIG_RECORDER_C_NAME" && "$ARCH2_EXISTING_CONFIG_RECORDER_C_NAME" != "None" ]]; then
  ARCH2_CONFIG_RECORDER_C_NAME="$ARCH2_EXISTING_CONFIG_RECORDER_C_NAME"
fi
aws configservice put-configuration-recorder \
  --region "$AWS_REGION" \
  --configuration-recorder "{\"name\":\"${ARCH2_CONFIG_RECORDER_C_NAME}\",\"roleARN\":\"${ARCH2_CONFIG_SERVICE_ROLE_ARN}\",\"recordingGroup\":{\"allSupported\":true,\"includeGlobalResourceTypes\":true}}"
ARCH2_CONFIG_RECORDER_C_STATUS="configured"
echo "ARCH2_CONFIG_RECORDER_C_NAME=$ARCH2_CONFIG_RECORDER_C_NAME"
echo "ARCH2_CONFIG_RECORDER_C_STATUS=$ARCH2_CONFIG_RECORDER_C_STATUS"

# 9) arch2_config_delivery_channel_c — AWS::Config::DeliveryChannel
log_step "09" "arch2_config_delivery_channel_c" "AWS::Config::DeliveryChannel"
ARCH2_EXISTING_CONFIG_DELIVERY_CHANNEL_C_NAME="$(aws configservice describe-delivery-channels \
  --region "$AWS_REGION" \
  --query 'DeliveryChannels[0].name' \
  --output text 2>/dev/null || true)"
if [[ -n "$ARCH2_EXISTING_CONFIG_DELIVERY_CHANNEL_C_NAME" && "$ARCH2_EXISTING_CONFIG_DELIVERY_CHANNEL_C_NAME" != "None" ]]; then
  ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME="$ARCH2_EXISTING_CONFIG_DELIVERY_CHANNEL_C_NAME"
fi
aws configservice put-delivery-channel \
  --region "$AWS_REGION" \
  --delivery-channel "name=${ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME},s3BucketName=${ARCH2_CONFIG_BUCKET_C_BUCKET}"
aws configservice start-configuration-recorder \
  --region "$AWS_REGION" \
  --configuration-recorder-name "$ARCH2_CONFIG_RECORDER_C_NAME"
ARCH2_CONFIG_DELIVERY_CHANNEL_C_STATUS="configured"
echo "ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME=$ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME"
echo "ARCH2_CONFIG_DELIVERY_CHANNEL_C_STATUS=$ARCH2_CONFIG_DELIVERY_CHANNEL_C_STATUS"

# 10) arch2_cloudtrail_main_c — AWS::CloudTrail::Trail
log_step "10" "arch2_cloudtrail_main_c" "AWS::CloudTrail::Trail"
ARCH2_CLOUDTRAIL_MAIN_C_ARN="$(aws cloudtrail describe-trails \
  --region "$AWS_REGION" \
  --trail-name-list "$ARCH2_CLOUDTRAIL_MAIN_C_NAME" \
  --query 'trailList[0].TrailARN' \
  --output text 2>/dev/null || true)"
if [[ -z "$ARCH2_CLOUDTRAIL_MAIN_C_ARN" || "$ARCH2_CLOUDTRAIL_MAIN_C_ARN" == "None" ]]; then
  ARCH2_CLOUDTRAIL_MAIN_C_ARN="$(aws cloudtrail create-trail \
    --region "$AWS_REGION" \
    --name "$ARCH2_CLOUDTRAIL_MAIN_C_NAME" \
    --s3-bucket-name "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
    --is-multi-region-trail \
    --include-global-service-events \
    --enable-log-file-validation \
    --query 'TrailARN' \
    --output text)"
fi
aws cloudtrail add-tags \
  --region "$AWS_REGION" \
  --resource-id "$ARCH2_CLOUDTRAIL_MAIN_C_ARN" \
  --tags-list \
    "Key=Name,Value=${ARCH2_CLOUDTRAIL_MAIN_C_NAME}" \
    "Key=Project,Value=${TAG_PROJECT_VALUE}" \
    "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
    "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
    "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
    "Key=Tier,Value=governance-admin" \
    "Key=ResourceGroup,Value=C"
aws cloudtrail start-logging --region "$AWS_REGION" --name "$ARCH2_CLOUDTRAIL_MAIN_C_NAME"
echo "ARCH2_CLOUDTRAIL_MAIN_C_ARN=$ARCH2_CLOUDTRAIL_MAIN_C_ARN"

# 11) arch2_ssm_sharing_block_c — ssm:UpdateServiceSetting
log_step "11" "arch2_ssm_sharing_block_c" "ssm:UpdateServiceSetting (account setting)"
ARCH2_SSM_SHARING_BLOCK_C_VALUE="$(aws ssm get-service-setting \
  --region "$AWS_REGION" \
  --setting-id "$ARCH2_SSM_PUBLIC_SHARING_SETTING_ID" \
  --query 'ServiceSetting.SettingValue' \
  --output text 2>/dev/null || true)"
if [[ "$ARCH2_SSM_SHARING_BLOCK_C_VALUE" != "Disable" ]]; then
  aws ssm update-service-setting \
    --region "$AWS_REGION" \
    --setting-id "$ARCH2_SSM_PUBLIC_SHARING_SETTING_ID" \
    --setting-value "Disable" >/dev/null
fi
ARCH2_SSM_SHARING_BLOCK_C_VALUE="$(aws ssm get-service-setting \
  --region "$AWS_REGION" \
  --setting-id "$ARCH2_SSM_PUBLIC_SHARING_SETTING_ID" \
  --query 'ServiceSetting.SettingValue' \
  --output text)"
echo "ARCH2_SSM_SHARING_BLOCK_C_VALUE=$ARCH2_SSM_SHARING_BLOCK_C_VALUE"

# 12) arch2_ebs_default_encryption_c — ec2:EnableEbsEncryptionByDefault + ModifyEbsDefaultKmsKeyId
log_step "12" "arch2_ebs_default_encryption_c" "ec2:EnableEbsEncryptionByDefault + ec2:ModifyEbsDefaultKmsKeyId"
ARCH2_EBS_ENCRYPTION_BY_DEFAULT="$(aws ec2 get-ebs-encryption-by-default --region "$AWS_REGION" --query 'EbsEncryptionByDefault' --output text)"
if [[ "$ARCH2_EBS_ENCRYPTION_BY_DEFAULT" != "True" ]]; then
  aws ec2 enable-ebs-encryption-by-default --region "$AWS_REGION" >/dev/null
fi
aws ec2 modify-ebs-default-kms-key-id \
  --region "$AWS_REGION" \
  --kms-key-id "$ARCH2_EBS_DEFAULT_KMS_KEY_ID" >/dev/null
ARCH2_EBS_DEFAULT_ENCRYPTION_C_KMS_KEY_ID="$(aws ec2 get-ebs-default-kms-key-id --region "$AWS_REGION" --query 'KmsKeyId' --output text)"
echo "ARCH2_EBS_ENCRYPTION_BY_DEFAULT=True"
echo "ARCH2_EBS_DEFAULT_ENCRYPTION_C_KMS_KEY_ID=$ARCH2_EBS_DEFAULT_ENCRYPTION_C_KMS_KEY_ID"

# 13) arch2_snapshot_block_public_access_c — AWS::EC2::SnapshotBlockPublicAccess
log_step "13" "arch2_snapshot_block_public_access_c" "AWS::EC2::SnapshotBlockPublicAccess"
ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE="$(aws ec2 get-snapshot-block-public-access-state \
  --region "$AWS_REGION" \
  --query 'State' \
  --output text 2>/dev/null || true)"
if [[ "$ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE" != "block-all-sharing" ]]; then
  aws ec2 enable-snapshot-block-public-access \
    --region "$AWS_REGION" \
    --state "block-all-sharing" >/dev/null
fi
ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE="$(aws ec2 get-snapshot-block-public-access-state \
  --region "$AWS_REGION" \
  --query 'State' \
  --output text)"
echo "ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE=$ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE"

# 14) arch2_root_credentials_state_c — AWS account root principal (manual gate only)
log_step "14" "arch2_root_credentials_state_c" "AWS account root principal (existing account entity)"
ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT="$(aws iam get-account-summary --query 'SummaryMap.AccountAccessKeysPresent' --output text)"
ARCH2_ROOT_ACCOUNT_MFA_ENABLED="$(aws iam get-account-summary --query 'SummaryMap.AccountMFAEnabled' --output text)"

if [[ "${ARCH2_ROOT_CREDENTIALS_STATE_ACK:-}" != "ACKNOWLEDGED_MANUAL_ROOT_REVIEW" ]]; then
  cat <<'EOF'
MANUAL SAFETY STOP:
arch2_root_credentials_state_c (IAM.4) is not a deployable AWS CLI create operation.

Before continuing:
1) Verify root credentials posture manually in AWS Console.
2) Capture evidence for your run record.
3) Re-run with:
   ARCH2_ROOT_CREDENTIALS_STATE_ACK=ACKNOWLEDGED_MANUAL_ROOT_REVIEW
EOF
  exit 1
fi
ARCH2_ROOT_CREDENTIALS_STATE_C_STATUS="manual-review-acknowledged"
echo "ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT=$ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT"
echo "ARCH2_ROOT_ACCOUNT_MFA_ENABLED=$ARCH2_ROOT_ACCOUNT_MFA_ENABLED"
echo "ARCH2_ROOT_CREDENTIALS_STATE_C_STATUS=$ARCH2_ROOT_CREDENTIALS_STATE_C_STATUS"

# 15) arch2_shared_compute_role_a3 — AWS::IAM::Role (A-series adversarial)
log_step "15" "arch2_shared_compute_role_a3" "AWS::IAM::Role"
A3_TRUST_POLICY_FILE="$(mktemp)"
A3_INLINE_POLICY_FILE="$(mktemp)"
cat >"$A3_TRUST_POLICY_FILE" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "ec2.amazonaws.com",
          "eks.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON
cat >"$A3_INLINE_POLICY_FILE" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "A3AdversarialWildcard",
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*"
    }
  ]
}
JSON
if aws iam get-role --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" >/dev/null 2>&1; then
  ARCH2_SHARED_COMPUTE_ROLE_A3_ARN="$(aws iam get-role --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" --query 'Role.Arn' --output text)"
else
  ARCH2_SHARED_COMPUTE_ROLE_A3_ARN="$(aws iam create-role \
    --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
    --assume-role-policy-document "file://${A3_TRUST_POLICY_FILE}" \
    --tags \
      "Key=Name,Value=${ARCH2_SHARED_COMPUTE_ROLE_A3_NAME}" \
      "Key=Project,Value=${TAG_PROJECT_VALUE}" \
      "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
      "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
      "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
      "Key=Tier,Value=processing-orchestration" \
      "Key=ResourceGroup,Value=A" \
      "Key=BlastRadiusTest,Value=iam-multi-principal" \
    --query 'Role.Arn' \
    --output text)"
fi
aws iam update-assume-role-policy \
  --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
  --policy-document "file://${A3_TRUST_POLICY_FILE}"
aws iam put-role-policy \
  --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
  --policy-name "${ARCH2_SHARED_COMPUTE_ROLE_A3_NAME}-inline-wildcard" \
  --policy-document "file://${A3_INLINE_POLICY_FILE}"
rm -f "$A3_TRUST_POLICY_FILE" "$A3_INLINE_POLICY_FILE"
echo "ARCH2_SHARED_COMPUTE_ROLE_A3_ARN=$ARCH2_SHARED_COMPUTE_ROLE_A3_ARN"

# 16) arch2_mixed_policy_role_b3 — AWS::IAM::Role (B-series adversarial)
log_step "16" "arch2_mixed_policy_role_b3" "AWS::IAM::Role"
B3_TRUST_POLICY_FILE="$(mktemp)"
B3_INLINE_POLICY_FILE="$(mktemp)"
cat >"$B3_TRUST_POLICY_FILE" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
JSON
cat >"$B3_INLINE_POLICY_FILE" <<'JSON'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "B3InlineWildcard",
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*"
    }
  ]
}
JSON
if aws iam get-role --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" >/dev/null 2>&1; then
  ARCH2_MIXED_POLICY_ROLE_B3_ARN="$(aws iam get-role --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" --query 'Role.Arn' --output text)"
else
  ARCH2_MIXED_POLICY_ROLE_B3_ARN="$(aws iam create-role \
    --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
    --assume-role-policy-document "file://${B3_TRUST_POLICY_FILE}" \
    --tags \
      "Key=Name,Value=${ARCH2_MIXED_POLICY_ROLE_B3_NAME}" \
      "Key=Project,Value=${TAG_PROJECT_VALUE}" \
      "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
      "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
      "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
      "Key=Tier,Value=governance-admin" \
      "Key=ResourceGroup,Value=B" \
      "Key=ContextTest,Value=inline-plus-managed" \
    --query 'Role.Arn' \
    --output text)"
fi
aws iam update-assume-role-policy \
  --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
  --policy-document "file://${B3_TRUST_POLICY_FILE}"
aws iam put-role-policy \
  --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
  --policy-name "${ARCH2_MIXED_POLICY_ROLE_B3_NAME}-inline-wildcard" \
  --policy-document "file://${B3_INLINE_POLICY_FILE}"
ARCH2_B3_POLICY_ATTACHED="$(aws iam list-attached-role-policies \
  --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
  --query "AttachedPolicies[?PolicyArn=='${ARCH2_MIXED_POLICY_ROLE_B3_MANAGED_POLICY_ARN}'] | length(@)" \
  --output text)"
if [[ "$ARCH2_B3_POLICY_ATTACHED" == "0" ]]; then
  aws iam attach-role-policy \
    --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
    --policy-arn "$ARCH2_MIXED_POLICY_ROLE_B3_MANAGED_POLICY_ARN"
fi
rm -f "$B3_TRUST_POLICY_FILE" "$B3_INLINE_POLICY_FILE"
echo "ARCH2_MIXED_POLICY_ROLE_B3_ARN=$ARCH2_MIXED_POLICY_ROLE_B3_ARN"

# 17) arch2_rds_primary_c — AWS::RDS::DBInstance
log_step "17" "arch2_rds_primary_c" "AWS::RDS::DBInstance"
ARCH2_VPC_MAIN_IGW_ID="$(aws ec2 describe-internet-gateways \
  --region "$AWS_REGION" \
  --filters "Name=attachment.vpc-id,Values=${ARCH2_VPC_MAIN_ID}" \
  --query 'InternetGateways[0].InternetGatewayId' \
  --output text 2>/dev/null || true)"
if [[ -z "$ARCH2_VPC_MAIN_IGW_ID" || "$ARCH2_VPC_MAIN_IGW_ID" == "None" ]]; then
  ARCH2_VPC_MAIN_IGW_ID="$(aws ec2 create-internet-gateway \
    --region "$AWS_REGION" \
    --query 'InternetGateway.InternetGatewayId' \
    --output text)"
  aws ec2 create-tags \
    --region "$AWS_REGION" \
    --resources "$ARCH2_VPC_MAIN_IGW_ID" \
    --tags \
      "Key=Name,Value=${ARCH2_VPC_MAIN_NAME}-igw" \
      "Key=Project,Value=${TAG_PROJECT_VALUE}" \
      "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
      "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
      "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
      "Key=Tier,Value=processing-orchestration" \
      "Key=ResourceGroup,Value=C" >/dev/null
  aws ec2 attach-internet-gateway \
    --region "$AWS_REGION" \
    --internet-gateway-id "$ARCH2_VPC_MAIN_IGW_ID" \
    --vpc-id "$ARCH2_VPC_MAIN_ID"
fi

ARCH2_PUBLIC_ROUTE_TABLE_ID="$(aws ec2 describe-route-tables \
  --region "$AWS_REGION" \
  --filters "Name=vpc-id,Values=${ARCH2_VPC_MAIN_ID}" "Name=tag:Name,Values=${ARCH2_VPC_MAIN_NAME}-public-rt" \
  --query 'RouteTables[0].RouteTableId' \
  --output text 2>/dev/null || true)"
if [[ -z "$ARCH2_PUBLIC_ROUTE_TABLE_ID" || "$ARCH2_PUBLIC_ROUTE_TABLE_ID" == "None" ]]; then
  ARCH2_PUBLIC_ROUTE_TABLE_ID="$(aws ec2 create-route-table \
    --region "$AWS_REGION" \
    --vpc-id "$ARCH2_VPC_MAIN_ID" \
    --query 'RouteTable.RouteTableId' \
    --output text)"
  aws ec2 create-tags \
    --region "$AWS_REGION" \
    --resources "$ARCH2_PUBLIC_ROUTE_TABLE_ID" \
    --tags \
      "Key=Name,Value=${ARCH2_VPC_MAIN_NAME}-public-rt" \
      "Key=Project,Value=${TAG_PROJECT_VALUE}" \
      "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
      "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
      "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
      "Key=Tier,Value=processing-orchestration" \
      "Key=ResourceGroup,Value=C" >/dev/null
fi
aws ec2 create-route \
  --region "$AWS_REGION" \
  --route-table-id "$ARCH2_PUBLIC_ROUTE_TABLE_ID" \
  --destination-cidr-block "0.0.0.0/0" \
  --gateway-id "$ARCH2_VPC_MAIN_IGW_ID" >/dev/null 2>&1 || true

for ARCH2_SUBNET_ID in "$ARCH2_PRIVATE_SUBNET_A_ID" "$ARCH2_PRIVATE_SUBNET_B_ID"; do
  ARCH2_ASSOCIATED_ROUTE_TABLE_ID="$(aws ec2 describe-route-tables \
    --region "$AWS_REGION" \
    --filters "Name=association.subnet-id,Values=${ARCH2_SUBNET_ID}" \
    --query 'RouteTables[0].RouteTableId' \
    --output text 2>/dev/null || true)"
  if [[ "$ARCH2_ASSOCIATED_ROUTE_TABLE_ID" != "$ARCH2_PUBLIC_ROUTE_TABLE_ID" ]]; then
    aws ec2 associate-route-table \
      --region "$AWS_REGION" \
      --subnet-id "$ARCH2_SUBNET_ID" \
      --route-table-id "$ARCH2_PUBLIC_ROUTE_TABLE_ID" >/dev/null
  fi
done

ARCH2_VPC_DEFAULT_SECURITY_GROUP_ID="$(aws ec2 describe-security-groups \
  --region "$AWS_REGION" \
  --filters "Name=vpc-id,Values=${ARCH2_VPC_MAIN_ID}" "Name=group-name,Values=default" \
  --query 'SecurityGroups[0].GroupId' \
  --output text)"
if [[ -z "$ARCH2_VPC_DEFAULT_SECURITY_GROUP_ID" || "$ARCH2_VPC_DEFAULT_SECURITY_GROUP_ID" == "None" ]]; then
  echo "Could not resolve default security group for VPC ${ARCH2_VPC_MAIN_ID}." >&2
  exit 1
fi
ARCH2_RDS_SUBNET_GROUP_EXISTS="$(aws rds describe-db-subnet-groups \
  --region "$AWS_REGION" \
  --db-subnet-group-name "$ARCH2_RDS_DB_SUBNET_GROUP_NAME" \
  --query 'DBSubnetGroups[0].DBSubnetGroupName' \
  --output text 2>/dev/null || true)"
if [[ -z "$ARCH2_RDS_SUBNET_GROUP_EXISTS" || "$ARCH2_RDS_SUBNET_GROUP_EXISTS" == "None" ]]; then
  aws rds create-db-subnet-group \
    --region "$AWS_REGION" \
    --db-subnet-group-name "$ARCH2_RDS_DB_SUBNET_GROUP_NAME" \
    --db-subnet-group-description "Subnet group for ${ARCH2_RDS_PRIMARY_C_NAME}" \
    --subnet-ids "$ARCH2_PRIVATE_SUBNET_A_ID" "$ARCH2_PRIVATE_SUBNET_B_ID" \
    --tags \
      "Key=Name,Value=${ARCH2_RDS_DB_SUBNET_GROUP_NAME}" \
      "Key=Project,Value=${TAG_PROJECT_VALUE}" \
      "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
      "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
      "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
      "Key=Tier,Value=data-retention" \
      "Key=ResourceGroup,Value=C" >/dev/null
fi
ARCH2_RDS_PRIMARY_C_ARN="$(aws rds describe-db-instances \
  --region "$AWS_REGION" \
  --db-instance-identifier "$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER" \
  --query 'DBInstances[0].DBInstanceArn' \
  --output text 2>/dev/null || true)"
if [[ -z "$ARCH2_RDS_PRIMARY_C_ARN" || "$ARCH2_RDS_PRIMARY_C_ARN" == "None" ]]; then
  ARCH2_RDS_PRIMARY_C_ARN="$(aws rds create-db-instance \
    --region "$AWS_REGION" \
    --db-instance-identifier "$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER" \
    --db-instance-class "$ARCH2_RDS_INSTANCE_CLASS" \
    --engine "$ARCH2_RDS_ENGINE" \
    --allocated-storage "$ARCH2_RDS_ALLOCATED_STORAGE" \
    --master-username "$ARCH2_RDS_MASTER_USERNAME" \
    --master-user-password "$ARCH2_RDS_MASTER_PASSWORD" \
    --db-subnet-group-name "$ARCH2_RDS_DB_SUBNET_GROUP_NAME" \
    --vpc-security-group-ids "$ARCH2_VPC_DEFAULT_SECURITY_GROUP_ID" \
    --publicly-accessible \
    --no-storage-encrypted \
    --backup-retention-period 7 \
    --tags \
      "Key=Name,Value=${ARCH2_RDS_PRIMARY_C_NAME}" \
      "Key=Project,Value=${TAG_PROJECT_VALUE}" \
      "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
      "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
      "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
      "Key=Tier,Value=data-retention" \
      "Key=ResourceGroup,Value=C" \
    --query 'DBInstance.DBInstanceArn' \
    --output text)"
fi
echo "ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER=$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER"
echo "ARCH2_RDS_PRIMARY_C_ARN=$ARCH2_RDS_PRIMARY_C_ARN"

# 18) arch2_eks_cluster_c — AWS::EKS::Cluster
log_step "18" "arch2_eks_cluster_c" "AWS::EKS::Cluster"
ARCH2_A3_EKS_POLICY_ATTACHED="$(aws iam list-attached-role-policies \
  --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
  --query "AttachedPolicies[?PolicyArn=='arn:aws:iam::aws:policy/AmazonEKSClusterPolicy'] | length(@)" \
  --output text)"
if [[ "$ARCH2_A3_EKS_POLICY_ATTACHED" == "0" ]]; then
  aws iam attach-role-policy \
    --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
fi
ARCH2_EKS_CLUSTER_C_ARN="$(aws eks describe-cluster \
  --region "$AWS_REGION" \
  --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
  --query 'cluster.arn' \
  --output text 2>/dev/null || true)"
if [[ -z "$ARCH2_EKS_CLUSTER_C_ARN" || "$ARCH2_EKS_CLUSTER_C_ARN" == "None" ]]; then
  ARCH2_EKS_CLUSTER_C_ARN="$(aws eks create-cluster \
    --region "$AWS_REGION" \
    --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
    --kubernetes-version "$ARCH2_EKS_KUBERNETES_VERSION" \
    --role-arn "$ARCH2_SHARED_COMPUTE_ROLE_A3_ARN" \
    --resources-vpc-config "subnetIds=${ARCH2_PRIVATE_SUBNET_A_ID},${ARCH2_PRIVATE_SUBNET_B_ID},endpointPublicAccess=true,endpointPrivateAccess=false" \
    --tags "Name=${ARCH2_EKS_CLUSTER_C_NAME},Project=${TAG_PROJECT_VALUE},Environment=${TAG_ENVIRONMENT_VALUE},ManagedBy=${TAG_MANAGED_BY_VALUE},Architecture=${TAG_ARCHITECTURE_VALUE},Tier=processing-orchestration,ResourceGroup=C" \
    --query 'cluster.arn' \
    --output text)"
fi
echo "ARCH2_EKS_CLUSTER_C_CLUSTER_NAME=$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME"
echo "ARCH2_EKS_CLUSTER_C_ARN=$ARCH2_EKS_CLUSTER_C_ARN"

echo
echo "Architecture 2 deployment script completed."
echo "Captured outputs:"
cat <<EOF
ARCH2_VPC_MAIN_ID=${ARCH2_VPC_MAIN_ID}
ARCH2_PRIVATE_SUBNET_A_ID=${ARCH2_PRIVATE_SUBNET_A_ID}
ARCH2_PRIVATE_SUBNET_B_ID=${ARCH2_PRIVATE_SUBNET_B_ID}
ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET=${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET}
ARCH2_CONFIG_BUCKET_C_BUCKET=${ARCH2_CONFIG_BUCKET_C_BUCKET}
ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN=${ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN}
ARCH2_GUARDDUTY_DETECTOR_C_ID=${ARCH2_GUARDDUTY_DETECTOR_C_ID}
ARCH2_CONFIG_RECORDER_C_NAME=${ARCH2_CONFIG_RECORDER_C_NAME}
ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME=${ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME}
ARCH2_CLOUDTRAIL_MAIN_C_ARN=${ARCH2_CLOUDTRAIL_MAIN_C_ARN}
ARCH2_SSM_SHARING_BLOCK_C_VALUE=${ARCH2_SSM_SHARING_BLOCK_C_VALUE}
ARCH2_EBS_DEFAULT_ENCRYPTION_C_KMS_KEY_ID=${ARCH2_EBS_DEFAULT_ENCRYPTION_C_KMS_KEY_ID}
ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE=${ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE}
ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT=${ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT}
ARCH2_ROOT_ACCOUNT_MFA_ENABLED=${ARCH2_ROOT_ACCOUNT_MFA_ENABLED}
ARCH2_SHARED_COMPUTE_ROLE_A3_ARN=${ARCH2_SHARED_COMPUTE_ROLE_A3_ARN}
ARCH2_MIXED_POLICY_ROLE_B3_ARN=${ARCH2_MIXED_POLICY_ROLE_B3_ARN}
ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER=${ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER}
ARCH2_RDS_PRIMARY_C_ARN=${ARCH2_RDS_PRIMARY_C_ARN}
ARCH2_EKS_CLUSTER_C_CLUSTER_NAME=${ARCH2_EKS_CLUSTER_C_CLUSTER_NAME}
ARCH2_EKS_CLUSTER_C_ARN=${ARCH2_EKS_CLUSTER_C_ARN}
EOF
