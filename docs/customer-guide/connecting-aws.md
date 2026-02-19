# Connecting Your AWS Account

This guide covers connecting your AWS account to AWS Security Autopilot by deploying IAM roles that allow the platform to read security findings and (optionally) execute safe remediations.

## Overview

To connect your AWS account, you need to deploy **two IAM roles**:

1. **ReadRole** (`SecurityAutopilotReadRole`) — **Required** — Allows reading Security Hub, GuardDuty, IAM Access Analyzer, and Inspector findings
2. **WriteRole** (`SecurityAutopilotWriteRole`) — **Optional** — Allows executing safe direct fixes (e.g., enable S3 public access block)

Both roles use **STS AssumeRole** with **ExternalId** for security (no long-lived AWS keys).

---

## Step 1: Get Your External ID

Your External ID is unique to your tenant and is shown during onboarding:

1. **Complete signup** (see [Account Creation](account-creation.md))
2. **Start onboarding wizard**
3. **Copy your External ID** from the onboarding screen

**Format**: `ext-xxxxxxxxxxxxxxxx` (e.g., `ext-a1b2c3d4e5f6g7h8`)

**Note**: Your External ID is also available in **Settings** → **Organization** after onboarding.

---

## Step 2: Deploy ReadRole (Required)

### Option A: CloudFormation Console (Recommended)

1. **Get the template URL** from the onboarding wizard or Settings
   - Default: `https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.1.yaml`

2. **Open AWS CloudFormation Console**:
   - Go to https://console.aws.amazon.com/cloudformation
   - Click **"Create stack"** → **"With new resources (standard)"**

3. **Specify template**:
   - Select **"Amazon S3 URL"**
   - Paste the template URL
   - Click **"Next"**

4. **Specify stack details**:
   - **Stack name**: `SecurityAutopilotReadRole` (or custom)
   - **SaaSAccountId**: `029037611564` (your SaaS provider's AWS account ID)
   - **ExternalId**: Paste your External ID (e.g., `ext-a1b2c3d4e5f6g7h8`)
   - **IncludeWriteRole**: `false` (we'll deploy WriteRole separately if needed)
   - Click **"Next"**

5. **Configure stack options** (optional):
   - Add tags if desired
   - Click **"Next"**

6. **Review**:
   - Review parameters
   - Check **"I acknowledge that AWS CloudFormation might create IAM resources"**
   - Click **"Create stack"**

7. **Wait for stack creation** (takes ~1-2 minutes)

8. **Get the role ARN**:
   - In stack **Outputs**, find **`ReadRoleArn`**
   - Copy the ARN (e.g., `arn:aws:iam::123456789012:role/SecurityAutopilotReadRole`)

### Option B: AWS CLI

```bash
# Download template
curl -O https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/read-role/v1.5.1.yaml

# Create stack
aws cloudformation create-stack \
  --stack-name SecurityAutopilotReadRole \
  --template-body file://read-role-template.yaml \
  --parameters \
    ParameterKey=SaaSAccountId,ParameterValue=029037611564 \
    ParameterKey=ExternalId,ParameterValue=ext-a1b2c3d4e5f6g7h8 \
    ParameterKey=IncludeWriteRole,ParameterValue=false \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# Wait for completion
aws cloudformation wait stack-create-complete \
  --stack-name SecurityAutopilotReadRole \
  --region us-east-1

# Get role ARN
aws cloudformation describe-stacks \
  --stack-name SecurityAutopilotReadRole \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='ReadRoleArn'].OutputValue" \
  --output text
```

---

## Step 3: Deploy WriteRole (Optional)

**Deploy WriteRole only if you want to enable direct fixes** (safe automated remediations).

### Option A: CloudFormation Console

1. **Get the template URL**:
   - Default: `https://security-autopilot-templates.s3.eu-north-1.amazonaws.com/cloudformation/write-role/v1.4.0.yaml`

2. **Create stack** (same process as ReadRole):
   - **Stack name**: `SecurityAutopilotWriteRole`
   - **SaaSAccountId**: `029037611564`
   - **ExternalId**: Your External ID
   - Click **"Create stack"**

3. **Get the role ARN** from stack Outputs

### Option B: Include in ReadRole Stack

You can deploy both roles in one stack:

1. When creating ReadRole stack, set **IncludeWriteRole** to `true`
2. Both roles will be created
3. Get both ARNs from stack Outputs

---

## Step 4: Connect Account in AWS Security Autopilot

### During Onboarding

1. **In the onboarding wizard**, go to **"Integration Role"** step
2. **Enter account details**:
   - **Account ID**: Your AWS account ID (12 digits)
   - **Integration Role ARN**: Paste ReadRole ARN
   - **Write Role ARN** (optional): Paste WriteRole ARN if deployed
   - **Regions**: Select regions to monitor (e.g., `us-east-1`, `us-west-2`)
3. **Click "Connect Account"**
4. **Wait for validation** — The platform will test AssumeRole access

### After Onboarding

1. Go to **Settings** → **AWS Accounts**
2. Click **"Connect Account"**
3. Fill in the same details as above
4. Click **"Connect"**

---

## What Permissions Are Granted?

### ReadRole Permissions

ReadRole allows:
- **Security Hub**: `securityhub:GetFindings`, `securityhub:ListFindings`, `securityhub:DescribeHub`
- **GuardDuty**: `guardduty:ListFindings`, `guardduty:GetFindings`, `guardduty:ListDetectors`
- **IAM Access Analyzer**: `access-analyzer:ListFindings`, `access-analyzer:GetFinding`
- **Inspector**: `inspector2:ListFindings`, `inspector2:GetFinding`
- **Minimal describe calls**: EC2, S3, IAM (for resource metadata)

**No write permissions** — ReadRole cannot modify any resources.

### WriteRole Permissions

WriteRole allows **limited write operations** for safe direct fixes:
- **S3**: `s3:PutAccountPublicAccessBlock` (account-level public access block)
- **Security Hub**: `securityhub:BatchEnableStandards` (enable Security Hub)
- **GuardDuty**: `guardduty:CreateDetector`, `guardduty:UpdateDetector` (enable GuardDuty)
- **No other write permissions** — WriteRole cannot delete resources or modify critical settings

---

## Security Considerations

### External ID

- **Unique per tenant** — Prevents confused deputy attacks
- **Never share** — Keep your External ID private
- **Rotate if compromised** — Contact support to regenerate External ID

### IAM Trust Policy

The roles trust **only your SaaS provider's AWS account** (`029037611564`):
- No other AWS accounts can assume these roles
- ExternalId must match your tenant's External ID

### Least Privilege

- **ReadRole**: Read-only access to security findings
- **WriteRole**: Limited to safe, idempotent operations
- **No delete permissions** — Roles cannot delete resources
- **No billing access** — Roles cannot access billing information

---

## Troubleshooting

### Stack Creation Fails

**Error**: `Resource already exists`

**Solution**: 
- Roles may already exist from a previous deployment
- Delete existing roles manually, or use a different stack name

**Error**: `Invalid parameter: ExternalId`

**Solution**:
- Verify External ID format: `ext-` followed by 16 hex characters
- Ensure no extra spaces or characters

### AssumeRole Fails

**Error**: `AccessDenied` when connecting account

**Solutions**:
- Verify External ID matches exactly (case-sensitive)
- Verify SaaS account ID is correct (`029037611564`)
- Check IAM trust policy allows the SaaS account
- Verify role ARN is correct

### Validation Fails

**Error**: `Cannot assume role` during account connection

**Solutions**:
- Verify role ARN is correct
- Verify role exists in the correct AWS account
- Check CloudFormation stack status (should be `CREATE_COMPLETE`)
- Verify External ID matches

---

## Next Steps

After connecting your AWS account:

1. **[Complete Onboarding](features-walkthrough.md#onboarding-wizard)** — Verify Inspector, Security Hub, Config, and control-plane forwarder
2. **[View Findings](features-walkthrough.md#findings-page)** — See your security findings
3. **[Review Actions](features-walkthrough.md#actions-page)** — Prioritized actions to fix

---

## See Also

- [Account Creation](account-creation.md) — Signup and login
- [Features Walkthrough](features-walkthrough.md) — Complete feature guide
- [Client-Side AWS Resources](../architecture/client/README.md) — Technical details about customer resources
