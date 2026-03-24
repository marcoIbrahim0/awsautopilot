# Manual Test Use Cases

This document lists all core use cases you should test before presenting the product. For each remediation case: (1) how to create the resource or state that triggers the finding, (2) how to get the action in the app, (3) steps to fix it.

**Prerequisites (all flows):**
- AWS account(s) connected with **ReadRole**.
- Worker running and SQS queue configured.
- You are logged in to the app.

---

## Part 1: PR-only remediation (4 cases)

These actions generate a **PR bundle** (Terraform or CloudFormation). You apply the fix yourself (merge PR, run pipeline, or apply manually).

---

### Use case 1 — S3.2: S3 bucket without block public access

**Control:** S3.2 (per-bucket block public access)  
**Action type:** `s3_bucket_block_public_access`

#### 1. Create the resource that triggers the finding

1. In **AWS Console** → **S3** → **Create bucket**.
2. Pick a **region** (e.g. `us-east-1`) and a unique **bucket name** (e.g. `my-test-bucket-no-block-12345`).
3. Under **Block Public Access settings**, **uncheck** “Block all public access” (or leave the bucket with public access allowed).
4. Create the bucket.
5. Ensure **Security Hub** is enabled in that region and that the **AWS Foundational Security Best Practices (FSBP)** standard is enabled so control **S3.2** is evaluated.

#### 2. Get the finding and action in the app

1. In the app: **Accounts** → select the account → **Refresh findings** (or trigger ingest for that account/region).
2. Wait for the worker to run (or use **Refresh findings** and wait).
3. Go to **Actions** → click **Recompute actions** if needed.
4. Find the action for **S3.2** / “S3 bucket block public access” for the bucket you created. Note the **bucket name** (it appears as `target_id` or in the action’s resource).

#### 3. Steps to fix (PR bundle)

1. On that action, choose **Generate PR bundle** (mode **PR only**).
2. Wait for the remediation run to complete (**Remediation runs** or run detail page).
3. **Download the bundle** (or open run detail → **artifacts** → **pr_bundle** → **files**).
4. **Verify the bundle:** Terraform: `aws_s3_bucket_public_access_block` with the correct bucket name; or CloudFormation: `BucketName` and `PublicAccessBlockConfiguration`. Account and region in the bundle must match the action.
5. **Apply the fix:**
   - **Terraform:** Set `bucket` in the `.tf` file to your bucket name, run `terraform init`, `terraform plan`, `terraform apply`.
   - **CloudFormation:** Create/update stack with the template; set `BucketName` to your bucket name.
6. In the app: go back to the **action** → **Recompute actions** (or trigger ingest again). Confirm the finding is resolved and the action status updates.

---

### Use case 2 — S3.4: S3 bucket without default encryption

**Control:** S3.4  
**Action type:** `s3_bucket_encryption`

#### 1. Create the resource that triggers the finding

1. In **AWS Console** → **S3** → **Create bucket**.
2. Choose **region** and a unique **bucket name** (e.g. `my-test-bucket-no-encryption-12345`).
3. **Do not** enable default encryption (leave “Server-side encryption” unset).
4. Create the bucket.
5. Security Hub FSBP must be enabled so **S3.4** is evaluated.

#### 2. Get the finding and action in the app

1. **Refresh findings** for that account (and region).
2. **Recompute actions**. Find the action for **S3.4** / “S3 bucket encryption” for your bucket.

#### 3. Steps to fix (PR bundle)

1. On that action, **Generate PR bundle** (PR only).
2. Wait for run to complete; download or view **artifacts** → **pr_bundle** → **files**.
3. **Verify:** Terraform has `aws_s3_bucket_server_side_encryption_configuration` with correct bucket and AES256; or CloudFormation has `BucketEncryption` / `ServerSideEncryptionConfiguration`.
4. **Apply:** Set bucket name in the IaC, then `terraform init` / `plan` / `apply` or CloudFormation create/update stack.
5. **Recompute actions** (or re-ingest) and confirm the finding is resolved.

---

### Use case 3 — EC2.53: Security group with 0.0.0.0/0 (and/or ::/0) on port 22 or 3389

**Control:** EC2.53 (canonical; aliases: EC2.13 / EC2.19 / EC2.18)  
**Action type:** `sg_restrict_public_ports`

#### 1. Create the resource that triggers the finding

1. In **AWS Console** → **EC2** → **Security Groups** (in a chosen region, e.g. `us-east-1`).
2. **Create security group:** name e.g. `test-sg-public-22`, VPC default or chosen.
3. **Add inbound rule:** Type **SSH** (port 22) or **RDP** (port 3389), Source **0.0.0.0/0** (Anywhere-IPv4).
4. (Optional) Add an IPv6 inbound rule with Source **::/0** (Anywhere-IPv6).
5. Save. Security Hub will flag **EC2.53** (or an equivalent alias control) for this SG.

#### 2. Get the finding and action in the app

1. **Refresh findings** for that account/region.
2. **Recompute actions**. Find the action for **EC2.53** / “Restrict public ports” for the security group (target is the **security group ID**, e.g. `sg-0123456789abcdef0`).

#### 3. Steps to fix (PR bundle)

1. On that action, **Generate PR bundle** (PR only).
2. Wait for run; open **artifacts** → **pr_bundle** → **files**.
3. **Verify:** Terraform has `aws_vpc_security_group_ingress_rule` (or similar) with correct `security_group_id` and ports 22/3389; CloudFormation has `SecurityGroupId` and `AllowedCidr`.
4. **Apply:**
   - Identify SG attachments first (EC2/ENI/ALB/NLB/RDS/ECS/EKS), and treat production workloads with extra caution.
   - Confirm alternative admin path first (SSM Session Manager, bastion, or VPN). Optionally validate current sources via VPC Flow Logs.
   - Replace broad sources (**0.0.0.0/0** and/or **::/0**) incrementally with restricted source(s) (VPN CIDR, office IP, or source SG).
   - Terraform bundle now runs a preflight revoke for conflicting public/duplicate 22/3389 CIDR rules before creating restricted rules.
   - Apply one change at a time and test app/dependency connectivity after each step.
5. **Recompute actions** and confirm the action/finding is resolved.

---

### Use case 4 — CloudTrail.1: CloudTrail not enabled

**Control:** CloudTrail.1  
**Action type:** `cloudtrail_enabled`

#### 1. Create the state that triggers the finding

1. In **AWS Console** → **CloudTrail** (any region, e.g. `us-east-1`).
2. If a trail already exists that meets the control, **delete** it (or use an account that has **no** multi-region trail / no CloudTrail).
3. Security Hub FSBP will report **CloudTrail.1** as failed when CloudTrail is not enabled.

**Note:** If your account already has a compliant trail, you may need a **different test account** or temporarily delete the trail (not recommended in production).

#### 2. Get the finding and action in the app

1. **Refresh findings** for the account.
2. **Recompute actions**. Find the action for **CloudTrail.1** / “CloudTrail enabled”. Target is typically region or account-level (no specific resource ID).

#### 3. Steps to fix (PR bundle)

1. On that action, **Generate PR bundle** (PR only).
2. Wait for run; open **artifacts** → **pr_bundle** → **files**.
3. **Verify:** Terraform has `aws_cloudtrail` with `trail_bucket_name` variable (no hardcoded bucket); CloudFormation has `TrailBucketName` parameter. Steps should say to create/set an S3 bucket for trail logs.
4. **Apply:**
   - Create an S3 bucket for CloudTrail logs (if you don’t have one).
   - Set `trail_bucket_name` (Terraform) or `TrailBucketName` (CloudFormation) and run `terraform init` / `plan` / `apply` or deploy the stack.
5. **Recompute actions** and confirm the finding is resolved.

---

## Part 2: Out-of-scope direct-fix and WriteRole checks

> ⚠️ Status: `direct_fix` and customer `WriteRole` are intentionally out of scope. Supported remediation remains PR-only.

Use this section to confirm the system fails closed instead of advertising or executing a write-capable path.

#### Steps

1. Pick any remediable action and open **Remediation preview** with `mode=pr_only`.
2. **Verify:** Response is informational only and instructs you to generate a PR bundle to review the change set.
3. Call `GET /api/actions/{action_id}/remediation-preview?mode=direct_fix`.
4. **Verify:** Response does not apply anything and returns the out-of-scope message for `direct_fix`.
5. Call `POST /api/remediation-runs` with `"mode": "direct_fix"` for a valid action.
6. **Verify:** Request is rejected and no remediation run is created.

---

## Part 3: Weekly digest

**Purpose:** Trigger the weekly digest job and (if configured) receive email/Slack.

#### Steps

1. **Prerequisites:** `DIGEST_CRON_SECRET` set in env; SQS ingest queue configured; worker running.
2. **Trigger:**  
   `POST /api/internal/weekly-digest`  
   Header: `X-Digest-Cron-Secret: <value of DIGEST_CRON_SECRET>`
3. **Verify response:** 200, body e.g. `{ "enqueued": N, "tenants": N }` with N ≥ 1.
4. **Verify worker:** Worker processes `weekly_digest` jobs (check worker logs).
5. **Verify content (if email/Slack configured):** Tenant has digest enabled and recipients; check inbox or Slack for digest (actions summary, expiring exceptions, “view in app” link).

---

## Part 4: Evidence export (2 cases)

**Purpose:** Generate an evidence pack or compliance pack and confirm the job completes.

**Prerequisites:** S3 export bucket configured (`S3_EXPORT_BUCKET`); worker running; authenticated.

---

### Use case: Evidence pack

1. **Create export:** `POST /api/exports` with body `{ "pack_type": "evidence" }` (or use UI “Export evidence”).
2. **Verify:** 202 with export `id`.
3. **Poll:** `GET /api/exports/{id}` until `status` is `success` or `failed`.
4. **Verify:** `status === "success"`; `download_url` present. Content = findings/actions/evidence (Step 10 style).

---

### Use case: Compliance pack

1. **Create export:** `POST /api/exports` with body `{ "pack_type": "compliance" }`.
2. **Verify:** 202 with export `id`.
3. **Poll:** `GET /api/exports/{id}` until `status` is `success` or `failed`.
4. **Verify:** `status === "success"`; `pack_type === "compliance"`; `download_url` present. Content = evidence + exception attestations + control mapping + auditor summary.

---

## Part 5: Baseline report

**Purpose:** Request a 48h baseline report and confirm the job completes.

**Prerequisites:** Worker running; queue and S3 (or configured storage) for reports. Rate limit: **one report per tenant per 24 hours**.

#### Steps

1. **Create report:**  
   `POST /api/baseline-report`  
   Body `{}` or `{ "account_ids": ["123456789012"] }` (optional; omit for all accounts).
2. **Verify:** 201 with report `id`, `status: "pending"`, message “within 48 hours”.
3. **Poll:** `GET /api/baseline-report/{id}` until `status` is `success` or `failed`.
4. **Verify:** `status === "success"`; `download_url` and/or `outcome` present.
5. **Rate limit:** Request another report within 24h for the same tenant; expect **429** (“One report per tenant per 24 hours”).

---

## Quick reference: controls and fix type

| Control       | Action type                     | Fix type   | How to trigger finding                          |
|--------------|----------------------------------|------------|-------------------------------------------------|
| S3.1         | s3_block_public_access           | Out of scope | Turn off account-level S3 Block Public Access |
| S3.2         | s3_bucket_block_public_access    | PR bundle  | Create S3 bucket without block public access     |
| S3.3         | canonicalizes to S3.2 / s3_bucket_block_public_access | PR bundle | Trigger the same public-access family as S3.2; the finding can stay S3.3 while grouped remediation displays canonical S3.2 |
| S3.8         | canonicalizes to S3.2 / s3_bucket_block_public_access | PR bundle | Trigger the same public-access family as S3.2; the finding can stay S3.8 while grouped remediation displays canonical S3.2 |
| S3.4         | s3_bucket_encryption             | PR bundle  | Create S3 bucket without default encryption     |
| S3.13        | canonicalizes to S3.11 / s3_bucket_lifecycle_configuration | PR bundle | Trigger the lifecycle family; the finding can stay S3.13 while grouped remediation displays canonical S3.11 |
| S3.17        | canonicalizes to S3.15 / s3_bucket_encryption_kms | PR bundle | Trigger the SSE-KMS family; the finding can stay S3.17 while grouped remediation displays canonical S3.15 |
| EC2.13       | canonicalizes to EC2.53 / sg_restrict_public_ports | PR bundle | Trigger the same security-group hardening family as EC2.53; grouped remediation can display canonical EC2.53 |
| EC2.18       | canonicalizes to EC2.53 / sg_restrict_public_ports | PR bundle | Trigger the same security-group hardening family as EC2.53; grouped remediation can display canonical EC2.53 |
| EC2.19       | canonicalizes to EC2.53 / sg_restrict_public_ports | PR bundle | Trigger the same security-group hardening family as EC2.53; grouped remediation can display canonical EC2.53 |
| EC2.53       | sg_restrict_public_ports          | PR bundle  | Create SG with 0.0.0.0/0 (and/or ::/0) on 22 or 3389 |
| CloudTrail.1 | cloudtrail_enabled               | PR bundle  | No CloudTrail (or delete trail)                 |
| SecurityHub.1| enable_security_hub              | Out of scope | Disable Security Hub in a region              |
| GuardDuty.1  | enable_guardduty                 | Out of scope | Disable GuardDuty in a region                 |

---

*Last updated: 2026-03-19*
