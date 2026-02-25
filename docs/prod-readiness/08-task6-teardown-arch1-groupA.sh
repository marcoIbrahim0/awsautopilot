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

TARGET_TEST_GROUP_VALUE="detection"

# ARCHITECTURE 1 DELETE ORDER (Group A subset only)

# DELETE arch1_app_server_a2 — look up the Group A instance first so SG and subnet dependencies can be removed safely later.
ARCH1_APP_SERVER_A2_ID="$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${ARCH1_APP_SERVER_A2_NAME}" "Name=tag:Architecture,Values=architecture-1" "Name=tag:TestGroup,Values=${TARGET_TEST_GROUP_VALUE}" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --region "$AWS_REGION" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_APP_SERVER_A2_ID" && "$ARCH1_APP_SERVER_A2_ID" != "None" ]]; then
  # DELETE arch1_app_server_a2 — terminate compute before deleting SG and subnet dependencies.
  aws ec2 terminate-instances \
    --instance-ids "$ARCH1_APP_SERVER_A2_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager >/dev/null 2>&1 || true

  # DELETE arch1_app_server_a2 — wait for instance termination so dependency teardown remains valid.
  aws ec2 wait instance-terminated \
    --instance-ids "$ARCH1_APP_SERVER_A2_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch1_claims_db_a2 — resolve DB ARN to validate Group A tag before destructive delete.
ARCH1_CLAIMS_DB_A2_ARN="$(aws rds describe-db-instances \
  --db-instance-identifier "$ARCH1_CLAIMS_DB_A2_IDENTIFIER" \
  --region "$AWS_REGION" \
  --query 'DBInstances[0].DBInstanceArn' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_CLAIMS_DB_A2_ARN" && "$ARCH1_CLAIMS_DB_A2_ARN" != "None" ]]; then
  # DELETE arch1_claims_db_a2 — read TestGroup tag so Group A teardown never touches non-target resources.
  ARCH1_CLAIMS_DB_A2_TEST_GROUP="$(aws rds list-tags-for-resource \
    --resource-name "$ARCH1_CLAIMS_DB_A2_ARN" \
    --region "$AWS_REGION" \
    --query "TagList[?Key=='TestGroup'] | [0].Value" \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ "$ARCH1_CLAIMS_DB_A2_TEST_GROUP" == "$TARGET_TEST_GROUP_VALUE" ]]; then
    # DELETE arch1_claims_db_a2 — remove DB instance before SG/subnet teardown to honor dependency ordering.
    aws rds delete-db-instance \
      --db-instance-identifier "$ARCH1_CLAIMS_DB_A2_IDENTIFIER" \
      --skip-final-snapshot \
      --delete-automated-backups \
      --region "$AWS_REGION" \
      --no-cli-pager >/dev/null 2>&1 || true

    # DELETE arch1_claims_db_a2 — wait until DB is gone so downstream SG/subnet deletion cannot race.
    aws rds wait db-instance-deleted \
      --db-instance-identifier "$ARCH1_CLAIMS_DB_A2_IDENTIFIER" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true

    # DELETE arch1_claims_db_a2 — delete its DB subnet group now that the DB dependency is removed.
    aws rds delete-db-subnet-group \
      --db-subnet-group-name "$ARCH1_DB_SUBNET_GROUP_NAME" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  fi
fi

# DELETE arch1_sg_reference_a2 — resolve SG-B ID under Group A tag so only target dependency-chain SG is deleted.
ARCH1_SG_REFERENCE_A2_ID="$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${ARCH1_SG_REFERENCE_A2_NAME}" "Name=tag:Architecture,Values=architecture-1" "Name=tag:TestGroup,Values=${TARGET_TEST_GROUP_VALUE}" \
  --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_SG_REFERENCE_A2_ID" && "$ARCH1_SG_REFERENCE_A2_ID" != "None" ]]; then
  # DELETE arch1_sg_reference_a2 — remove SG-B before SG-A per reverse dependency order.
  aws ec2 delete-security-group \
    --group-id "$ARCH1_SG_REFERENCE_A2_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch1_bucket_policy_website_a1 — read bucket tags first so policy deletion applies only to Group A website bucket.
ARCH1_BUCKET_WEBSITE_A1_TEST_GROUP="$(aws s3api get-bucket-tagging \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query "TagSet[?Key=='TestGroup'] | [0].Value" \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ "$ARCH1_BUCKET_WEBSITE_A1_TEST_GROUP" == "$TARGET_TEST_GROUP_VALUE" ]]; then
  # DELETE arch1_bucket_policy_website_a1 — remove bucket policy before bucket deletion to satisfy dependency order.
  aws s3api delete-bucket-policy \
    --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch1_sg_dependency_a2 — resolve SG-A ID under Group A tag after SG-B and attached resources are removed.
ARCH1_SG_DEPENDENCY_A2_ID="$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${ARCH1_SG_DEPENDENCY_A2_NAME}" "Name=tag:Architecture,Values=architecture-1" "Name=tag:TestGroup,Values=${TARGET_TEST_GROUP_VALUE}" \
  --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_SG_DEPENDENCY_A2_ID" && "$ARCH1_SG_DEPENDENCY_A2_ID" != "None" ]]; then
  # DELETE arch1_sg_dependency_a2 — delete SG-A only after all SG-A dependents are already deleted.
  aws ec2 delete-security-group \
    --group-id "$ARCH1_SG_DEPENDENCY_A2_ID" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

if [[ "$ARCH1_BUCKET_WEBSITE_A1_TEST_GROUP" == "$TARGET_TEST_GROUP_VALUE" ]]; then
  # DELETE arch1_bucket_website_a1 — enumerate current object keys so non-versioned objects are removed before bucket delete.
  ARCH1_BUCKET_WEBSITE_A1_OBJECT_KEYS="$(aws s3api list-objects-v2 \
    --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --query 'Contents[].Key' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -n "$ARCH1_BUCKET_WEBSITE_A1_OBJECT_KEYS" && "$ARCH1_BUCKET_WEBSITE_A1_OBJECT_KEYS" != "None" ]]; then
    for object_key in $ARCH1_BUCKET_WEBSITE_A1_OBJECT_KEYS; do
      # DELETE arch1_bucket_website_a1 — remove each current object so bucket deletion is unblocked.
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

      # DELETE arch1_bucket_website_a1 — remove each object version before final bucket deletion.
      aws s3api delete-object \
        --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
        --key "$object_key" \
        --version-id "$version_id" \
        --region "$AWS_REGION" \
        --no-cli-pager 2>/dev/null || true
    done <<< "$ARCH1_BUCKET_WEBSITE_A1_VERSIONS"
  fi

  # DELETE arch1_bucket_website_a1 — enumerate delete markers so all versioned tombstones are removed pre-delete.
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

      # DELETE arch1_bucket_website_a1 — remove each delete marker so bucket version graph is fully cleared.
      aws s3api delete-object \
        --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
        --key "$object_key" \
        --version-id "$version_id" \
        --region "$AWS_REGION" \
        --no-cli-pager 2>/dev/null || true
    done <<< "$ARCH1_BUCKET_WEBSITE_A1_DELETE_MARKERS"
  fi

  # DELETE arch1_bucket_website_a1 — delete the bucket only after policy and all objects/versions are removed.
  aws s3api delete-bucket \
    --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

