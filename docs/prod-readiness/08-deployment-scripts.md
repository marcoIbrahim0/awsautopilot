# Deployment Scripts — AWS Security Test Environment

## How to use these scripts
These scripts are intended for isolated AWS test accounts used for security control validation and remediation proof runs. Set required environment variables and placeholders first, then run each script only in the sequence needed for your test objective. Deploy scripts create both baseline and adversarial states, while reset scripts reintroduce misconfigurations for repeatable validation cycles. Review safety warnings and manual-gate checkpoints before execution, especially for root-credential and immutable-resource scenarios.

## Architecture 1 — RapidClaims Telehealth Evidence Pipeline

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
```

## Architecture 2 — RapidRad Teleradiology Exchange Platform

```bash
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
aws configservice put-configuration-recorder \
  --region "$AWS_REGION" \
  --configuration-recorder "name=${ARCH2_CONFIG_RECORDER_C_NAME},roleARN=${ARCH2_CONFIG_SERVICE_ROLE_ARN},recordingGroup={allSupported=true,includeGlobalResourceTypes=true}"
ARCH2_CONFIG_RECORDER_C_STATUS="configured"
echo "ARCH2_CONFIG_RECORDER_C_NAME=$ARCH2_CONFIG_RECORDER_C_NAME"
echo "ARCH2_CONFIG_RECORDER_C_STATUS=$ARCH2_CONFIG_RECORDER_C_STATUS"

# 9) arch2_config_delivery_channel_c — AWS::Config::DeliveryChannel
log_step "09" "arch2_config_delivery_channel_c" "AWS::Config::DeliveryChannel"
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
    --engine-version "$ARCH2_RDS_ENGINE_VERSION" \
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
    --version "$ARCH2_EKS_KUBERNETES_VERSION" \
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
```

## Reset Commands — Architecture 1

```bash
#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Variables block (Architecture 1 variables from 08-task2-deploy-arch1.sh)
# ---------------------------------------------------------------------------
ACCOUNT_ID="<YOUR_ACCOUNT_ID_HERE>"
AWS_REGION="<YOUR_AWS_REGION_HERE>"

ARCH1_VPC_MAIN_NAME="arch1_vpc_main"
ARCH1_SG_APP_B2_NAME="arch1_sg_app_b2"
ARCH1_SG_DEPENDENCY_A2_NAME="arch1_sg_dependency_a2"
ARCH1_BUCKET_WEBSITE_A1_NAME="arch1_bucket_website_a1"
ARCH1_BUCKET_POLICY_WEBSITE_A1_NAME="arch1_bucket_policy_website_a1"
ARCH1_BUCKET_EVIDENCE_B1_NAME="arch1_bucket_evidence_b1"
ARCH1_BUCKET_PAB_EVIDENCE_B1_NAME="arch1_bucket_pab_evidence_b1"

SSH_PORT="22"
PUBLIC_CIDR_ANY="0.0.0.0/0"

ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME="${ARCH1_BUCKET_WEBSITE_A1_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}"
ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME="${ARCH1_BUCKET_EVIDENCE_B1_NAME//_/-}-${ACCOUNT_ID}-${AWS_REGION}"

# Resource ID variables needed by reset commands.
ARCH1_VPC_ID="${ARCH1_VPC_ID:-$(aws ec2 describe-vpcs \
  --filters "Name=tag:Name,Values=${ARCH1_VPC_MAIN_NAME}" \
  --region "$AWS_REGION" \
  --query 'Vpcs[0].VpcId' \
  --output text \
  --no-cli-pager)}"

ARCH1_SG_DEPENDENCY_A2_ID="${ARCH1_SG_DEPENDENCY_A2_ID:-$(aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=${ARCH1_VPC_ID}" "Name=group-name,Values=${ARCH1_SG_DEPENDENCY_A2_NAME}" \
  --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --no-cli-pager)}"

ARCH1_SG_APP_B2_ID="${ARCH1_SG_APP_B2_ID:-$(aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=${ARCH1_VPC_ID}" "Name=group-name,Values=${ARCH1_SG_APP_B2_NAME}" \
  --region "$AWS_REGION" \
  --query 'SecurityGroups[0].GroupId' \
  --output text \
  --no-cli-pager)}"

# ============================================================
# RESET: arch1_bucket_website_a1
# Group: A
# Control ID: S3.2, S3.3, S3.8, S3.17
# Restores: Re-disables bucket public access block and re-enables static website hosting for anonymous website access.
# ============================================================
# RESET arch1_bucket_website_a1 — restores disabled bucket public access block for website exposure
aws s3api put-public-access-block \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" \
  --region "$AWS_REGION" \
  --no-cli-pager

# RESET arch1_bucket_website_a1 — restores static website hosting configuration
aws s3api put-bucket-website \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --website-configuration "IndexDocument={Suffix=index.html},ErrorDocument={Key=error.html}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# ============================================================
# RESET: arch1_bucket_policy_website_a1
# Group: A
# Control ID: S3.5
# Restores: Re-applies the website bucket policy that grants s3:GetObject to Principal "*".
# ============================================================
# RESET arch1_bucket_policy_website_a1 — restores public read policy granting s3:GetObject to "*"
aws s3api put-bucket-policy \
  --bucket "$ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME" \
  --policy "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"PublicReadWebsiteObjects\",\"Effect\":\"Allow\",\"Principal\":\"*\",\"Action\":[\"s3:GetObject\"],\"Resource\":[\"arn:aws:s3:::${ARCH1_BUCKET_WEBSITE_A1_BUCKET_NAME}/*\"]}]}" \
  --region "$AWS_REGION" \
  --no-cli-pager

# ============================================================
# RESET: arch1_sg_dependency_a2
# Group: A
# Control ID: EC2.53, EC2.13, EC2.18, EC2.19
# Restores: Re-adds inbound TCP 22 from 0.0.0.0/0 on SG-A.
# ============================================================
# RESET arch1_sg_dependency_a2 — restores public SSH ingress (22/tcp from 0.0.0.0/0)
aws ec2 authorize-security-group-ingress \
  --group-id "$ARCH1_SG_DEPENDENCY_A2_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=${SSH_PORT},ToPort=${SSH_PORT},IpRanges=[{CidrIp=${PUBLIC_CIDR_ANY},Description='intentional-a2-public-ssh'}]" \
  --region "$AWS_REGION" \
  --no-cli-pager

# ============================================================
# RESET: arch1_bucket_pab_evidence_b1
# Group: C
# Control ID: S3.2, S3.3, S3.8, S3.17
# Restores: Re-disables bucket public access block only while preserving existing bucket policy statements.
# ============================================================
# RESET arch1_bucket_pab_evidence_b1 — restores disabled bucket public access block only
aws s3api put-public-access-block \
  --bucket "$ARCH1_BUCKET_EVIDENCE_B1_BUCKET_NAME" \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" \
  --region "$AWS_REGION" \
  --no-cli-pager

# ============================================================
# RESET: arch1_sg_app_b2
# Group: C
# Control ID: EC2.53, EC2.13, EC2.18, EC2.19
# Restores: Re-adds only inbound TCP 22 from 0.0.0.0/0 while preserving legitimate HTTPS/app/PostgreSQL rules.
# ============================================================
# RESET arch1_sg_app_b2 — restores only the public SSH ingress rule (22/tcp from 0.0.0.0/0)
aws ec2 authorize-security-group-ingress \
  --group-id "$ARCH1_SG_APP_B2_ID" \
  --ip-permissions "IpProtocol=tcp,FromPort=${SSH_PORT},ToPort=${SSH_PORT},IpRanges=[{CidrIp=${PUBLIC_CIDR_ANY},Description='intentional-misconfig-public-ssh'}]" \
  --region "$AWS_REGION" \
  --no-cli-pager
```

## Reset Commands — Architecture 2

```bash
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
```
