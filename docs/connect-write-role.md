# Connect WriteRole — Enable Direct Fixes

This document describes how to connect the optional **WriteRole** to enable safe direct remediations (S3 Block Public Access, Security Hub, GuardDuty enablement). WriteRole is **optional**; many customers start with read-only access. Deploy it only when you are ready for direct fixes.

## Overview

- **ReadRole** (required): Used for Security Hub findings ingestion. No write access.
- **WriteRole** (optional): Used for direct fixes. Scoped to three safe operations only.

When WriteRole is **not** configured:
- Ingestion, actions, findings, exceptions, and PR-only remediation work as usual.
- Direct fix runs fail with: "WriteRole not configured; use PR-only or add WriteRole ARN in account settings."

## Deploy WriteRole

### 1. CloudFormation template

The WriteRole template is at:

```
infrastructure/cloudformation/write-role-template.yaml
```

**Parameters:**

| Parameter       | Description                                                       |
|----------------|-------------------------------------------------------------------|
| SaaSAccountId  | Your SaaS AWS account ID (12 digits). Same as ReadRole.           |
| ExternalId     | Tenant external ID. **Must match** the value stored for this tenant (same as ReadRole). |

### 2. Deploy in customer AWS account

**Option A — AWS Console**

1. In the customer AWS account, open **CloudFormation → Stacks → Create stack**.
2. Choose **Upload a template file** or **Amazon S3 URL** if you host the template.
3. Stack name: e.g. `SecurityAutopilotWriteRole`.
4. Enter `SaaSAccountId` and `ExternalId` (from your SaaS Settings → Organization).
5. Create stack.
6. Copy the **WriteRoleArn** from the stack **Outputs** tab.

**Option B — AWS CLI**

```bash
aws cloudformation create-stack \
  --stack-name SecurityAutopilotWriteRole \
  --template-body file://infrastructure/cloudformation/write-role-template.yaml \
  --parameters \
    ParameterKey=SaaSAccountId,ParameterValue=YOUR_SAAS_ACCOUNT_ID \
    ParameterKey=ExternalId,ParameterValue=YOUR_TENANT_EXTERNAL_ID \
  --capabilities CAPABILITY_NAMED_IAM
```

After the stack succeeds, get the output:

```bash
aws cloudformation describe-stacks --stack-name SecurityAutopilotWriteRole \
  --query 'Stacks[0].Outputs[?OutputKey==`WriteRoleArn`].OutputValue' --output text
```

### 3. Connect WriteRole in SaaS

**API — PATCH account**

```http
PATCH /api/aws/accounts/{account_id}
Content-Type: application/json

{
  "role_write_arn": "arn:aws:iam::123456789012:role/SecurityAutopilotWriteRole"
}
```

The `account_id` in the path must match the account ID in the ARN.

**Remove WriteRole (disable direct fixes):**

```http
PATCH /api/aws/accounts/{account_id}
Content-Type: application/json

{
  "role_write_arn": null
}
```

**Registration — optional at connect time**

When registering a new account, you can include WriteRole in the same request:

```http
POST /api/aws/accounts
Content-Type: application/json

{
  "account_id": "123456789012",
  "role_read_arn": "arn:aws:iam::123456789012:role/SecurityAutopilotReadRole",
  "role_write_arn": "arn:aws:iam::123456789012:role/SecurityAutopilotWriteRole",
  "regions": ["us-east-1", "eu-west-1"],
  "tenant_id": "..."
}
```

## WriteRole permissions (least privilege)

The template creates an IAM role with **only** these scoped permissions:

| Fix                    | IAM actions                                                                 |
|------------------------|-----------------------------------------------------------------------------|
| S3 Block Public Access | `s3:GetAccountPublicAccessBlock`, `s3:PutAccountPublicAccessBlock`          |
| Security Hub           | `securityhub:EnableSecurityHub`, `securityhub:GetEnabledStandards`, `securityhub:DescribeHub` |
| GuardDuty              | `guardduty:CreateDetector`, `guardduty:GetDetector`, `guardduty:ListDetectors` |
| Validation             | `sts:GetCallerIdentity`                                                     |

All actions use `Resource: "*"` as required by these account-level and service APIs.

## Trust policy

The role trusts only your SaaS account and requires the tenant `ExternalId`:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "arn:aws:iam::YOUR_SAAS_ACCOUNT_ID:root"},
    "Action": "sts:AssumeRole",
    "Condition": {"StringEquals": {"sts:ExternalId": "TENANT_EXTERNAL_ID"}}
  }]
}
```

## Launch Stack URL (optional)

If you host the WriteRole template on S3/CloudFront (similar to ReadRole), you can provide a Launch Stack URL in the UI. Add configuration:

- `CLOUDFORMATION_WRITE_ROLE_TEMPLATE_URL` — full HTTPS URL to the Write Role template.

The UI can then show a **Deploy Write Role** button next to **Deploy Read Role** on Settings → Organization or Connect AWS flows.

## Checklist

- [ ] Deploy WriteRole stack in customer AWS account (same ExternalId as ReadRole).
- [ ] Copy WriteRoleArn from stack Outputs.
- [ ] PATCH `/api/aws/accounts/{account_id}` with `role_write_arn`, or include it in initial registration.
- [ ] Direct fix actions (e.g. "Run fix" on S3 Block Public Access) will now use WriteRole when approved.
