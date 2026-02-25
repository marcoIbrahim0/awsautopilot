# Teardown Scripts — AWS Security Test Environment

> ⚠️ Run teardown only after confirming you are in the correct test account. These scripts permanently delete AWS resources. There is no undo.

## Architecture 1 Teardown

### Group A only

```bash
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

```

### Group B only

```bash
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

TARGET_TEST_GROUP_VALUE="negative"

# ARCHITECTURE 1 DELETE ORDER (Group B subset only)

# DELETE arch1_bucket_policy_evidence_b1 — read bucket tags first so policy teardown is scoped to Group B resources only.
ARCH1_BUCKET_EVIDENCE_B1_TEST_GROUP="$(aws s3api get-bucket-tagging \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --region "$AWS_REGION" \
  --query "TagSet[?Key=='TestGroup'] | [0].Value" \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ "$ARCH1_BUCKET_EVIDENCE_B1_TEST_GROUP" == "$TARGET_TEST_GROUP_VALUE" ]]; then
  # DELETE arch1_bucket_policy_evidence_b1 — remove bucket policy before bucket deletion per reverse dependency order.
  aws s3api delete-bucket-policy \
    --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

if [[ "$ARCH1_BUCKET_EVIDENCE_B1_TEST_GROUP" == "$TARGET_TEST_GROUP_VALUE" ]]; then
  # DELETE arch1_bucket_pab_evidence_b1 — remove bucket-level PAB object before deleting the parent bucket.
  aws s3api delete-public-access-block \
    --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

# DELETE arch1_sg_app_b2 — resolve Group B SG ID so only negative-test security group is targeted.
ARCH1_SG_APP_B2_ID="$(aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=${ARCH1_SG_APP_B2_NAME}" "Name=tag:Architecture,Values=architecture-1" "Name=tag:TestGroup,Values=${TARGET_TEST_GROUP_VALUE}" \
  --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
if [[ -n "$ARCH1_SG_APP_B2_ID" && "$ARCH1_SG_APP_B2_ID" != "None" ]]; then
  # DELETE arch1_sg_app_b2 — check attached ENIs so SG is never deleted before dependents.
  ARCH1_SG_APP_B2_DEPENDENT_ENI_ID="$(aws ec2 describe-network-interfaces \
    --filters "Name=group-id,Values=${ARCH1_SG_APP_B2_ID}" \
    --region "$AWS_REGION" \
    --query 'NetworkInterfaces[0].NetworkInterfaceId' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -z "$ARCH1_SG_APP_B2_DEPENDENT_ENI_ID" || "$ARCH1_SG_APP_B2_DEPENDENT_ENI_ID" == "None" ]]; then
    # DELETE arch1_sg_app_b2 — delete SG only after all dependent ENIs are gone.
    aws ec2 delete-security-group \
      --group-id "$ARCH1_SG_APP_B2_ID" \
      --region "$AWS_REGION" \
      --no-cli-pager 2>/dev/null || true
  fi
fi

if [[ "$ARCH1_BUCKET_EVIDENCE_B1_TEST_GROUP" == "$TARGET_TEST_GROUP_VALUE" ]]; then
  # DELETE arch1_bucket_evidence_b1 — enumerate current object keys so non-versioned objects are removed before bucket delete.
  ARCH1_BUCKET_EVIDENCE_B1_OBJECT_KEYS="$(aws s3api list-objects-v2 \
    --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --query 'Contents[].Key' \
    --output text \
    --no-cli-pager 2>/dev/null || true)"

  if [[ -n "$ARCH1_BUCKET_EVIDENCE_B1_OBJECT_KEYS" && "$ARCH1_BUCKET_EVIDENCE_B1_OBJECT_KEYS" != "None" ]]; then
    for object_key in $ARCH1_BUCKET_EVIDENCE_B1_OBJECT_KEYS; do
      # DELETE arch1_bucket_evidence_b1 — remove each current object so parent bucket deletion can succeed.
      aws s3api delete-object \
        --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
        --key "$object_key" \
        --region "$AWS_REGION" \
        --no-cli-pager 2>/dev/null || true
    done
  fi

  # DELETE arch1_bucket_evidence_b1 — enumerate object versions so versioned data cannot block deletion.
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

  # DELETE arch1_bucket_evidence_b1 — delete bucket after policy/PAB/object cleanup in reverse dependency order.
  aws s3api delete-bucket \
    --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || true
fi

```

### Full teardown (all groups)

```bash
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

```

## Architecture 2 Teardown

### Group A only

```bash
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
```

### Group B only

```bash
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

ARCH2_MIXED_POLICY_ROLE_B3_ARN=""

# ARCHITECTURE 2 DELETE ORDER (Group B subset only)

# DELETE arch2_mixed_policy_role_b3 — resolve role ARN so role-specific policy detach and delete can proceed.
ARCH2_MIXED_POLICY_ROLE_B3_ARN="$(aws iam get-role \
  --role-name "$ARCH2_MIXED_POLICY_ROLE_B3_NAME" \
  --query 'Role.Arn' \
  --output text \
  --no-cli-pager 2>/dev/null || true)"
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
```

### Full teardown (all groups)

```bash
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
```
