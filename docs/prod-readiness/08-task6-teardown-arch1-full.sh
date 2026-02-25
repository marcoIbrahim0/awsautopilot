#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Variables block (Architecture 1 variables from Section 3 that this script uses)
# ---------------------------------------------------------------------------
ACCOUNT_ID="<YOUR_ACCOUNT_ID_HERE>"
AWS_REGION="<YOUR_AWS_REGION_HERE>"

ARCH1_VPC_MAIN_NAME="arch1_vpc_main"
ARCH1_PUBLIC_SUBNET_A_NAME="arch1_public_subnet_a"
ARCH1_PRIVATE_SUBNET_A_NAME="arch1_private_subnet_a"
ARCH1_SG_APP_B2_NAME="arch1_sg_app_b2"
ARCH1_SG_DEPENDENCY_A2_NAME="arch1_sg_dependency_a2"
ARCH1_SG_REFERENCE_A2_NAME="arch1_sg_reference_a2"
ARCH1_APP_SERVER_A2_NAME="arch1_app_server_a2"
ARCH1_CLAIMS_DB_A2_NAME="arch1_claims_db_a2"
ARCH1_BUCKET_WEBSITE_A1_NAME="arch1_bucket_website_a1"
ARCH1_BUCKET_POLICY_WEBSITE_A1_NAME="arch1_bucket_policy_website_a1"
ARCH1_BUCKET_EVIDENCE_B1_NAME="arch1_bucket_evidence_b1"
ARCH1_BUCKET_POLICY_EVIDENCE_B1_NAME="arch1_bucket_policy_evidence_b1"
ARCH1_BUCKET_PAB_EVIDENCE_B1_NAME="arch1_bucket_pab_evidence_b1"
ARCH1_BUCKET_INGEST_C_NAME="arch1_bucket_ingest_c"
ARCH1_BUCKET_POLICY_INGEST_C_NAME="arch1_bucket_policy_ingest_c"
ARCH1_BUCKET_LOGGING_TARGET_C_NAME="arch1_bucket_logging_target_c"
ARCH1_ACCOUNT_PAB_C_NAME="arch1_account_pab_c"
ARCH1_WEB_INGEST_SERVICE_NAME="arch1_web_ingest_service"

ARCH1_VPC_CIDR="10.10.0.0/16"
ARCH1_PUBLIC_SUBNET_A_CIDR="10.10.1.0/24"
ARCH1_PRIVATE_SUBNET_A_CIDR="10.10.11.0/24"

SSH_PORT="22"
HTTPS_PORT="443"
POSTGRES_PORT="5432"
APP_PORT="8080"
PUBLIC_CIDR_ANY="0.0.0.0/0"
INTERNAL_VPC_CIDR="10.0.0.0/16"
ADMIN_HOST_CIDR="203.0.113.10/32"

B1_DATA_PIPELINE_ROLE_ARN_PATTERN="arn:aws:iam::<ACCOUNT_ID>:role/DataPipelineRole"
B1_DATA_PIPELINE_ROLE_ARN_VALUE="arn:aws:iam::111122223333:role/DataPipelineRole"
B1_CROSS_ACCOUNT_ID="123456789012"

TAG_PROJECT="Project=AWS-Security-Autopilot"
TAG_ENVIRONMENT="Environment=security-test"
TAG_MANAGED_BY="ManagedBy=test-script"
TAG_ARCH1="Architecture=architecture-1"
TAG_GROUP_A1="BlastRadiusTest=website-hosting"
TAG_GROUP_A2="BlastRadiusTest=sg-dependency-chain"
TAG_GROUP_B1="ContextTest=existing-complex-policy"
TAG_GROUP_B2="ContextTest=mixed-sg-rules"
TAG_TEST_GROUP="TestGroup=architecture-1"

TAG_PROJECT_VALUE="${TAG_PROJECT#*=}"
TAG_ENVIRONMENT_VALUE="${TAG_ENVIRONMENT#*=}"
TAG_MANAGED_BY_VALUE="${TAG_MANAGED_BY#*=}"
TAG_ARCH1_VALUE="${TAG_ARCH1#*=}"
TAG_GROUP_A1_VALUE="${TAG_GROUP_A1#*=}"
TAG_GROUP_A2_VALUE="${TAG_GROUP_A2#*=}"
TAG_GROUP_B1_VALUE="${TAG_GROUP_B1#*=}"
TAG_GROUP_B2_VALUE="${TAG_GROUP_B2#*=}"
TAG_TEST_GROUP_VALUE="${TAG_TEST_GROUP#*=}"

# Normalize names for AWS resource types that do not accept underscores.
ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME="${ARCH1_BUCKET_WEBSITE_A1_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}"
ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME="${ARCH1_BUCKET_EVIDENCE_B1_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}"
ARCH1_BUCKET_INGEST_C_BUCKET_NAME="${ARCH1_BUCKET_INGEST_C_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}"
ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME="${ARCH1_BUCKET_LOGGING_TARGET_C_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}"
ARCH1_CLAIMS_DB_A2_IDENTIFIER="${ARCH1_CLAIMS_DB_A2_NAME//_/-}"
ARCH1_DB_SUBNET_GROUP_NAME="${ARCH1_CLAIMS_DB_A2_IDENTIFIER}-subnet-group"
ARCH1_ECS_CLUSTER_NAME="${ARCH1_WEB_INGEST_SERVICE_NAME}-cluster"
ARCH1_ECS_TASK_FAMILY_NAME="${ARCH1_WEB_INGEST_SERVICE_NAME}-taskdef"
ARCH1_ECS_EXECUTION_ROLE_NAME="${ARCH1_WEB_INGEST_SERVICE_NAME}-exec-role"
ARCH1_RDS_MASTER_USERNAME="<YOUR_RDS_MASTER_USERNAME_HERE>"
ARCH1_RDS_MASTER_PASSWORD="<YOUR_RDS_MASTER_PASSWORD_HERE>"

# ARCHITECTURE 1 DELETE ORDER (full)

# DELETE arch1_web_ingest_service — resolve service ARN first so the top-most dependent workload is removed before SG/subnet deletion.
ARCH1_WEB_INGEST_SERVICE_ARN="$(aws ecs describe-services \
  --cluster "$ARCH1_ECS_CLUSTER_NAME" \
  --services "$ARCH1_WEB_INGEST_SERVICE_NAME" \
  --region "$AWS_REGION" \
  --query 'services[0].serviceArn' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_WEB_INGEST_SERVICE_ARN" && "$ARCH1_WEB_INGEST_SERVICE_ARN" != "None" ]]; then
  # DELETE arch1_web_ingest_service — scale desired count to zero before force-delete so task ENIs are drained first.
  aws ecs update-service \
    --cluster "$ARCH1_ECS_CLUSTER_NAME" \
    --service "$ARCH1_WEB_INGEST_SERVICE_NAME" \
    --desired-count 0 \
    --region "$AWS_REGION" \
    --no-cli-pager >/dev/null 2>&1 || true

  # DELETE arch1_web_ingest_service — delete ECS service before SG and subnet resources it depends on.
  aws ecs delete-service \
    --cluster "$ARCH1_ECS_CLUSTER_NAME" \
    --service "$ARCH1_WEB_INGEST_SERVICE_NAME" \
    --force \
    --region "$AWS_REGION" \
    --no-cli-pager >/dev/null 2>&1 || true

  # DELETE arch1_web_ingest_service — wait until service is inactive so dependent network interfaces are released.
  aws ecs wait services-inactive \
    --cluster "$ARCH1_ECS_CLUSTER_NAME" \
    --services "$ARCH1_WEB_INGEST_SERVICE_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch1_web_ingest_service — list active task definitions so service family artifacts can be retired after service removal.
ARCH1_WEB_INGEST_ACTIVE_TASK_DEFINITION_ARNS="$(aws ecs list-task-definitions \
  --family-prefix "$ARCH1_ECS_TASK_FAMILY_NAME" \
  --status ACTIVE \
  --region "$AWS_REGION" \
  --query 'taskDefinitionArns' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_WEB_INGEST_ACTIVE_TASK_DEFINITION_ARNS" && "$ARCH1_WEB_INGEST_ACTIVE_TASK_DEFINITION_ARNS" != "None" ]]; then
  for task_definition_arn in $ARCH1_WEB_INGEST_ACTIVE_TASK_DEFINITION_ARNS; do
    # DELETE arch1_web_ingest_service — deregister active task definitions so runtime family artifacts are cleaned up.
    aws ecs deregister-task-definition \
      --task-definition "$task_definition_arn" \
      --region "$AWS_REGION" \
      --no-cli-pager >/dev/null 2>&1 || true
  done
fi

# DELETE arch1_web_ingest_service — resolve ECS cluster ARN so the cluster can be removed after service deletion.
ARCH1_ECS_CLUSTER_ARN="$(aws ecs describe-clusters \
  --clusters "$ARCH1_ECS_CLUSTER_NAME" \
  --region "$AWS_REGION" \
  --query 'clusters[0].clusterArn' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_ECS_CLUSTER_ARN" && "$ARCH1_ECS_CLUSTER_ARN" != "None" ]]; then
  # DELETE arch1_web_ingest_service — delete ECS cluster now that no services are active.
  aws ecs delete-cluster \
    --cluster "$ARCH1_ECS_CLUSTER_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager >/dev/null 2>&1 || true
fi

# DELETE arch1_web_ingest_service — delete the ECS log group because it is an implementation dependency of this service.
aws logs delete-log-group \
  --log-group-name "/ecs/${ARCH1_WEB_INGEST_SERVICE_NAME}" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_web_ingest_service — detach execution role policy before deleting the role used only by this service.
aws iam detach-role-policy \
  --role-name "$ARCH1_ECS_EXECUTION_ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_web_ingest_service — delete execution role after policy detach to finish service-level IAM teardown.
aws iam delete-role \
  --role-name "$ARCH1_ECS_EXECUTION_ROLE_NAME" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_app_server_a2 — resolve EC2 instance ID so compute dependency is removed before SG/subnet teardown.
ARCH1_APP_SERVER_A2_ID="$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${ARCH1_APP_SERVER_A2_NAME}" "Name=tag:Architecture,Values=architecture-1" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --region "$AWS_REGION" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_APP_SERVER_A2_ID" && "$ARCH1_APP_SERVER_A2_ID" != "None" ]]; then
  # DELETE arch1_app_server_a2 — terminate EC2 dependency before deleting SG and subnet parents.
  aws ec2 terminate-instances \
    --instance-ids "$ARCH1_APP_SERVER_A2_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager >/dev/null 2>&1 || true

  # DELETE arch1_app_server_a2 — wait for termination so SG/subnet deletion remains dependency-safe.
  aws ec2 wait instance-terminated \
    --instance-ids "$ARCH1_APP_SERVER_A2_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch1_claims_db_a2 — resolve DB identifier state so database dependency is removed before SG/subnet teardown.
ARCH1_CLAIMS_DB_A2_CURRENT_ID="$(aws rds describe-db-instances \
  --db-instance-identifier "$ARCH1_CLAIMS_DB_A2_IDENTIFIER" \
  --region "$AWS_REGION" \
  --query 'DBInstances[0].DBInstanceIdentifier' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_CLAIMS_DB_A2_CURRENT_ID" && "$ARCH1_CLAIMS_DB_A2_CURRENT_ID" != "None" ]]; then
  # DELETE arch1_claims_db_a2 — delete DB instance before deleting SG/subnet resources it depends on.
  aws rds delete-db-instance \
    --db-instance-identifier "$ARCH1_CLAIMS_DB_A2_IDENTIFIER" \
    --skip-final-snapshot \
    --delete-automated-backups \
    --region "$AWS_REGION" \
    --no-cli-pager >/dev/null 2>&1 || true

  # DELETE arch1_claims_db_a2 — wait for DB removal so SG/subnet teardown cannot race active DB networking.
  aws rds wait db-instance-deleted \
    --db-instance-identifier "$ARCH1_CLAIMS_DB_A2_IDENTIFIER" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch1_claims_db_a2 — delete DB subnet group after DB deletion to remove remaining RDS dependency artifacts.
aws rds delete-db-subnet-group \
  --db-subnet-group-name "$ARCH1_DB_SUBNET_GROUP_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_sg_reference_a2 — resolve SG-B ID so it is removed before SG-A per reverse dependency order.
ARCH1_SG_REFERENCE_A2_ID="$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${ARCH1_SG_REFERENCE_A2_NAME}" "Name=tag:Architecture,Values=architecture-1" \
  --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_SG_REFERENCE_A2_ID" && "$ARCH1_SG_REFERENCE_A2_ID" != "None" ]]; then
  # DELETE arch1_sg_reference_a2 — delete SG-B before SG-A and VPC to satisfy dependency graph.
  aws ec2 delete-security-group \
    --group-id "$ARCH1_SG_REFERENCE_A2_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch1_bucket_policy_website_a1 — remove website bucket policy before deleting website bucket.
aws s3api delete-bucket-policy \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_bucket_policy_evidence_b1 — remove evidence bucket policy before deleting evidence bucket.
aws s3api delete-bucket-policy \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_bucket_pab_evidence_b1 — remove evidence bucket PAB object before deleting parent bucket.
aws s3api delete-public-access-block \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_bucket_policy_ingest_c — remove ingest bucket policy before deleting ingest bucket.
aws s3api delete-bucket-policy \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_sg_app_b2 — resolve SG ID so it is deleted only after service-level dependents are gone.
ARCH1_SG_APP_B2_ID="$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${ARCH1_SG_APP_B2_NAME}" "Name=tag:Architecture,Values=architecture-1" \
  --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_SG_APP_B2_ID" && "$ARCH1_SG_APP_B2_ID" != "None" ]]; then
  # DELETE arch1_sg_app_b2 — check for attached ENIs so SG is never deleted before live dependents.
  ARCH1_SG_APP_B2_DEPENDENT_ENI_ID="$(aws ec2 describe-network-interfaces \
    --filters "Name=group-id,Values=${ARCH1_SG_APP_B2_ID}" \
    --region "$AWS_REGION" \
    --query 'NetworkInterfaces[0].NetworkInterfaceId' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -z "$ARCH1_SG_APP_B2_DEPENDENT_ENI_ID" || "$ARCH1_SG_APP_B2_DEPENDENT_ENI_ID" == "None" ]]; then
    # DELETE arch1_sg_app_b2 — delete SG only after dependent ENIs have been removed by upstream teardown.
    aws ec2 delete-security-group \
      --group-id "$ARCH1_SG_APP_B2_ID" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  fi
fi

# DELETE arch1_sg_dependency_a2 — resolve SG-A ID so it can be deleted after instance/DB/SG-B dependents are gone.
ARCH1_SG_DEPENDENCY_A2_ID="$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${ARCH1_SG_DEPENDENCY_A2_NAME}" "Name=tag:Architecture,Values=architecture-1" \
  --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_SG_DEPENDENCY_A2_ID" && "$ARCH1_SG_DEPENDENCY_A2_ID" != "None" ]]; then
  # DELETE arch1_sg_dependency_a2 — check for attached ENIs so SG-A is deleted only when dependencies are clear.
  ARCH1_SG_DEPENDENCY_A2_DEPENDENT_ENI_ID="$(aws ec2 describe-network-interfaces \
    --filters "Name=group-id,Values=${ARCH1_SG_DEPENDENCY_A2_ID}" \
    --region "$AWS_REGION" \
    --query 'NetworkInterfaces[0].NetworkInterfaceId' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -z "$ARCH1_SG_DEPENDENCY_A2_DEPENDENT_ENI_ID" || "$ARCH1_SG_DEPENDENCY_A2_DEPENDENT_ENI_ID" == "None" ]]; then
    # DELETE arch1_sg_dependency_a2 — delete SG-A after all dependent attachments are removed.
    aws ec2 delete-security-group \
      --group-id "$ARCH1_SG_DEPENDENCY_A2_ID" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  fi
fi

# DELETE arch1_public_subnet_a — resolve subnet ID after service/instance teardown so subnet delete is dependency-safe.
ARCH1_PUBLIC_SUBNET_A_ID="$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=${ARCH1_PUBLIC_SUBNET_A_NAME}" "Name=tag:Architecture,Values=architecture-1" \
  --region "$AWS_REGION" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_PUBLIC_SUBNET_A_ID" && "$ARCH1_PUBLIC_SUBNET_A_ID" != "None" ]]; then
  # DELETE arch1_public_subnet_a — check subnet ENIs so subnet is never deleted before dependent interfaces.
  ARCH1_PUBLIC_SUBNET_A_DEPENDENT_ENI_ID="$(aws ec2 describe-network-interfaces \
    --filters "Name=subnet-id,Values=${ARCH1_PUBLIC_SUBNET_A_ID}" \
    --region "$AWS_REGION" \
    --query 'NetworkInterfaces[0].NetworkInterfaceId' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -z "$ARCH1_PUBLIC_SUBNET_A_DEPENDENT_ENI_ID" || "$ARCH1_PUBLIC_SUBNET_A_DEPENDENT_ENI_ID" == "None" ]]; then
    # DELETE arch1_public_subnet_a — delete subnet only after all dependent ENIs have been removed.
    aws ec2 delete-subnet \
      --subnet-id "$ARCH1_PUBLIC_SUBNET_A_ID" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  fi
fi

# DELETE arch1_private_subnet_a — resolve private subnet ID after DB teardown so subnet delete is dependency-safe.
ARCH1_PRIVATE_SUBNET_A_ID="$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=${ARCH1_PRIVATE_SUBNET_A_NAME}" "Name=tag:Architecture,Values=architecture-1" \
  --region "$AWS_REGION" \
  --query 'Subnets[0].SubnetId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_PRIVATE_SUBNET_A_ID" && "$ARCH1_PRIVATE_SUBNET_A_ID" != "None" ]]; then
  # DELETE arch1_private_subnet_a — check subnet ENIs so subnet is never deleted before dependent interfaces.
  ARCH1_PRIVATE_SUBNET_A_DEPENDENT_ENI_ID="$(aws ec2 describe-network-interfaces \
    --filters "Name=subnet-id,Values=${ARCH1_PRIVATE_SUBNET_A_ID}" \
    --region "$AWS_REGION" \
    --query 'NetworkInterfaces[0].NetworkInterfaceId' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -z "$ARCH1_PRIVATE_SUBNET_A_DEPENDENT_ENI_ID" || "$ARCH1_PRIVATE_SUBNET_A_DEPENDENT_ENI_ID" == "None" ]]; then
    # DELETE arch1_private_subnet_a — delete subnet only after all dependent ENIs have been removed.
    aws ec2 delete-subnet \
      --subnet-id "$ARCH1_PRIVATE_SUBNET_A_ID" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  fi
fi

# DELETE arch1_bucket_website_a1 — enumerate current object keys so non-versioned objects are removed before bucket delete.
ARCH1_BUCKET_WEBSITE_A1_OBJECT_KEYS="$(aws s3api list-objects-v2 \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'Contents[].Key' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_WEBSITE_A1_OBJECT_KEYS" && "$ARCH1_BUCKET_WEBSITE_A1_OBJECT_KEYS" != "None" ]]; then
  for object_key in $ARCH1_BUCKET_WEBSITE_A1_OBJECT_KEYS; do
    # DELETE arch1_bucket_website_a1 — remove each current object so bucket deletion can proceed.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
      --key "$object_key" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done
fi

# DELETE arch1_bucket_website_a1 — enumerate object versions so versioned data cannot block bucket deletion.
ARCH1_BUCKET_WEBSITE_A1_VERSIONS="$(aws s3api list-object-versions \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'Versions[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_WEBSITE_A1_VERSIONS" && "$ARCH1_BUCKET_WEBSITE_A1_VERSIONS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch1_bucket_website_a1 — remove each object version before final bucket delete.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH1_BUCKET_WEBSITE_A1_VERSIONS"
fi

# DELETE arch1_bucket_website_a1 — enumerate delete markers so bucket version metadata is fully cleared.
ARCH1_BUCKET_WEBSITE_A1_DELETE_MARKERS="$(aws s3api list-object-versions \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'DeleteMarkers[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_WEBSITE_A1_DELETE_MARKERS" && "$ARCH1_BUCKET_WEBSITE_A1_DELETE_MARKERS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch1_bucket_website_a1 — remove each delete marker so bucket deletion is not blocked.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH1_BUCKET_WEBSITE_A1_DELETE_MARKERS"
fi

# DELETE arch1_bucket_website_a1 — delete bucket after policy/object/version cleanup.
aws s3api delete-bucket \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_bucket_evidence_b1 — enumerate current object keys so non-versioned objects are removed before bucket delete.
ARCH1_BUCKET_EVIDENCE_B1_OBJECT_KEYS="$(aws s3api list-objects-v2 \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'Contents[].Key' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_EVIDENCE_B1_OBJECT_KEYS" && "$ARCH1_BUCKET_EVIDENCE_B1_OBJECT_KEYS" != "None" ]]; then
  for object_key in $ARCH1_BUCKET_EVIDENCE_B1_OBJECT_KEYS; do
    # DELETE arch1_bucket_evidence_b1 — remove each current object so bucket deletion can proceed.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
      --key "$object_key" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done
fi

# DELETE arch1_bucket_evidence_b1 — enumerate object versions so versioned data cannot block bucket deletion.
ARCH1_BUCKET_EVIDENCE_B1_VERSIONS="$(aws s3api list-object-versions \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'Versions[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_EVIDENCE_B1_VERSIONS" && "$ARCH1_BUCKET_EVIDENCE_B1_VERSIONS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch1_bucket_evidence_b1 — remove each object version before final bucket delete.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH1_BUCKET_EVIDENCE_B1_VERSIONS"
fi

# DELETE arch1_bucket_evidence_b1 — enumerate delete markers so bucket version metadata is fully cleared.
ARCH1_BUCKET_EVIDENCE_B1_DELETE_MARKERS="$(aws s3api list-object-versions \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'DeleteMarkers[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_EVIDENCE_B1_DELETE_MARKERS" && "$ARCH1_BUCKET_EVIDENCE_B1_DELETE_MARKERS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch1_bucket_evidence_b1 — remove each delete marker so bucket deletion is not blocked.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH1_BUCKET_EVIDENCE_B1_DELETE_MARKERS"
fi

# DELETE arch1_bucket_evidence_b1 — delete bucket after policy/PAB/object/version cleanup.
aws s3api delete-bucket \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_bucket_ingest_c — enumerate current object keys so non-versioned objects are removed before bucket delete.
ARCH1_BUCKET_INGEST_C_OBJECT_KEYS="$(aws s3api list-objects-v2 \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'Contents[].Key' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_INGEST_C_OBJECT_KEYS" && "$ARCH1_BUCKET_INGEST_C_OBJECT_KEYS" != "None" ]]; then
  for object_key in $ARCH1_BUCKET_INGEST_C_OBJECT_KEYS; do
    # DELETE arch1_bucket_ingest_c — remove each current object so bucket deletion can proceed.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
      --key "$object_key" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done
fi

# DELETE arch1_bucket_ingest_c — enumerate object versions so versioned data cannot block bucket deletion.
ARCH1_BUCKET_INGEST_C_VERSIONS="$(aws s3api list-object-versions \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'Versions[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_INGEST_C_VERSIONS" && "$ARCH1_BUCKET_INGEST_C_VERSIONS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch1_bucket_ingest_c — remove each object version before final bucket delete.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH1_BUCKET_INGEST_C_VERSIONS"
fi

# DELETE arch1_bucket_ingest_c — enumerate delete markers so bucket version metadata is fully cleared.
ARCH1_BUCKET_INGEST_C_DELETE_MARKERS="$(aws s3api list-object-versions \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'DeleteMarkers[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_INGEST_C_DELETE_MARKERS" && "$ARCH1_BUCKET_INGEST_C_DELETE_MARKERS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch1_bucket_ingest_c — remove each delete marker so bucket deletion is not blocked.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH1_BUCKET_INGEST_C_DELETE_MARKERS"
fi

# DELETE arch1_bucket_ingest_c — delete bucket after policy/object/version cleanup.
aws s3api delete-bucket \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_bucket_logging_target_c — enumerate current object keys so non-versioned objects are removed before bucket delete.
ARCH1_BUCKET_LOGGING_TARGET_C_OBJECT_KEYS="$(aws s3api list-objects-v2 \
  --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'Contents[].Key' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_LOGGING_TARGET_C_OBJECT_KEYS" && "$ARCH1_BUCKET_LOGGING_TARGET_C_OBJECT_KEYS" != "None" ]]; then
  for object_key in $ARCH1_BUCKET_LOGGING_TARGET_C_OBJECT_KEYS; do
    # DELETE arch1_bucket_logging_target_c — remove each current object so bucket deletion can proceed.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
      --key "$object_key" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done
fi

# DELETE arch1_bucket_logging_target_c — enumerate object versions so versioned data cannot block bucket deletion.
ARCH1_BUCKET_LOGGING_TARGET_C_VERSIONS="$(aws s3api list-object-versions \
  --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'Versions[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_LOGGING_TARGET_C_VERSIONS" && "$ARCH1_BUCKET_LOGGING_TARGET_C_VERSIONS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch1_bucket_logging_target_c — remove each object version before final bucket delete.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH1_BUCKET_LOGGING_TARGET_C_VERSIONS"
fi

# DELETE arch1_bucket_logging_target_c — enumerate delete markers so bucket version metadata is fully cleared.
ARCH1_BUCKET_LOGGING_TARGET_C_DELETE_MARKERS="$(aws s3api list-object-versions \
  --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query 'DeleteMarkers[].[Key,VersionId]' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_BUCKET_LOGGING_TARGET_C_DELETE_MARKERS" && "$ARCH1_BUCKET_LOGGING_TARGET_C_DELETE_MARKERS" != "None" ]]; then
  while IFS=$'\t' read -r object_key version_id; do
    if [[ -z "${object_key:-}" || "$object_key" == "None" || -z "${version_id:-}" || "$version_id" == "None" ]]; then
      continue
    fi

    # DELETE arch1_bucket_logging_target_c — remove each delete marker so bucket deletion is not blocked.
    aws s3api delete-object \
      --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
      --key "$object_key" \
      --version-id "$version_id" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  done <<< "$ARCH1_BUCKET_LOGGING_TARGET_C_DELETE_MARKERS"
fi

# DELETE arch1_bucket_logging_target_c — delete bucket after object/version cleanup.
aws s3api delete-bucket \
  --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_account_pab_c — remove account-level PAB setting after all bucket-level resources are already torn down.
aws s3control delete-public-access-block \
  --account-id "$ACCOUNT_ID" \
  --region "$AWS_REGION" \
  --no-cli-pager 2>/dev/null || true

# DELETE arch1_vpc_main — resolve VPC ID only after subnets and security groups are deleted.
ARCH1_VPC_ID="$(aws ec2 describe-vpcs \
  --filters "Name=tag:Name,Values=${ARCH1_VPC_MAIN_NAME}" "Name=tag:Architecture,Values=architecture-1" \
  --region "$AWS_REGION" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_VPC_ID" && "$ARCH1_VPC_ID" != "None" ]]; then
  # DELETE arch1_vpc_main — delete VPC last because it is the root dependency for all Architecture 1 network resources.
  aws ec2 delete-vpc \
    --vpc-id "$ARCH1_VPC_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

