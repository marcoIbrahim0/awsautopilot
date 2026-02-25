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

# arch1_preflight_identity — confirms current caller/account context — clean safety check before deployment
aws sts get-caller-identity --no-cli-pager

echo ""
echo "⚠️  DEPLOY TO A DEDICATED TEST ACCOUNT ONLY"
echo "These resources contain deliberate security misconfigurations."
echo "Do not deploy to a production, staging, or shared development account."
echo "Confirm you are in the correct account by reviewing the output above."
echo ""
read -r -p "Type CONFIRM to proceed or anything else to exit: " CONFIRM_INPUT
if [ "$CONFIRM_INPUT" != "CONFIRM" ]; then
  echo "Aborted."
  exit 1
fi

# ---------------------------------------------------------------------------
# ARCHITECTURE 1 CREATE ORDER
# ---------------------------------------------------------------------------

# arch1_vpc_main — creates the Architecture 1 VPC boundary — clean foundational network for all dependent resources
ARCH1_VPC_ID=$(aws ec2 create-vpc \
  --cidr-block "$ARCH1_VPC_CIDR" \
  --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=${ARCH1_VPC_MAIN_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=workflow-processing},{Key=ResourceGroup,Value=C},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}}]" \
  --region "$AWS_REGION" \
  --query 'Vpc.VpcId' \
  --output text \
  --no-cli-pager)

# arch1_vpc_main — enables DNS support in the VPC — clean baseline required for ECS/Fargate name resolution
aws ec2 modify-vpc-attribute \
  --vpc-id "$ARCH1_VPC_ID" \
  --enable-dns-support "{\"Value\":true}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_vpc_main — enables DNS hostnames in the VPC — clean baseline so instances/tasks can receive DNS hostnames
aws ec2 modify-vpc-attribute \
  --vpc-id "$ARCH1_VPC_ID" \
  --enable-dns-hostnames "{\"Value\":true}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_public_subnet_a — creates the external-intake subnet — clean public subnet used by app and ECS service
ARCH1_PUBLIC_SUBNET_A_ID=$(aws ec2 create-subnet \
  --vpc-id "$ARCH1_VPC_ID" \
  --cidr-block "$ARCH1_PUBLIC_SUBNET_A_CIDR" \
  --availability-zone "${AWS_REGION}a" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${ARCH1_PUBLIC_SUBNET_A_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=external-intake},{Key=ResourceGroup,Value=C},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}}]" \
  --region "$AWS_REGION" \
  --query 'Subnet.SubnetId' \
  --output text \
  --no-cli-pager)

# arch1_public_subnet_a — enables public IP assignment on launch — clean baseline for internet-facing workload placement
aws ec2 modify-subnet-attribute \
  --subnet-id "$ARCH1_PUBLIC_SUBNET_A_ID" \
  --map-public-ip-on-launch \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_private_subnet_a — creates the data-retention subnet — clean private-tier subnet for RDS placement
ARCH1_PRIVATE_SUBNET_A_ID=$(aws ec2 create-subnet \
  --vpc-id "$ARCH1_VPC_ID" \
  --cidr-block "$ARCH1_PRIVATE_SUBNET_A_CIDR" \
  --availability-zone "${AWS_REGION}b" \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${ARCH1_PRIVATE_SUBNET_A_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=data-retention},{Key=ResourceGroup,Value=C},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}}]" \
  --region "$AWS_REGION" \
  --query 'Subnet.SubnetId' \
  --output text \
  --no-cli-pager)

# arch1_sg_app_b2 — creates B2 mixed-rule security group — adversarial SG must preserve legitimate rules while containing one permissive SSH rule
ARCH1_SG_APP_B2_ID=$(aws ec2 create-security-group \
  --group-name "$ARCH1_SG_APP_B2_NAME" \
  --description "B2 mixed legitimate rules plus permissive SSH rule" \
  --vpc-id "$ARCH1_VPC_ID" \
  --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=${ARCH1_SG_APP_B2_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=external-intake},{Key=ResourceGroup,Value=B},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}},{Key=ContextTest,Value=${TAG_GROUP_B2_VALUE}}]" \
  --region "$AWS_REGION" \
  --query 'GroupId' \
  --output text \
  --no-cli-pager)

# arch1_sg_app_b2 — adds legitimate inbound HTTPS from internal CIDR — clean preserved rule required by B2 context
aws ec2 authorize-security-group-ingress \
  --group-id "$ARCH1_SG_APP_B2_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=${HTTPS_PORT},ToPort=${HTTPS_PORT},IpRanges=[{CidrIp=${INTERNAL_VPC_CIDR},Description='legitimate-https-internal'}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_sg_app_b2 — adds legitimate inbound app port from admin host CIDR — clean preserved rule required by B2 context
aws ec2 authorize-security-group-ingress \
  --group-id "$ARCH1_SG_APP_B2_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=${APP_PORT},ToPort=${APP_PORT},IpRanges=[{CidrIp=${ADMIN_HOST_CIDR},Description='legitimate-app-admin-host'}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_sg_app_b2 — adds permissive SSH ingress from anywhere — intentional B2 misconfiguration to preserve for testing
aws ec2 authorize-security-group-ingress \
  --group-id "$ARCH1_SG_APP_B2_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=${SSH_PORT},ToPort=${SSH_PORT},IpRanges=[{CidrIp=${PUBLIC_CIDR_ANY},Description='intentional-misconfig-public-ssh'}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_sg_dependency_a2 — creates A2 dependency-chain security group (SG-A) — adversarial SG used across EC2, RDS, and SG reference chain
ARCH1_SG_DEPENDENCY_A2_ID=$(aws ec2 create-security-group \
  --group-name "$ARCH1_SG_DEPENDENCY_A2_NAME" \
  --description "A2 SG-A dependency chain group" \
  --vpc-id "$ARCH1_VPC_ID" \
  --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=${ARCH1_SG_DEPENDENCY_A2_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=workflow-processing},{Key=ResourceGroup,Value=A},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}},{Key=BlastRadiusTest,Value=${TAG_GROUP_A2_VALUE}}]" \
  --region "$AWS_REGION" \
  --query 'GroupId' \
  --output text \
  --no-cli-pager)

# arch1_sg_dependency_a2 — adds intentional public SSH ingress on SG-A — required A2 misconfiguration that drives blast-radius behavior
aws ec2 authorize-security-group-ingress \
  --group-id "$ARCH1_SG_DEPENDENCY_A2_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=${SSH_PORT},ToPort=${SSH_PORT},IpRanges=[{CidrIp=${PUBLIC_CIDR_ANY},Description='intentional-a2-public-ssh'}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_sg_reference_a2 — creates A2 reference-chain security group (SG-B) — adversarial dependency endpoint that references SG-A
ARCH1_SG_REFERENCE_A2_ID=$(aws ec2 create-security-group \
  --group-name "$ARCH1_SG_REFERENCE_A2_NAME" \
  --description "A2 SG-B referencing SG-A inbound source" \
  --vpc-id "$ARCH1_VPC_ID" \
  --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=${ARCH1_SG_REFERENCE_A2_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=workflow-processing},{Key=ResourceGroup,Value=A},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}},{Key=BlastRadiusTest,Value=${TAG_GROUP_A2_VALUE}}]" \
  --region "$AWS_REGION" \
  --query 'GroupId' \
  --output text \
  --no-cli-pager)

# arch1_sg_reference_a2 — adds SG-B inbound rule sourced from SG-A — required A2 transitive SG dependency-chain reference
aws ec2 authorize-security-group-ingress \
  --group-id "$ARCH1_SG_REFERENCE_A2_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=${POSTGRES_PORT},ToPort=${POSTGRES_PORT},UserIdGroupPairs=[{GroupId=${ARCH1_SG_DEPENDENCY_A2_ID},Description='a2-transitive-sg-reference'}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_sg_app_b2 — adds legitimate inbound PostgreSQL from source security group — clean preserved B2 rule to keep mixed-context realism
aws ec2 authorize-security-group-ingress \
  --group-id "$ARCH1_SG_APP_B2_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=${POSTGRES_PORT},ToPort=${POSTGRES_PORT},UserIdGroupPairs=[{GroupId=${ARCH1_SG_REFERENCE_A2_ID},Description='legitimate-postgres-from-source-sg'}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_website_a1 — creates A1 website bucket — adversarial website-hosting bucket that will remain public by design
if [ "$AWS_REGION" = "us-east-1" ]; then
  # arch1_bucket_website_a1 — creates the physical S3 bucket in us-east-1 — intentional A1 website endpoint dependency
  aws s3api create-bucket \
    --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager
else
  # arch1_bucket_website_a1 — creates the physical S3 bucket outside us-east-1 — intentional A1 website endpoint dependency
  aws s3api create-bucket \
    --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
    --create-bucket-configuration "LocationConstraint=${AWS_REGION}" \
    --region "$AWS_REGION" \
    --no-cli-pager
fi

# arch1_bucket_website_a1 — applies required tags including A1 adversarial marker — intentional tag context for blast-radius tests
aws s3api put-bucket-tagging \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --tagging "TagSet=[{Key=Name,Value=${ARCH1_BUCKET_WEBSITE_A1_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=external-intake},{Key=ResourceGroup,Value=A},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}},{Key=BlastRadiusTest,Value=${TAG_GROUP_A1_VALUE}}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_website_a1 — disables bucket-level public access block — intentional A1 misconfiguration that keeps website objects publicly reachable
aws s3api put-public-access-block \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_website_a1 — enables static website hosting — intentional A1 misconfiguration prerequisite for direct public website access
aws s3api put-bucket-website \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --website-configuration "IndexDocument={Suffix=index.html},ErrorDocument={Key=error.html}" \
  --region "$AWS_REGION" \
  --no-cli-pager

ARCH1_WEBSITE_INDEX_FILE="$(mktemp)"
printf '%s\n' '<!doctype html><html><body><h1>arch1 website</h1></body></html>' > "$ARCH1_WEBSITE_INDEX_FILE"

# arch1_bucket_website_a1 — uploads index.html website object — intentional A1 requirement that at least one object exists for public website serving
aws s3api put-object \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --key "index.html" \
  --body "$ARCH1_WEBSITE_INDEX_FILE" \
  --region "$AWS_REGION" \
  --no-cli-pager

ARCH1_BUCKET_POLICY_WEBSITE_A1_FILE="$(mktemp)"
cat > "$ARCH1_BUCKET_POLICY_WEBSITE_A1_FILE" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadWebsiteObjects",
      "Effect": "Allow",
      "Principal": "*",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::${ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME}/*"]
    }
  ]
}
EOF

# arch1_bucket_policy_website_a1 — applies public read bucket policy — intentional A1 misconfiguration that exposes website objects anonymously
aws s3api put-bucket-policy \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --policy "file://${ARCH1_BUCKET_POLICY_WEBSITE_A1_FILE}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_evidence_b1 — creates B1 evidence bucket — adversarial context resource where legitimate policy must be preserved
if [ "$AWS_REGION" = "us-east-1" ]; then
  # arch1_bucket_evidence_b1 — creates physical evidence bucket in us-east-1 — B1 baseline bucket for policy-preservation testing
  aws s3api create-bucket \
    --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager
else
  # arch1_bucket_evidence_b1 — creates physical evidence bucket outside us-east-1 — B1 baseline bucket for policy-preservation testing
  aws s3api create-bucket \
    --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
    --create-bucket-configuration "LocationConstraint=${AWS_REGION}" \
    --region "$AWS_REGION" \
    --no-cli-pager
fi

# arch1_bucket_evidence_b1 — applies required tags including B1 adversarial marker — intentional context tag for complex-policy preservation tests
aws s3api put-bucket-tagging \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --tagging "TagSet=[{Key=Name,Value=${ARCH1_BUCKET_EVIDENCE_B1_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=data-retention},{Key=ResourceGroup,Value=B},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}},{Key=ContextTest,Value=${TAG_GROUP_B1_VALUE}}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

ARCH1_BUCKET_POLICY_EVIDENCE_B1_FILE="$(mktemp)"
cat > "$ARCH1_BUCKET_POLICY_EVIDENCE_B1_FILE" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowCrossAccountRead",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::${B1_CROSS_ACCOUNT_ID}:root"
      },
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::${ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME}/*"]
    },
    {
      "Sid": "AllowDataPipelinePutObject",
      "Effect": "Allow",
      "Principal": {
        "AWS": "${B1_DATA_PIPELINE_ROLE_ARN_VALUE}"
      },
      "Action": ["s3:PutObject"],
      "Resource": ["arn:aws:s3:::${ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME}/*"]
    },
    {
      "Sid": "AllowVpcScopedReadPath",
      "Effect": "Allow",
      "Principal": "*",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::${ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME}/*"],
      "Condition": {
        "StringEquals": {
          "aws:SourceVpc": "${ARCH1_VPC_ID}"
        }
      }
    }
  ]
}
EOF

# arch1_bucket_policy_evidence_b1 — applies full legitimate multi-statement policy — clean preserved policy context required by B1 before misconfig fix testing
aws s3api put-bucket-policy \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --policy "file://${ARCH1_BUCKET_POLICY_EVIDENCE_B1_FILE}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_pab_evidence_b1 — disables bucket public access block flags — intentional B1 misconfiguration while preserving legitimate policy statements
aws s3api put-public-access-block \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_logging_target_c — creates clean logging-target bucket — baseline destination bucket for ingest access logs
if [ "$AWS_REGION" = "us-east-1" ]; then
  # arch1_bucket_logging_target_c — creates physical logging bucket in us-east-1 — clean log retention destination
  aws s3api create-bucket \
    --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager
else
  # arch1_bucket_logging_target_c — creates physical logging bucket outside us-east-1 — clean log retention destination
  aws s3api create-bucket \
    --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
    --create-bucket-configuration "LocationConstraint=${AWS_REGION}" \
    --region "$AWS_REGION" \
    --no-cli-pager
fi

# arch1_bucket_logging_target_c — applies required clean baseline tags — clean governance metadata for operations retention tier
aws s3api put-bucket-tagging \
  --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
  --tagging "TagSet=[{Key=Name,Value=${ARCH1_BUCKET_LOGGING_TARGET_C_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=data-retention},{Key=ResourceGroup,Value=C},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_logging_target_c — enables strict public access block — clean configuration to keep log bucket private
aws s3api put-public-access-block \
  --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_ingest_c — creates clean ingest bucket — baseline production-like bucket with hardening controls
if [ "$AWS_REGION" = "us-east-1" ]; then
  # arch1_bucket_ingest_c — creates physical ingest bucket in us-east-1 — clean primary data-ingest bucket
  aws s3api create-bucket \
    --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
    --region "$AWS_REGION" \
    --no-cli-pager
else
  # arch1_bucket_ingest_c — creates physical ingest bucket outside us-east-1 — clean primary data-ingest bucket
  aws s3api create-bucket \
    --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
    --create-bucket-configuration "LocationConstraint=${AWS_REGION}" \
    --region "$AWS_REGION" \
    --no-cli-pager
fi

# arch1_bucket_ingest_c — applies required clean baseline tags — clean governance metadata for Architecture 1 data tier
aws s3api put-bucket-tagging \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --tagging "TagSet=[{Key=Name,Value=${ARCH1_BUCKET_INGEST_C_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=data-retention},{Key=ResourceGroup,Value=C},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_ingest_c — enables strict public access block — clean baseline enforcing private bucket posture
aws s3api put-public-access-block \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_ingest_c — enables versioning — clean retention control for data durability and change history
aws s3api put-bucket-versioning \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --versioning-configuration "Status=Enabled" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_ingest_c — enforces server-side encryption by default — clean storage-hardening control
aws s3api put-bucket-encryption \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' \
  --region "$AWS_REGION" \
  --no-cli-pager

ARCH1_BUCKET_LOGGING_TARGET_POLICY_FILE="$(mktemp)"
cat > "$ARCH1_BUCKET_LOGGING_TARGET_POLICY_FILE" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowS3ServerAccessLogsWrite",
      "Effect": "Allow",
      "Principal": {
        "Service": "logging.s3.amazonaws.com"
      },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::${ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME}/*",
      "Condition": {
        "ArnLike": {
          "aws:SourceArn": "arn:aws:s3:::${ARCH1_BUCKET_INGEST_C_BUCKET_NAME}"
        },
        "StringEquals": {
          "aws:SourceAccount": "${ACCOUNT_ID}"
        }
      }
    }
  ]
}
EOF

# arch1_bucket_logging_target_c — grants S3 logging service write access from ingest bucket — clean dependency for access-log delivery
aws s3api put-bucket-policy \
  --bucket "$ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME" \
  --policy "file://${ARCH1_BUCKET_LOGGING_TARGET_POLICY_FILE}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_bucket_ingest_c — enables server access logging to the logging target bucket — clean observability/retention control
aws s3api put-bucket-logging \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --bucket-logging-status "LoggingEnabled={TargetBucket=${ARCH1_BUCKET_LOGGING_TARGET_C_BUCKET_NAME},TargetPrefix=access-logs/}" \
  --region "$AWS_REGION" \
  --no-cli-pager

ARCH1_BUCKET_POLICY_INGEST_C_FILE="$(mktemp)"
cat > "$ARCH1_BUCKET_POLICY_INGEST_C_FILE" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyInsecureTransport",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::${ARCH1_BUCKET_INGEST_C_BUCKET_NAME}",
        "arn:aws:s3:::${ARCH1_BUCKET_INGEST_C_BUCKET_NAME}/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    }
  ]
}
EOF

# arch1_bucket_policy_ingest_c — applies TLS-enforcement bucket policy — clean baseline policy control for secure transport
aws s3api put-bucket-policy \
  --bucket "$ARCH1_BUCKET_INGEST_C_BUCKET_NAME" \
  --policy "file://${ARCH1_BUCKET_POLICY_INGEST_C_FILE}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_app_server_a2 — resolves latest Amazon Linux AMI ID — clean helper to launch minimal EC2 test instance
ARCH1_APP_AMI_ID=$(aws ssm get-parameter \
  --name "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64" \
  --region "$AWS_REGION" \
  --query 'Parameter.Value' \
  --output text \
  --no-cli-pager)

# arch1_app_server_a2 — launches t3.micro EC2 attached to SG-A — required A2 dependency-chain attachment for blast-radius testing
ARCH1_APP_SERVER_A2_ID=$(aws ec2 run-instances \
  --image-id "$ARCH1_APP_AMI_ID" \
  --instance-type "t3.micro" \
  --subnet-id "$ARCH1_PUBLIC_SUBNET_A_ID" \
  --security-group-ids "$ARCH1_SG_DEPENDENCY_A2_ID" \
  --associate-public-ip-address \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":8,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${ARCH1_APP_SERVER_A2_NAME}},{Key=Project,Value=${TAG_PROJECT_VALUE}},{Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}},{Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}},{Key=Architecture,Value=${TAG_ARCH1_VALUE}},{Key=Tier,Value=workflow-processing},{Key=ResourceGroup,Value=A},{Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}},{Key=BlastRadiusTest,Value=${TAG_GROUP_A2_VALUE}}]" \
  --region "$AWS_REGION" \
  --query 'Instances[0].InstanceId' \
  --output text \
  --no-cli-pager)

# arch1_claims_db_a2 — creates DB subnet group from Architecture 1 subnets — clean prerequisite so RDS can deploy in VPC
aws rds create-db-subnet-group \
  --db-subnet-group-name "$ARCH1_DB_SUBNET_GROUP_NAME" \
  --db-subnet-group-description "DB subnet group for ${ARCH1_CLAIMS_DB_A2_NAME}" \
  --subnet-ids "$ARCH1_PUBLIC_SUBNET_A_ID" "$ARCH1_PRIVATE_SUBNET_A_ID" \
  --tags "Key=Name,Value=${ARCH1_DB_SUBNET_GROUP_NAME}" "Key=Project,Value=${TAG_PROJECT_VALUE}" "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" "Key=Architecture,Value=${TAG_ARCH1_VALUE}" "Key=Tier,Value=data-retention" "Key=ResourceGroup,Value=A" "Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}" "Key=BlastRadiusTest,Value=${TAG_GROUP_A2_VALUE}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_claims_db_a2 — creates db.t3.micro RDS attached to SG-A — required A2 dependency-chain attachment while keeping minimal-size database
ARCH1_CLAIMS_DB_A2_ID=$(aws rds create-db-instance \
  --db-instance-identifier "$ARCH1_CLAIMS_DB_A2_IDENTIFIER" \
  --db-instance-class "db.t3.micro" \
  --engine "postgres" \
  --allocated-storage "20" \
  --storage-type "gp3" \
  --master-username "$ARCH1_RDS_MASTER_USERNAME" \
  --master-user-password "$ARCH1_RDS_MASTER_PASSWORD" \
  --db-name "claimsdb" \
  --db-subnet-group-name "$ARCH1_DB_SUBNET_GROUP_NAME" \
  --vpc-security-group-ids "$ARCH1_SG_DEPENDENCY_A2_ID" \
  --no-publicly-accessible \
  --backup-retention-period "0" \
  --tags "Key=Name,Value=${ARCH1_CLAIMS_DB_A2_NAME}" "Key=Project,Value=${TAG_PROJECT_VALUE}" "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" "Key=Architecture,Value=${TAG_ARCH1_VALUE}" "Key=Tier,Value=data-retention" "Key=ResourceGroup,Value=A" "Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}" "Key=BlastRadiusTest,Value=${TAG_GROUP_A2_VALUE}" \
  --region "$AWS_REGION" \
  --query 'DBInstance.DBInstanceIdentifier' \
  --output text \
  --no-cli-pager)

# arch1_account_pab_c — enables account-level S3 public access block — clean account-wide baseline control for S3.1
aws s3control put-public-access-block \
  --account-id "$ACCOUNT_ID" \
  --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
  --region "$AWS_REGION" \
  --no-cli-pager

ARCH1_ECS_EXECUTION_ROLE_TRUST_POLICY_FILE="$(mktemp)"
cat > "$ARCH1_ECS_EXECUTION_ROLE_TRUST_POLICY_FILE" <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# arch1_web_ingest_service — creates execution IAM role for ECS task startup — clean prerequisite to run the service in ECS
ARCH1_ECS_EXECUTION_ROLE_ARN=$(aws iam create-role \
  --role-name "$ARCH1_ECS_EXECUTION_ROLE_NAME" \
  --assume-role-policy-document "file://${ARCH1_ECS_EXECUTION_ROLE_TRUST_POLICY_FILE}" \
  --tags "Key=Name,Value=${ARCH1_ECS_EXECUTION_ROLE_NAME}" "Key=Project,Value=${TAG_PROJECT_VALUE}" "Key=Environment,Value=${TAG_ENVIRONMENT_VALUE}" "Key=ManagedBy,Value=${TAG_MANAGED_BY_VALUE}" "Key=Architecture,Value=${TAG_ARCH1_VALUE}" "Key=Tier,Value=external-intake" "Key=ResourceGroup,Value=C" "Key=TestGroup,Value=${TAG_TEST_GROUP_VALUE}" \
  --query 'Role.Arn' \
  --output text \
  --no-cli-pager)

# arch1_web_ingest_service — attaches ECS task execution managed policy — clean prerequisite for image pull and task startup permissions
aws iam attach-role-policy \
  --role-name "$ARCH1_ECS_EXECUTION_ROLE_NAME" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" \
  --no-cli-pager

# arch1_web_ingest_service — creates CloudWatch log group for ECS task logs — clean operational logging baseline
aws logs create-log-group \
  --log-group-name "/ecs/${ARCH1_WEB_INGEST_SERVICE_NAME}" \
  --tags "Name=${ARCH1_WEB_INGEST_SERVICE_NAME},Project=${TAG_PROJECT_VALUE},Environment=${TAG_ENVIRONMENT_VALUE},ManagedBy=${TAG_MANAGED_BY_VALUE},Architecture=${TAG_ARCH1_VALUE},Tier=external-intake,ResourceGroup=C,TestGroup=${TAG_TEST_GROUP_VALUE}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# arch1_web_ingest_service — creates ECS cluster hosting the ingest service — clean control-plane container orchestration dependency
ARCH1_ECS_CLUSTER_ARN=$(aws ecs create-cluster \
  --cluster-name "$ARCH1_ECS_CLUSTER_NAME" \
  --tags "key=Name,value=${ARCH1_ECS_CLUSTER_NAME}" "key=Project,value=${TAG_PROJECT_VALUE}" "key=Environment,value=${TAG_ENVIRONMENT_VALUE}" "key=ManagedBy,value=${TAG_MANAGED_BY_VALUE}" "key=Architecture,value=${TAG_ARCH1_VALUE}" "key=Tier,value=external-intake" "key=ResourceGroup,value=C" "key=TestGroup,value=${TAG_TEST_GROUP_VALUE}" \
  --region "$AWS_REGION" \
  --query 'cluster.clusterArn' \
  --output text \
  --no-cli-pager)

ARCH1_ECS_CONTAINER_DEFINITIONS_FILE="$(mktemp)"
cat > "$ARCH1_ECS_CONTAINER_DEFINITIONS_FILE" <<EOF
[
  {
    "name": "web-ingest",
    "image": "public.ecr.aws/docker/library/nginx:latest",
    "essential": true,
    "portMappings": [
      {
        "containerPort": 80,
        "hostPort": 80,
        "protocol": "tcp"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/${ARCH1_WEB_INGEST_SERVICE_NAME}",
        "awslogs-region": "${AWS_REGION}",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }
]
EOF

# arch1_web_ingest_service — registers minimal Fargate task definition — clean prerequisite workload definition for ECS service creation
ARCH1_WEB_INGEST_TASK_DEFINITION_ARN=$(aws ecs register-task-definition \
  --family "$ARCH1_ECS_TASK_FAMILY_NAME" \
  --execution-role-arn "$ARCH1_ECS_EXECUTION_ROLE_ARN" \
  --task-role-arn "$ARCH1_ECS_EXECUTION_ROLE_ARN" \
  --network-mode "awsvpc" \
  --requires-compatibilities "FARGATE" \
  --cpu "256" \
  --memory "512" \
  --container-definitions "file://${ARCH1_ECS_CONTAINER_DEFINITIONS_FILE}" \
  --tags "key=Name,value=${ARCH1_ECS_TASK_FAMILY_NAME}" "key=Project,value=${TAG_PROJECT_VALUE}" "key=Environment,value=${TAG_ENVIRONMENT_VALUE}" "key=ManagedBy,value=${TAG_MANAGED_BY_VALUE}" "key=Architecture,value=${TAG_ARCH1_VALUE}" "key=Tier,value=external-intake" "key=ResourceGroup,value=C" "key=TestGroup,value=${TAG_TEST_GROUP_VALUE}" \
  --region "$AWS_REGION" \
  --query 'taskDefinition.taskDefinitionArn' \
  --output text \
  --no-cli-pager)

# arch1_web_ingest_service — creates ECS service in public subnet with B2 SG — clean workload endpoint that depends on required subnet and SG resources
ARCH1_WEB_INGEST_SERVICE_ARN=$(aws ecs create-service \
  --cluster "$ARCH1_ECS_CLUSTER_ARN" \
  --service-name "$ARCH1_WEB_INGEST_SERVICE_NAME" \
  --task-definition "$ARCH1_WEB_INGEST_TASK_DEFINITION_ARN" \
  --desired-count "1" \
  --launch-type "FARGATE" \
  --network-configuration "awsvpcConfiguration={subnets=[${ARCH1_PUBLIC_SUBNET_A_ID}],securityGroups=[${ARCH1_SG_APP_B2_ID}],assignPublicIp=ENABLED}" \
  --tags "key=Name,value=${ARCH1_WEB_INGEST_SERVICE_NAME}" "key=Project,value=${TAG_PROJECT_VALUE}" "key=Environment,value=${TAG_ENVIRONMENT_VALUE}" "key=ManagedBy,value=${TAG_MANAGED_BY_VALUE}" "key=Architecture,value=${TAG_ARCH1_VALUE}" "key=Tier,value=external-intake" "key=ResourceGroup,value=C" "key=TestGroup,value=${TAG_TEST_GROUP_VALUE}" \
  --region "$AWS_REGION" \
  --query 'service.serviceArn' \
  --output text \
  --no-cli-pager)
