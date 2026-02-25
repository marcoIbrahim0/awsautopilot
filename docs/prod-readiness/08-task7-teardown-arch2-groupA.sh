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

ARCH2_EKS_CLUSTER_C_ARN=""
ARCH2_SHARED_COMPUTE_ROLE_A3_ARN=""

# Normalize names for AWS resource types that do not accept underscores.
ARCH2_EKS_CLUSTER_C_CLUSTER_NAME="${ARCH2_EKS_CLUSTER_C_NAME//_/-}"

# ARCHITECTURE 2 DELETE ORDER (Group A subset only)

# DELETE arch2_eks_cluster_c (dependency check) — verify EKS cluster is absent before deleting the Group A IAM role.
ARCH2_EKS_CLUSTER_C_ARN="$(aws eks describe-cluster \
  --name "$ARCH2_EKS_CLUSTER_C_CLUSTER_NAME" \
  --region "$AWS_REGION" \
  --query 'cluster.arn' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"

if [[ -n "$ARCH2_EKS_CLUSTER_C_ARN" && "$ARCH2_EKS_CLUSTER_C_ARN" != "None" ]]; then
  echo "Skipping ${ARCH2_SHARED_COMPUTE_ROLE_A3_NAME} teardown because ${ARCH2_EKS_CLUSTER_C_CLUSTER_NAME} still exists." >&2
  echo "Delete arch2_eks_cluster_c first (or run 08-task7-teardown-arch2-full.sh)." >&2
  exit 1
fi

# DELETE arch2_shared_compute_role_a3 — resolve role ARN so role-specific policy detach and delete can proceed.
ARCH2_SHARED_COMPUTE_ROLE_A3_ARN="$(aws iam get-role \
  --role-name "$ARCH2_SHARED_COMPUTE_ROLE_A3_NAME" \
  --query 'Role.Arn' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
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
