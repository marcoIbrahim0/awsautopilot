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
