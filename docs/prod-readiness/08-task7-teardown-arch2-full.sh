#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Variables block (Architecture 2 variables from Section 3 that this script uses)
# ---------------------------------------------------------------------------
ACCOUNT_ID="<YOUR_ACCOUNT_ID_HERE>"
AWS_REGION="<YOUR_AWS_REGION_HERE>"

ARCH2_VPC_MAIN_NAME="arch2_vpc_main"
ARCH2_PRIVATE_SUBNET_A_NAME="arch2_private_subnet_a"
ARCH2_PRIVATE_SUBNET_B_NAME="arch2_private_subnet_b"
ARCH2_EKS_CLUSTER_C_NAME="arch2_eks_cluster_c"
ARCH2_RDS_PRIMARY_C_NAME="arch2_rds_primary_c"
ARCH2_SECURITYHUB_ACCOUNT_C_NAME="arch2_securityhub_account_c"
ARCH2_GUARDDUTY_DETECTOR_C_NAME="arch2_guardduty_detector_c"
ARCH2_CLOUDTRAIL_MAIN_C_NAME="arch2_cloudtrail_main_c"
ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_NAME="arch2_cloudtrail_logs_bucket_c"
ARCH2_CONFIG_BUCKET_C_NAME="arch2_config_bucket_c"
ARCH2_CONFIG_RECORDER_C_NAME="arch2_config_recorder_c"
ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME="arch2_config_delivery_channel_c"
ARCH2_SSM_SHARING_BLOCK_C_NAME="arch2_ssm_sharing_block_c"
ARCH2_EBS_DEFAULT_ENCRYPTION_C_NAME="arch2_ebs_default_encryption_c"
ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_NAME="arch2_snapshot_block_public_access_c"
ARCH2_ROOT_CREDENTIALS_STATE_C_NAME="arch2_root_credentials_state_c"
ARCH2_SHARED_COMPUTE_ROLE_A3_NAME="arch2_shared_compute_role_a3"
ARCH2_MIXED_POLICY_ROLE_B3_NAME="arch2_mixed_policy_role_b3"

ARCH2_VPC_MAIN_ID=""
ARCH2_PRIVATE_SUBNET_A_ID=""
ARCH2_PRIVATE_SUBNET_B_ID=""
ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN=""
ARCH2_GUARDDUTY_DETECTOR_C_ID=""
ARCH2_CLOUDTRAIL_MAIN_C_ARN=""
ARCH2_SHARED_COMPUTE_ROLE_A3_ARN=""
ARCH2_MIXED_POLICY_ROLE_B3_ARN=""
ARCH2_RDS_PRIMARY_C_ARN=""
ARCH2_EKS_CLUSTER_C_ARN=""

# Normalize names for AWS resource types that do not accept underscores.
ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET="${ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}"
ARCH2_CONFIG_BUCKET_C_BUCKET="${ARCH2_CONFIG_BUCKET_C_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}"
ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER="${ARCH2_RDS_PRIMARY_C_NAME//_/-}"
ARCH2_RDS_DB_SUBNET_GROUP_NAME="${ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER}-subnet-group"
ARCH2_EKS_CLUSTER_C_CLUSTER_NAME="${ARCH2_EKS_CLUSTER_C_NAME//_/-}"
ARCH2_SSM_PUBLIC_SHARING_SETTING_ID="/ssm/documents/console/public-sharing-permission"

# ARCHITECTURE 2 DELETE ORDER (full)

# Resolve arch2_vpc_main ID up front so subnet lookups can stay VPC-scoped and deletion remains safe.
if [[ -z "$ARCH2_VPC_MAIN_ID" ]]; then
  ARCH2_VPC_MAIN_ID="$(aws ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=${ARCH2_VPC_MAIN_NAME}" "Name=tag:Architecture,Values=architecture-2" \
    --region "$AWS_REGION" \
    --query 'Vpcs[0].VpcId' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"
fi

# DELETE arch2_eks_cluster_c — delete EKS cluster first so subnet and IAM role dependencies can be removed later.
if [[ -z "$ARCH2_EKS_CLUSTER_C_ARN" ]]; then
  ARCH2_EKS_CLUSTER_C_ARN="$(aws eks describe-cluster \
    --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
    --region "$AWS_REGION" \
    --query 'cluster.arn' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"
fi
if [[ -n "$ARCH2_EKS_CLUSTER_C_ARN" && "$ARCH2_EKS_CLUSTER_C_ARN" != "None" ]]; then
  # DELETE arch2_eks_cluster_c — remove cluster before private subnets in reverse dependency order.
  aws eks delete-cluster \
    --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true

  # DELETE arch2_eks_cluster_c — wait for cluster deletion so subnet teardown cannot race dependency cleanup.
  aws eks wait cluster-deleted \
    --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_rds_primary_c — delete RDS instance before subnet teardown in reverse dependency order.
if [[ -z "$ARCH2_RDS_PRIMARY_C_ARN" ]]; then
  ARCH2_RDS_PRIMARY_C_ARN="$(aws rds describe-db-instances \
    --db-instance-identifier "$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER" \
    --region "$AWS_REGION" \
    --query 'DBInstances[0].DBInstanceArn' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"
fi
if [[ -n "$ARCH2_RDS_PRIMARY_C_ARN" && "$ARCH2_RDS_PRIMARY_C_ARN" != "None" ]]; then
  # DELETE arch2_rds_primary_c — delete DB instance before subnet and VPC parent resources.
  aws rds delete-db-instance \
    --db-instance-identifier "$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER" \
    --skip-final-snapshot \
    --delete-automated-backups \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true

  # DELETE arch2_rds_primary_c — wait for DB deletion so subnet teardown cannot race active DB networking.
  aws rds wait db-instance-deleted \
    --db-instance-identifier "$ARCH2_RDS_PRIMARY_C_DB_IDENTIFIER" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_rds_primary_c — delete DB subnet group after DB instance teardown.
aws rds delete-db-subnet-group \
  --db-subnet-group-name "$ARCH2_RDS_DB_SUBNET_GROUP_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch2_cloudtrail_main_c — stop and delete trail before deleting its logs bucket.
if [[ -z "$ARCH2_CLOUDTRAIL_MAIN_C_ARN" ]]; then
  ARCH2_CLOUDTRAIL_MAIN_C_ARN="$(aws cloudtrail describe-trails \
    --trail-name-list "$ARCH2_CLOUDTRAIL_MAIN_C_NAME" \
    --region "$AWS_REGION" \
    --query 'trailList[0].TrailARN' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"
fi
if [[ -n "$ARCH2_CLOUDTRAIL_MAIN_C_ARN" && "$ARCH2_CLOUDTRAIL_MAIN_C_ARN" != "None" ]]; then
  # DELETE arch2_cloudtrail_main_c — stop logging before trail deletion.
  aws cloudtrail stop-logging \
    --name "$ARCH2_CLOUDTRAIL_MAIN_C_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true

  # DELETE arch2_cloudtrail_main_c — delete trail before logs bucket deletion.
  aws cloudtrail delete-trail \
    --name "$ARCH2_CLOUDTRAIL_MAIN_C_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_config_delivery_channel_c — stop recorder and delete delivery channel before config bucket deletion.
ARCH2_CONFIG_DELIVERY_CHANNEL_EXISTS_COUNT="$(aws configservice describe-delivery-channels \
  --region "$AWS_REGION" \
  --query "DeliveryChannels[?name=='${ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME}'] | length(@)" \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ "$ARCH2_CONFIG_DELIVERY_CHANNEL_EXISTS_COUNT" != "0" && "$ARCH2_CONFIG_DELIVERY_CHANNEL_EXISTS_COUNT" != "None" ]]; then
  # DELETE arch2_config_delivery_channel_c — stop recorder first so delivery channel can be removed safely.
  aws configservice stop-configuration-recorder \
    --configuration-recorder-name "$ARCH2_CONFIG_RECORDER_C_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true

  # DELETE arch2_config_delivery_channel_c — delete delivery channel before config bucket and recorder.
  aws configservice delete-delivery-channel \
    --delivery-channel-name "$ARCH2_CONFIG_DELIVERY_CHANNEL_C_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_private_subnet_a — resolve subnet ID after EKS/RDS teardown so subnet deletion is dependency-safe.
if [[ -z "$ARCH2_PRIVATE_SUBNET_A_ID" ]]; then
  if [[ -n "$ARCH2_VPC_MAIN_ID" && "$ARCH2_VPC_MAIN_ID" != "None" ]]; then
    ARCH2_PRIVATE_SUBNET_A_ID="$(aws ec2 describe-subnets \
      --filters "Name=vpc-id,Values=${ARCH2_VPC_MAIN_ID}" "Name=tag:Name,Values=${ARCH2_PRIVATE_SUBNET_A_NAME}" \
      --region "$AWS_REGION" \
      --query 'Subnets[0].SubnetId' \
      --output text \
      --no-cli-pager 2>/dev/null || true)"
  else
    ARCH2_PRIVATE_SUBNET_A_ID="$(aws ec2 describe-subnets \
      --filters "Name=tag:Name,Values=${ARCH2_PRIVATE_SUBNET_A_NAME}" "Name=tag:Architecture,Values=architecture-2" \
      --region "$AWS_REGION" \
      --query 'Subnets[0].SubnetId' \
      --output text \
      --no-cli-pager 2>/dev/null || true)"
  fi
fi
if [[ -n "$ARCH2_PRIVATE_SUBNET_A_ID" && "$ARCH2_PRIVATE_SUBNET_A_ID" != "None" ]]; then
  # DELETE arch2_private_subnet_a — check attached ENIs so subnet is never deleted before dependents.
  ARCH2_PRIVATE_SUBNET_A_DEPENDENT_ENI_ID="$(aws ec2 describe-network-interfaces \
    --filters "Name=subnet-id,Values=${ARCH2_PRIVATE_SUBNET_A_ID}" \
    --region "$AWS_REGION" \
    --query 'NetworkInterfaces[0].NetworkInterfaceId' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -z "$ARCH2_PRIVATE_SUBNET_A_DEPENDENT_ENI_ID" || "$ARCH2_PRIVATE_SUBNET_A_DEPENDENT_ENI_ID" == "None" ]]; then
    # DELETE arch2_private_subnet_a — delete subnet only after all dependent ENIs have been removed.
    aws ec2 delete-subnet \
      --subnet-id "$ARCH2_PRIVATE_SUBNET_A_ID" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  fi
fi

# DELETE arch2_private_subnet_b — resolve subnet ID after EKS/RDS teardown so subnet deletion is dependency-safe.
if [[ -z "$ARCH2_PRIVATE_SUBNET_B_ID" ]]; then
  if [[ -n "$ARCH2_VPC_MAIN_ID" && "$ARCH2_VPC_MAIN_ID" != "None" ]]; then
    ARCH2_PRIVATE_SUBNET_B_ID="$(aws ec2 describe-subnets \
      --filters "Name=vpc-id,Values=${ARCH2_VPC_MAIN_ID}" "Name=tag:Name,Values=${ARCH2_PRIVATE_SUBNET_B_NAME}" \
      --region "$AWS_REGION" \
      --query 'Subnets[0].SubnetId' \
      --output text \
      --no-cli-pager 2>/dev/null || true)"
  else
    ARCH2_PRIVATE_SUBNET_B_ID="$(aws ec2 describe-subnets \
      --filters "Name=tag:Name,Values=${ARCH2_PRIVATE_SUBNET_B_NAME}" "Name=tag:Architecture,Values=architecture-2" \
      --region "$AWS_REGION" \
      --query 'Subnets[0].SubnetId' \
      --output text \
      --no-cli-pager 2>/dev/null || true)"
  fi
fi
if [[ -n "$ARCH2_PRIVATE_SUBNET_B_ID" && "$ARCH2_PRIVATE_SUBNET_B_ID" != "None" ]]; then
  # DELETE arch2_private_subnet_b — check attached ENIs so subnet is never deleted before dependents.
  ARCH2_PRIVATE_SUBNET_B_DEPENDENT_ENI_ID="$(aws ec2 describe-network-interfaces \
    --filters "Name=subnet-id,Values=${ARCH2_PRIVATE_SUBNET_B_ID}" \
    --region "$AWS_REGION" \
    --query 'NetworkInterfaces[0].NetworkInterfaceId' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -z "$ARCH2_PRIVATE_SUBNET_B_DEPENDENT_ENI_ID" || "$ARCH2_PRIVATE_SUBNET_B_DEPENDENT_ENI_ID" == "None" ]]; then
    # DELETE arch2_private_subnet_b — delete subnet only after all dependent ENIs have been removed.
    aws ec2 delete-subnet \
      --subnet-id "$ARCH2_PRIVATE_SUBNET_B_ID" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  fi
fi

# DELETE arch2_config_recorder_c — stop and delete recorder after delivery channel teardown.
ARCH2_CONFIG_RECORDER_EXISTS_COUNT="$(aws configservice describe-configuration-recorders \
  --region "$AWS_REGION" \
  --query "ConfigurationRecorders[?name=='${ARCH2_CONFIG_RECORDER_C_NAME}'] | length(@)" \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ "$ARCH2_CONFIG_RECORDER_EXISTS_COUNT" != "0" && "$ARCH2_CONFIG_RECORDER_EXISTS_COUNT" != "None" ]]; then
  # DELETE arch2_config_recorder_c — stop recorder before deletion.
  aws configservice stop-configuration-recorder \
    --configuration-recorder-name "$ARCH2_CONFIG_RECORDER_C_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true

  # DELETE arch2_config_recorder_c — delete configuration recorder after delivery channel is removed.
  aws configservice delete-configuration-recorder \
    --configuration-recorder-name "$ARCH2_CONFIG_RECORDER_C_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_cloudtrail_logs_bucket_c — enumerate current object keys so non-versioned objects are removed before bucket delete.
ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_OBJECT_KEYS="$(aws s3api list-objects-v2 \
  --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
  --region "$AWS_REGION" \
  --query 'Contents[].Key' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_OBJECT_KEYS" && "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_OBJECT_KEYS" != "None" ]]; then
  for object_key in $ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_OBJECT_KEYS; do
    # DELETE arch2_cloudtrail_logs_bucket_c — remove each current object so bucket deletion can proceed.
    aws s3api delete-object \
      --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
      --key "$object_key" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done
fi

# DELETE arch2_cloudtrail_logs_bucket_c — enumerate object versions so versioned data cannot block bucket deletion.
ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_VERSIONS="$(aws s3api list-object-versions \
  --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
  --region "$AWS_REGION" \
  --query 'Versions[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_VERSIONS" && "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_VERSIONS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch2_cloudtrail_logs_bucket_c — remove each object version before final bucket delete.
    aws s3api delete-object \
      --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_VERSIONS"
fi

# DELETE arch2_cloudtrail_logs_bucket_c — enumerate delete markers so bucket version metadata is fully cleared.
ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_DELETE_MARKERS="$(aws s3api list-object-versions \
  --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
  --region "$AWS_REGION" \
  --query 'DeleteMarkers[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_DELETE_MARKERS" && "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_DELETE_MARKERS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch2_cloudtrail_logs_bucket_c — remove each delete marker so bucket deletion is not blocked.
    aws s3api delete-object \
      --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_DELETE_MARKERS"
fi

# DELETE arch2_cloudtrail_logs_bucket_c — delete bucket after object/version cleanup.
aws s3api delete-bucket \
  --bucket "$ARCH2_CLOUDTRAIL_LOGS_BUCKET_C_BUCKET" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch2_config_bucket_c — enumerate current object keys so non-versioned objects are removed before bucket delete.
ARCH2_CONFIG_BUCKET_C_OBJECT_KEYS="$(aws s3api list-objects-v2 \
  --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
  --region "$AWS_REGION" \
  --query 'Contents[].Key' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH2_CONFIG_BUCKET_C_OBJECT_KEYS" && "$ARCH2_CONFIG_BUCKET_C_OBJECT_KEYS" != "None" ]]; then
  for object_key in $ARCH2_CONFIG_BUCKET_C_OBJECT_KEYS; do
    # DELETE arch2_config_bucket_c — remove each current object so bucket deletion can proceed.
    aws s3api delete-object \
      --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
      --key "$object_key" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done
fi

# DELETE arch2_config_bucket_c — enumerate object versions so versioned data cannot block bucket deletion.
ARCH2_CONFIG_BUCKET_C_VERSIONS="$(aws s3api list-object-versions \
  --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
  --region "$AWS_REGION" \
  --query 'Versions[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH2_CONFIG_BUCKET_C_VERSIONS" && "$ARCH2_CONFIG_BUCKET_C_VERSIONS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch2_config_bucket_c — remove each object version before final bucket delete.
    aws s3api delete-object \
      --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH2_CONFIG_BUCKET_C_VERSIONS"
fi

# DELETE arch2_config_bucket_c — enumerate delete markers so bucket version metadata is fully cleared.
ARCH2_CONFIG_BUCKET_C_DELETE_MARKERS="$(aws s3api list-object-versions \
  --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
  --region "$AWS_REGION" \
  --query 'DeleteMarkers[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH2_CONFIG_BUCKET_C_DELETE_MARKERS" && "$ARCH2_CONFIG_BUCKET_C_DELETE_MARKERS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch2_config_bucket_c — remove each delete marker so bucket deletion is not blocked.
    aws s3api delete-object \
      --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH2_CONFIG_BUCKET_C_DELETE_MARKERS"
fi

# DELETE arch2_config_bucket_c — delete bucket after object/version cleanup.
aws s3api delete-bucket \
  --bucket "$ARCH2_CONFIG_BUCKET_C_BUCKET" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch2_securityhub_account_c — disable Security Hub account setting after dependent resources are removed.
if [[ -z "$ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN" ]]; then
  ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN="$(aws securityhub describe-hub \
    --region "$AWS_REGION" \
    --query 'HubArn' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"
fi
if [[ -n "$ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN" && "$ARCH2_SECURITYHUB_ACCOUNT_C_HUB_ARN" != "None" ]]; then
  aws securityhub disable-security-hub \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_guardduty_detector_c — delete detector after dependent runtime resources are removed.
if [[ -z "$ARCH2_GUARDDUTY_DETECTOR_C_ID" ]]; then
  ARCH2_GUARDDUTY_DETECTOR_C_ID="$(aws guardduty list-detectors \
    --region "$AWS_REGION" \
    --query 'DetectorIds[0]' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"
fi
if [[ -n "$ARCH2_GUARDDUTY_DETECTOR_C_ID" && "$ARCH2_GUARDDUTY_DETECTOR_C_ID" != "None" ]]; then
  aws guardduty delete-detector \
    --detector-id "$ARCH2_GUARDDUTY_DETECTOR_C_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_ssm_sharing_block_c — revert account setting after architecture-specific teardown.
ARCH2_SSM_SHARING_BLOCK_C_VALUE="$(aws ssm get-service-setting \
  --setting-id "$ARCH2_SSM_PUBLIC_SHARING_SETTING_ID" \
  --region "$AWS_REGION" \
  --query 'ServiceSetting.SettingValue' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ "$ARCH2_SSM_SHARING_BLOCK_C_VALUE" == "Disable" ]]; then
  aws ssm update-service-setting \
    --setting-id "$ARCH2_SSM_PUBLIC_SHARING_SETTING_ID" \
    --setting-value "Enable" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_ebs_default_encryption_c — disable account-level default EBS encryption setting.
ARCH2_EBS_ENCRYPTION_BY_DEFAULT="$(aws ec2 get-ebs-encryption-by-default \
  --region "$AWS_REGION" \
  --query 'EbsEncryptionByDefault' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ "$ARCH2_EBS_ENCRYPTION_BY_DEFAULT" == "True" ]]; then
  aws ec2 disable-ebs-encryption-by-default \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_snapshot_block_public_access_c — disable account-level snapshot block public access setting.
ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE="$(aws ec2 get-snapshot-block-public-access-state \
  --region "$AWS_REGION" \
  --query 'State' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ "$ARCH2_SNAPSHOT_BLOCK_PUBLIC_ACCESS_C_STATE" != "unblocked" ]]; then
  aws ec2 disable-snapshot-block-public-access \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_root_credentials_state_c — no delete API exists; capture root-principal state for teardown evidence.
ARCH2_ROOT_ACCOUNT_ACCESS_KEYS_PRESENT="$(aws iam get-account-summary \
  --query 'SummaryMap.AccountAccessKeysPresent' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
ARCH2_ROOT_ACCOUNT_MFA_ENABLED="$(aws iam get-account-summary \
  --query 'SummaryMap.AccountMFAEnabled' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"

# DELETE arch2_shared_compute_role_a3 — resolve role ARN so role-specific policy detach and delete can proceed.
if [[ -z "$ARCH2_SHARED_COMPUTE_ROLE_A3_ARN" ]]; then
  ARCH2_SHARED_COMPUTE_ROLE_A3_ARN="$(aws iam get-role \
    --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
    --query 'Role.Arn' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"
fi
if [[ -n "$ARCH2_SHARED_COMPUTE_ROLE_A3_ARN" && "$ARCH2_SHARED_COMPUTE_ROLE_A3_ARN" != "None" ]]; then
  # DELETE arch2_shared_compute_role_a3 — list inline policies so each can be removed before role deletion.
  ARCH2_A3_INLINE_POLICY_NAMES="$(aws iam list-role-policies \
    --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
    --query 'PolicyNames' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -n "$ARCH2_A3_INLINE_POLICY_NAMES" && "$ARCH2_A3_INLINE_POLICY_NAMES" != "None" ]]; then
    for policy_name in $ARCH2_A3_INLINE_POLICY_NAMES; do
      # DELETE arch2_shared_compute_role_a3 — remove each inline policy before deleting the role.
      aws iam delete-role-policy \
        --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
        --policy-name "$policy_name" \
        --no-cli-pager 2>/dev/null || true
    done
  fi

  # DELETE arch2_shared_compute_role_a3 — list attached managed policies so they can be detached before role deletion.
  ARCH2_A3_ATTACHED_POLICY_ARNS="$(aws iam list-attached-role-policies \
    --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
    --query 'AttachedPolicies[].PolicyArn' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -n "$ARCH2_A3_ATTACHED_POLICY_ARNS" && "$ARCH2_A3_ATTACHED_POLICY_ARNS" != "None" ]]; then
    for policy_arn in $ARCH2_A3_ATTACHED_POLICY_ARNS; do
      # DELETE arch2_shared_compute_role_a3 — detach each managed policy before deleting the role.
      aws iam detach-role-policy \
        --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
        --policy-arn "$policy_arn" \
        --no-cli-pager 2>/dev/null || true
    done
  fi

  # DELETE arch2_shared_compute_role_a3 — list linked instance profiles so role can be removed from each profile first.
  ARCH2_A3_INSTANCE_PROFILE_NAMES="$(aws iam list-instance-profiles-for-role \
    --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
    --query 'InstanceProfiles[].InstanceProfileName' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -n "$ARCH2_A3_INSTANCE_PROFILE_NAMES" && "$ARCH2_A3_INSTANCE_PROFILE_NAMES" != "None" ]]; then
    for profile_name in $ARCH2_A3_INSTANCE_PROFILE_NAMES; do
      # DELETE arch2_shared_compute_role_a3 — remove role from each instance profile before deleting role.
      aws iam remove-role-from-instance-profile \
        --instance-profile-name "$profile_name" \
        --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
        --no-cli-pager 2>/dev/null || true
    done
  fi

  # DELETE arch2_shared_compute_role_a3 — delete Group A IAM role after inline/managed/profile detach cleanup.
  aws iam delete-role \
    --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_mixed_policy_role_b3 — resolve role ARN so role-specific policy detach and delete can proceed.
if [[ -z "$ARCH2_MIXED_POLICY_ROLE_B3_ARN" ]]; then
  ARCH2_MIXED_POLICY_ROLE_B3_ARN="$(aws iam get-role \
    --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
    --query 'Role.Arn' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"
fi
if [[ -n "$ARCH2_MIXED_POLICY_ROLE_B3_ARN" && "$ARCH2_MIXED_POLICY_ROLE_B3_ARN" != "None" ]]; then
  # DELETE arch2_mixed_policy_role_b3 — list inline policies so each can be removed before role deletion.
  ARCH2_B3_INLINE_POLICY_NAMES="$(aws iam list-role-policies \
    --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
    --query 'PolicyNames' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -n "$ARCH2_B3_INLINE_POLICY_NAMES" && "$ARCH2_B3_INLINE_POLICY_NAMES" != "None" ]]; then
    for policy_name in $ARCH2_B3_INLINE_POLICY_NAMES; do
      # DELETE arch2_mixed_policy_role_b3 — remove each inline policy before deleting the role.
      aws iam delete-role-policy \
        --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
        --policy-name "$policy_name" \
        --no-cli-pager 2>/dev/null || true
    done
  fi

  # DELETE arch2_mixed_policy_role_b3 — list attached managed policies so they can be detached before role deletion.
  ARCH2_B3_ATTACHED_POLICY_ARNS="$(aws iam list-attached-role-policies \
    --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
    --query 'AttachedPolicies[].PolicyArn' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -n "$ARCH2_B3_ATTACHED_POLICY_ARNS" && "$ARCH2_B3_ATTACHED_POLICY_ARNS" != "None" ]]; then
    for policy_arn in $ARCH2_B3_ATTACHED_POLICY_ARNS; do
      # DELETE arch2_mixed_policy_role_b3 — detach each managed policy before deleting the role.
      aws iam detach-role-policy \
        --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
        --policy-arn "$policy_arn" \
        --no-cli-pager 2>/dev/null || true
    done
  fi

  # DELETE arch2_mixed_policy_role_b3 — list linked instance profiles so role can be removed from each profile first.
  ARCH2_B3_INSTANCE_PROFILE_NAMES="$(aws iam list-instance-profiles-for-role \
    --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
    --query 'InstanceProfiles[].InstanceProfileName' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -n "$ARCH2_B3_INSTANCE_PROFILE_NAMES" && "$ARCH2_B3_INSTANCE_PROFILE_NAMES" != "None" ]]; then
    for profile_name in $ARCH2_B3_INSTANCE_PROFILE_NAMES; do
      # DELETE arch2_mixed_policy_role_b3 — remove role from each instance profile before deleting role.
      aws iam remove-role-from-instance-profile \
        --instance-profile-name "$profile_name" \
        --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
        --no-cli-pager 2>/dev/null || true
    done
  fi

  # DELETE arch2_mixed_policy_role_b3 — delete Group B IAM role after inline/managed/profile detach cleanup.
  aws iam delete-role \
    --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch2_vpc_main — resolve VPC ID only after subnets are deleted.
if [[ -z "$ARCH2_VPC_MAIN_ID" ]]; then
  ARCH2_VPC_MAIN_ID="$(aws ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=${ARCH2_VPC_MAIN_NAME}" "Name=tag:Architecture,Values=architecture-2" \
    --region "$AWS_REGION" \
    --query 'Vpcs[0].VpcId' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"
fi
if [[ -n "$ARCH2_VPC_MAIN_ID" && "$ARCH2_VPC_MAIN_ID" != "None" ]]; then
  # DELETE arch2_vpc_main — delete VPC last because it is the root dependency for Architecture 2 network resources.
  aws ec2 delete-vpc \
    --vpc-id "$ARCH2_VPC_MAIN_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi
