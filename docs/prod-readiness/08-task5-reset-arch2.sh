#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# SAFETY WARNING
# ==============================================================================
# This script resets Architecture 2 Group A and Group C resources to the
# intended adversarial/misconfigured states used by remediation validation.
#
# - This script mutates real AWS resources.
# - Run only in an isolated test account you control.
# - Root-principal state (arch2_root_credentials_state_c) is MANUAL-GATE ONLY.
# - No deploy/teardown logic is included in this script by design.
#
# To proceed intentionally, export:
#   ENABLE_ARCH2_RESET=true
# ==============================================================================

if [[ "${ENABLE_ARCH2_RESET:-}" != "true" ]]; then
  echo "Refusing to run. Set ENABLE_ARCH2_RESET=true to acknowledge the safety warning." >&2
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required but not installed." >&2
  exit 1
fi

AWS_PAGER=""

require_non_placeholder() {
  local var_name="$1"
  local var_value="$2"
  local placeholder="$3"
  if [[ -z "$var_value" || "$var_value" == "$placeholder" ]]; then
    echo "Missing required value for ${var_name}. Current value: '${var_value}'" >&2
    exit 1
  fi
}

require_existing_resource() {
  local resource_name="$1"
  local resource_value="$2"
  if [[ -z "$resource_value" || "$resource_value" == "None" ]]; then
    echo "Required resource '${resource_name}' was not found. Deploy Architecture 2 first." >&2
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
ARCH2_EKS_CLUSTER_C_CLUSTER_NAME="${ARCH2_EKS_CLUSTER_C_CLUSTER_NAME:-${ARCH2_EKS_CLUSTER_C_NAME//_/-}}"

TAG_PROJECT_VALUE="AWS-Security-Autopilot"
TAG_ENVIRONMENT_VALUE="prod-readiness"
TAG_MANAGED_BY_VALUE="aws-cli"
TAG_ARCHITECTURE_VALUE="architecture-2"

require_non_placeholder "ACCOUNT_ID" "$ACCOUNT_ID" "<YOUR_ACCOUNT_ID_HERE>"
require_non_placeholder "AWS_REGION" "$AWS_REGION" "<YOUR_AWS_REGION_HERE>"

# ==============================================================================
# SECTION: Architecture 2 Reset Order
# ==============================================================================

# 1) arch2_vpc_main — AWS::EC2::VPC
log_step "01" "arch2_vpc_main" "AWS::EC2::VPC"
ARCH2_VPC_MAIN_ID="$(aws ec2 describe-vpcs \
  --region "$AWS_REGION" \
  --filters "Name=tag:Name,Values=${ARCH2_VPC_MAIN_NAME}" "Name=tag:Architecture,Values=${TAG_ARCHITECTURE_VALUE}" \
  --query 'Vpcs[0].VpcId' \
  --output text 2>/dev/null || true)"
require_existing_resource "arch2_vpc_main" "$ARCH2_VPC_MAIN_ID"
aws ec2 create-tags \
  --region "$AWS_REGION" \
  --resources "$ARCH2_VPC_MAIN_ID" \
  --tags \
    "Key=Name,Value=${ARCH2_VPC_MAIN_NAME}" \
    "Key=Project,Value=${TAG_PROJECT_VALUE}" \
    "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
    "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
    "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
    "Key=Tier,Value=processing-orchestration" \
    "Key=ResourceGroup,Value=C" >/dev/null
aws ec2 modify-vpc-attribute --region "$AWS_REGION" --vpc-id "$ARCH2_VPC_MAIN_ID" --enable-dns-support "{\"Value\":true}"
aws ec2 modify-vpc-attribute --region "$AWS_REGION" --vpc-id "$ARCH2_VPC_MAIN_ID" --enable-dns-hostnames "{\"Value\":true}"
echo "ARCH2_VPC_MAIN_ID=$ARCH2_VPC_MAIN_ID"

# 2) arch2_private_subnet_a — AWS::EC2::Subnet
log_step "02" "arch2_private_subnet_a" "AWS::EC2::Subnet"
ARCH2_PRIVATE_SUBNET_A_ID="$(aws ec2 describe-subnets \
  --region "$AWS_REGION" \
  --filters "Name=vpc-id,Values=${ARCH2_VPC_MAIN_ID}" "Name=tag:Name,Values=${ARCH2_PRIVATE_SUBNET_A_NAME}" \
  --query 'Subnets[0].SubnetId' \
  --output text 2>/dev/null || true)"
require_existing_resource "arch2_private_subnet_a" "$ARCH2_PRIVATE_SUBNET_A_ID"
aws ec2 create-tags \
  --region "$AWS_REGION" \
  --resources "$ARCH2_PRIVATE_SUBNET_A_ID" \
  --tags \
    "Key=Name,Value=${ARCH2_PRIVATE_SUBNET_A_NAME}" \
    "Key=Project,Value=${TAG_PROJECT_VALUE}" \
    "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
    "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
    "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
    "Key=Tier,Value=processing-orchestration" \
    "Key=ResourceGroup,Value=C" >/dev/null
aws ec2 modify-subnet-attribute --region "$AWS_REGION" --subnet-id "$ARCH2_PRIVATE_SUBNET_A_ID" --no-map-public-ip-on-launch
echo "ARCH2_PRIVATE_SUBNET_A_ID=$ARCH2_PRIVATE_SUBNET_A_ID"

# 3) arch2_private_subnet_b — AWS::EC2::Subnet
log_step "03" "arch2_private_subnet_b" "AWS::EC2::Subnet"
ARCH2_PRIVATE_SUBNET_B_ID="$(aws ec2 describe-subnets \
  --region "$AWS_REGION" \
  --filters "Name=vpc-id,Values=${ARCH2_VPC_MAIN_ID}" "Name=tag:Name,Values=${ARCH2_PRIVATE_SUBNET_B_NAME}" \
  --query 'Subnets[0].SubnetId' \
  --output text 2>/dev/null || true)"
require_existing_resource "arch2_private_subnet_b" "$ARCH2_PRIVATE_SUBNET_B_ID"
aws ec2 create-tags \
  --region "$AWS_REGION" \
  --resources "$ARCH2_PRIVATE_SUBNET_B_ID" \
  --tags \
    "Key=Name,Value=${ARCH2_PRIVATE_SUBNET_B_NAME}" \
    "Key=Project,Value=${TAG_PROJECT_VALUE}" \
    "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
    "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
    "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
    "Key=Tier,Value=data-retention" \
    "Key=ResourceGroup,Value=C" >/dev/null
aws ec2 modify-subnet-attribute --region "$AWS_REGION" --subnet-id "$ARCH2_PRIVATE_SUBNET_B_ID" --no-map-public-ip-on-launch
echo "ARCH2_PRIVATE_SUBNET_B_ID=$ARCH2_PRIVATE_SUBNET_B_ID"

# 4) arch2_cloudtrail_logs_bucket_c — AWS::S3::Bucket
log_step "04" "arch2_cloudtrail_logs_bucket_c" "AWS::S3::Bucket"
if ! aws s3api head-bucket --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" 2>/dev/null; then
  echo "Required resource 'arch2_cloudtrail_logs_bucket_c' was not found. Deploy Architecture 2 first." >&2
  exit 1
fi
aws s3api put-bucket-tagging \
  --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
  --tagging "TagSet=[{Key=Name,Value=${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}},{Key=Tier,Value=data-retention},{Key=ResourceGroup,Value=C}]"
ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_ARN="arn:aws:s3:::${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET}"
echo "ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET=$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET"
echo "ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_ARN=$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_ARN"

# 5) arch2_config_bucket_c — AWS::S3::Bucket
log_step "05" "arch2_config_bucket_c" "AWS::S3::Bucket"
if ! aws s3api head-bucket --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" 2>/dev/null; then
  echo "Required resource 'arch2_config_bucket_c' was not found. Deploy Architecture 2 first." >&2
  exit 1
fi
aws s3api put-bucket-tagging \
  --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
  --tagging "TagSet=[{Key=Name,Value=${ARCH2_CONFIG_BUCKET_C_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}},{Key=Tier,Value=data-retention},{Key=ResourceGroup,Value=C}]"
ARCH2_CONFIG_BUCKET_C_ARN="arn:aws:s3:::${ARCH2_CONFIG_BUCKET_C_BUCKET}"
echo "ARCH2_CONFIG_BUCKET_C_BUCKET=$ARCH2_CONFIG_BUCKET_C_BUCKET"
echo "ARCH2_CONFIG_BUCKET_C_ARN=$ARCH2_CONFIG_BUCKET_C_ARN"

# 6) arch2_securityhub_account_c — securityhub:EnableSecurityHub (account setting)
log_step "06" "arch2_securityhub_account_c" "securityhub:EnableSecurityHub (account setting)"
if ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN="$(aws securityhub describe-hub --region "$AWS_REGION" --query 'HubArn' --output text 2>/dev/null)"; then
  aws securityhub disable-security-hub --region "$AWS_REGION" >/dev/null
  ARCH2_SECURITYHUB_ACCOUNT_C_STATE="disabled"
else
  ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN="None"
  ARCH2_SECURITYHUB_ACCOUNT_C_STATE="already-disabled"
fi
echo "ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN=$ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN"
echo "ARCH2_SECURITYHUB_ACCOUNT_C_STATE=$ARCH2_SECURITYHUB_ACCOUNT_C_STATE"

# 7) arch2_guardduty_detector_c — AWS::GuardDuty::Detector
log_step "07" "arch2_guardduty_detector_c" "AWS::GuardDuty::Detector"
ARCH2_GUARDDUTY_DETECTOR_C_ID="$(aws guardduty list-detectors --region "$AWS_REGION" --query 'DetectorIds[0]' --output text 2>/dev/null || true)"
require_existing_resource "arch2_guardduty_detector_c" "$ARCH2_GUARDDUTY_DETECTOR_C_ID"
aws guardduty update-detector \
  --region "$AWS_REGION" \
  --detector-id "$ARCH2_GUARDDUTY_DETECTOR_C_ID" \
  --no-enable >/dev/null
aws guardduty tag-resource \
  --region "$AWS_REGION" \
  --resource-arn "arn:aws:guardduty:${AWS_REGION}:${ACCOUNT_ID}:detector/${ARCH2_GUARDDUTY_DETECTOR_C_ID}" \
  --tags "Name=${ARCH2_GUARDDUTY_DETECTOR_C_NAME},Project=${TAG_PROJECT_VALUE},Environment=${TAG_ENVIRONMENT_VALUE},ManagedBy=${TAG_MANAGED_BY_VALUE},Architecture=${TAG_ARCHITECTURE_VALUE},Tier=governance-admin,ResourceGroup=C" >/dev/null
ARCH2_GUARDDUTY_DETECTOR_C_STATUS="$(aws guardduty get-detector \
  --region "$AWS_REGION" \
  --detector-id "$ARCH2_GUARDDUTY_DETECTOR_C_ID" \
  --query 'Status' \
  --output text)"
echo "ARCH2_GUARDDUTY_DETECTOR_C_ID=$ARCH2_GUARDDUTY_DETECTOR_C_ID"
echo "ARCH2_GUARDDUTY_DETECTOR_C_STATUS=$ARCH2_GUARDDUTY_DETECTOR_C_STATUS"

# 8) arch2_config_recorder_c — AWS::Config::ConfigurationRecorder
log_step "08" "arch2_config_recorder_c" "AWS::Config::ConfigurationRecorder"
aws configservice put-configuration-recorder \
  --region "$AWS_REGION" \
  --configuration-recorder "name=${ARCH2_CONFIG_RECORDER_C_NAME},roleARN=${ARCH2_CONFIG_SERVICE_ROLE_ARN},recordingGroup={allSupported=true,includeGlobalResourceTypes=true}"
aws configservice stop-configuration-recorder \
  --region "$AWS_REGION" \
  --configuration-recorder-name "$ARCH2_CONFIG_RECORDER_C_NAME" >/dev/null || true
ARCH2_CONFIG_RECORDER_C_RECORDING="$(aws configservice describe-configuration-recorder-status \
  --region "$AWS_REGION" \
  --configuration-recorder-names "$ARCH2_CONFIG_RECORDER_C_NAME" \
  --query 'ConfigurationRecordersStatus[0].recording' \
  --output text 2>/dev/null || true)"
echo "ARCH2_CONFIG_RECORDER_C_NAME=$ARCH2_CONFIG_RECORDER_C_NAME"
echo "ARCH2_CONFIG_RECORDER_C_RECORDING=$ARCH2_CONFIG_RECORDER_C_RECORDING"

# 9) arch2_config_delivery_channel_c — AWS::Config::DeliveryChannel
log_step "09" "arch2_config_delivery_channel_c" "AWS::Config::DeliveryChannel"
aws configservice put-delivery-channel \
  --region "$AWS_REGION" \
  --delivery-channel "name=${ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME},s3BucketName=${ARCH2_CONFIG_BUCKET_C_BUCKET}"
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
require_existing_resource "arch2_cloudtrail_main_c" "$ARCH2_CLOUDTRAIL_MAIN_C_ARN"
aws cloudtrail stop-logging --region "$AWS_REGION" --name "$ARCH2_CLOUDTRAIL_MAIN_C_NAME"
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
ARCH2_CLOUDTRAIL_MAIN_C_IS_LOGGING="$(aws cloudtrail get-trail-status \
  --region "$AWS_REGION" \
  --name "$ARCH2_CLOUDTRAIL_MAIN_C_NAME" \
  --query 'IsLogging' \
  --output text)"
echo "ARCH2_CLOUDTRAIL_MAIN_C_ARN=$ARCH2_CLOUDTRAIL_MAIN_C_ARN"
echo "ARCH2_CLOUDTRAIL_MAIN_C_IS_LOGGING=$ARCH2_CLOUDTRAIL_MAIN_C_IS_LOGGING"

# 11) arch2_ssm_sharing_block_c — ssm:UpdateServiceSetting (account setting)
log_step "11" "arch2_ssm_sharing_block_c" "ssm:UpdateServiceSetting (account setting)"
aws ssm update-service-setting \
  --region "$AWS_REGION" \
  --setting-id "$ARCH2_SSM_PUBLIC_SHARING_SETTING_ID" \
  --setting-value "Enable" >/dev/null
ARCH2_SSM_SHARING_BLOCK_C_VALUE="$(aws ssm get-service-setting \
  --region "$AWS_REGION" \
  --setting-id "$ARCH2_SSM_PUBLIC_SHARING_SETTING_ID" \
  --query 'ServiceSetting.SettingValue' \
  --output text)"
echo "ARCH2_SSM_SHARING_BLOCK_C_NAME=$ARCH2_SSM_SHARING_BLOCK_C_NAME"
echo "ARCH2_SSM_SHARING_BLOCK_C_VALUE=$ARCH2_SSM_SHARING_BLOCK_C_VALUE"

# 12) arch2_ebs_default_encryption_c — ec2:EnableEbsEncryptionByDefault + ec2:ModifyEbsDefaultKmsKeyId
log_step "12" "arch2_ebs_default_encryption_c" "ec2:EnableEbsEncryptionByDefault + ec2:ModifyEbsDefaultKmsKeyId"
aws ec2 disable-ebs-encryption-by-default --region "$AWS_REGION" >/dev/null || true
ARCH2_EBS_ENCRYPTION_BY_DEFAULT="$(aws ec2 get-ebs-encryption-by-default --region "$AWS_REGION" --query 'EbsEncryptionByDefault' --output text)"
ARCH2_EBS_DEFAULT_ENCRYPTION_C_KMS_KEY_ID="$(aws ec2 get-ebs-default-kms-key-id --region "$AWS_REGION" --query 'KmsKeyId' --output text 2>/dev/null || true)"
echo "ARCH2_EBS_DEFAULT_ENCRYPTION_C_NAME=$ARCH2_EBS_DEFAULT_ENCRYPTION_C_NAME"
echo "ARCH2_EBS_ENCRYPTION_BY_DEFAULT=$ARCH2_EBS_ENCRYPTION_BY_DEFAULT"
echo "ARCH2_EBS_DEFAULT_ENCRYPTION_C_KMS_KEY_ID=$ARCH2_EBS_DEFAULT_ENCRYPTION_C_KMS_KEY_ID"

# 13) arch2_snapshot_block_public_access_c — AWS::EC2::SnapshotBlockPublicAccess
log_step "13" "arch2_snapshot_block_public_access_c" "AWS::EC2::SnapshotBlockPublicAccess"
aws ec2 disable-snapshot-block-public-access --region "$AWS_REGION" >/dev/null || true
ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE="$(aws ec2 get-snapshot-block-public-access-state \
  --region "$AWS_REGION" \
  --query 'State' \
  --output text 2>/dev/null || true)"
echo "ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_NAME=$ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_NAME"
echo "ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE=$ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE"

# 14) arch2_rds_primary_c — AWS::RDS::DBInstance
log_step "14" "arch2_rds_primary_c" "AWS::RDS::DBInstance"
ARCH2_RDS_PRIMARY_C_ARN="$(aws rds describe-db-instances \
  --region "$AWS_REGION" \
  --db-instance-identifier "$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER" \
  --query 'DBInstances[0].DBInstanceArn' \
  --output text 2>/dev/null || true)"
require_existing_resource "arch2_rds_primary_c" "$ARCH2_RDS_PRIMARY_C_ARN"
aws rds modify-db-instance \
  --region "$AWS_REGION" \
  --db-instance-identifier "$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER" \
  --publicly-accessible \
  --apply-immediately >/dev/null
aws rds add-tags-to-resource \
  --region "$AWS_REGION" \
  --resource-name "$ARCH2_RDS_PRIMARY_C_ARN" \
  --tags \
    "Key=Name,Value=${ARCH2_RDS_PRIMARY_C_NAME}" \
    "Key=Project,Value=${TAG_PROJECT_VALUE}" \
    "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" \
    "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" \
    "Key=Architecture,Value=${TAG_ARCHITECTURE_VALUE}" \
    "Key=Tier,Value=data-retention" \
    "Key=ResourceGroup,Value=C"
ARCH2_RDS_PRIMARY_C_PUBLICLY_ACCESSIBLE="$(aws rds describe-db-instances \
  --region "$AWS_REGION" \
  --db-instance-identifier "$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER" \
  --query 'DBInstances[0].PubliclyAccessible' \
  --output text)"
ARCH2_RDS_PRIMARY_C_STORAGE_ENCRYPTED="$(aws rds describe-db-instances \
  --region "$AWS_REGION" \
  --db-instance-identifier "$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER" \
  --query 'DBInstances[0].StorageEncrypted' \
  --output text)"
if [[ "$ARCH2_RDS_PRIMARY_C_STORAGE_ENCRYPTED" == "True" ]]; then
  ARCH2_RDS_PRIMARY_C_ENCRYPTION_RESET_STATUS="manual-recreate-required"
  cat <<'EOF'
RDS ENCRYPTION NOTE:
arch2_rds_primary_c is currently encrypted.
RDS storage encryption cannot be disabled in place.
To fully reset the adversarial state for RDS.ENCRYPTION, recreate the instance
without storage encryption using the same identifier and tags.
EOF
else
  ARCH2_RDS_PRIMARY_C_ENCRYPTION_RESET_STATUS="not-encrypted"
fi
echo "ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER=$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER"
echo "ARCH2_RDS_PRIMARY_C_ARN=$ARCH2_RDS_PRIMARY_C_ARN"
echo "ARCH2_RDS_PRIMARY_C_PUBLICLY_ACCESSIBLE=$ARCH2_RDS_PRIMARY_C_PUBLICLY_ACCESSIBLE"
echo "ARCH2_RDS_PRIMARY_C_STORAGE_ENCRYPTED=$ARCH2_RDS_PRIMARY_C_STORAGE_ENCRYPTED"
echo "ARCH2_RDS_PRIMARY_C_ENCRYPTION_RESET_STATUS=$ARCH2_RDS_PRIMARY_C_ENCRYPTION_RESET_STATUS"

# 15) arch2_eks_cluster_c — AWS::EKS::Cluster
log_step "15" "arch2_eks_cluster_c" "AWS::EKS::Cluster"
ARCH2_EKS_CLUSTER_C_ARN="$(aws eks describe-cluster \
  --region "$AWS_REGION" \
  --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
  --query 'cluster.arn' \
  --output text 2>/dev/null || true)"
require_existing_resource "arch2_eks_cluster_c" "$ARCH2_EKS_CLUSTER_C_ARN"
aws eks update-cluster-config \
  --region "$AWS_REGION" \
  --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
  --resources-vpc-config "endpointPublicAccess=true,endpointPrivateAccess=false" >/dev/null
aws eks tag-resource \
  --region "$AWS_REGION" \
  --resource-arn "$ARCH2_EKS_CLUSTER_C_ARN" \
  --tags "Name=${ARCH2_EKS_CLUSTER_C_NAME},Project=${TAG_PROJECT_VALUE},Environment=${TAG_ENVIRONMENT_VALUE},ManagedBy=${TAG_MANAGED_BY_VALUE},Architecture=${TAG_ARCHITECTURE_VALUE},Tier=processing-orchestration,ResourceGroup=C" >/dev/null
ARCH2_EKS_CLUSTER_C_ENDPOINT_PUBLIC="$(aws eks describe-cluster \
  --region "$AWS_REGION" \
  --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
  --query 'cluster.resourcesVpcConfig.endpointPublicAccess' \
  --output text)"
ARCH2_EKS_CLUSTER_C_ENDPOINT_PRIVATE="$(aws eks describe-cluster \
  --region "$AWS_REGION" \
  --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
  --query 'cluster.resourcesVpcConfig.endpointPrivateAccess' \
  --output text)"
echo "ARCH2_EKS_CLUSTER_C_CLUSTER_NAME=$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME"
echo "ARCH2_EKS_CLUSTER_C_ARN=$ARCH2_EKS_CLUSTER_C_ARN"
echo "ARCH2_EKS_CLUSTER_C_ENDPOINT_PUBLIC=$ARCH2_EKS_CLUSTER_C_ENDPOINT_PUBLIC"
echo "ARCH2_EKS_CLUSTER_C_ENDPOINT_PRIVATE=$ARCH2_EKS_CLUSTER_C_ENDPOINT_PRIVATE"

# 16) arch2_shared_compute_role_a3 — AWS::IAM::Role (A-series adversarial)
log_step "16" "arch2_shared_compute_role_a3" "AWS::IAM::Role"
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

# 17) arch2_mixed_policy_role_b3 — AWS::IAM::Role (B-series adversarial in Architecture 2)
log_step "17" "arch2_mixed_policy_role_b3" "AWS::IAM::Role"
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

# 18) arch2_root_credentials_state_c — AWS account root principal (manual gate only)
log_step "18" "arch2_root_credentials_state_c" "AWS account root principal (existing account entity)"
ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT="$(aws iam get-account-summary --query 'SummaryMap.AccountAccessKeysPresent' --output text)"
ARCH2_ROOT_ACCOUNT_MFA_ENABLED="$(aws iam get-account-summary --query 'SummaryMap.AccountMFAEnabled' --output text)"
if [[ "${ARCH2_ROOT_CREDENTIALS_STATE_ACK:-}" != "ACKNOWLEDGED_MANUAL_ROOT_RESET" ]]; then
  cat <<'EOF'
MANUAL SAFETY STOP:
arch2_root_credentials_state_c (IAM.4) is not a deployable AWS CLI reset operation.

Before considering this reset complete:
1) Review root credentials posture manually in AWS Console.
2) If your test cycle requires root-credential exposure state, perform it manually.
3) Capture evidence for your run record.
4) Re-run with:
   ARCH2_ROOT_CREDENTIALS_STATE_ACK=ACKNOWLEDGED_MANUAL_ROOT_RESET
EOF
  exit 1
fi
ARCH2_ROOT_CREDENTIALS_STATE_C_STATUS="manual-reset-acknowledged"
echo "ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT=$ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT"
echo "ARCH2_ROOT_ACCOUNT_MFA_ENABLED=$ARCH2_ROOT_ACCOUNT_MFA_ENABLED"
echo "ARCH2_ROOT_CREDENTIALS_STATE_C_STATUS=$ARCH2_ROOT_CREDENTIALS_STATE_C_STATUS"

echo
echo "Architecture 2 reset script completed."
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
ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER=${ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER}
ARCH2_RDS_PRIMARY_C_ARN=${ARCH2_RDS_PRIMARY_C_ARN}
ARCH2_EKS_CLUSTER_C_CLUSTER_NAME=${ARCH2_EKS_CLUSTER_C_CLUSTER_NAME}
ARCH2_EKS_CLUSTER_C_ARN=${ARCH2_EKS_CLUSTER_C_ARN}
ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT=${ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT}
ARCH2_ROOT_ACCOUNT_MFA_ENABLED=${ARCH2_ROOT_ACCOUNT_MFA_ENABLED}
ARCH2_SHARED_COMPUTE_ROLE_A3_ARN=${ARCH2_SHARED_COMPUTE_ROLE_A3_ARN}
ARCH2_MIXED_POLICY_ROLE_B3_ARN=${ARCH2_MIXED_POLICY_ROLE_B3_ARN}
EOF
