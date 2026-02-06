# Manual Test Use Cases

This document lists all core use cases you should test before presenting the product. For each remediation case: (1) how to create the resource or state that triggers the finding, (2) how to get the action in the app, (3) steps to fix it.

**Prerequisites (all flows):**
- AWS account(s) connected with **ReadRole** (and **WriteRole** for direct-fix tests).
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

### Use case 3 — EC2.18: Security group with 0.0.0.0/0 on port 22 or 3389

**Control:** EC2.18 (FSBP)  
**Action type:** `sg_restrict_public_ports`

#### 1. Create the resource that triggers the finding

1. In **AWS Console** → **EC2** → **Security Groups** (in a chosen region, e.g. `us-east-1`).
2. **Create security group:** name e.g. `test-sg-public-22`, VPC default or chosen.
3. **Add inbound rule:** Type **SSH** (port 22) or **RDP** (port 3389), Source **0.0.0.0/0** (Anywhere-IPv4).
4. Save. Security Hub FSBP will flag **EC2.18** for this SG.

#### 2. Get the finding and action in the app

1. **Refresh findings** for that account/region.
2. **Recompute actions**. Find the action for **EC2.18** / “Restrict public ports” for the security group (target is the **security group ID**, e.g. `sg-0123456789abcdef0`).

#### 3. Steps to fix (PR bundle)

1. On that action, **Generate PR bundle** (PR only).
2. Wait for run; open **artifacts** → **pr_bundle** → **files**.
3. **Verify:** Terraform has `aws_vpc_security_group_ingress_rule` (or similar) with correct `security_group_id` and ports 22/3389; CloudFormation has `SecurityGroupId` and `AllowedCidr`. Steps in the bundle should say to **remove** existing 0.0.0.0/0 rules first.
4. **Apply:**
   - In AWS Console (or CLI): **remove** the inbound rule that allows 0.0.0.0/0 on 22 (and 3389 if present).
   - Optionally apply the bundle to add a **restricted** rule (e.g. your IP or VPN CIDR) using the generated IaC.
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

## Part 2: Direct-fix remediation (3 cases)

These actions can be fixed **directly** by the app using the account’s **WriteRole**. No PR bundle to apply manually.

**Prerequisite:** The AWS account must have **WriteRole** configured and trusted (see `docs/connect-write-role.md`).

---

### Use case 5 — S3.1: Account-level S3 Block Public Access off

**Control:** S3.1  
**Action type:** `s3_block_public_access`

#### 1. Create the state that triggers the finding

1. In **AWS Console** → **S3** → **Block Public Access settings for this account** (account-level, not per bucket).
2. Click **Edit** and **uncheck** all four “Block public access” options (or at least one), then save.
3. Security Hub FSBP will report **S3.1** as failed.

#### 2. Get the finding and action in the app

1. **Refresh findings** for that account.
2. **Recompute actions**. Find the action for **S3.1** / “S3 block public access” (account-level; region may be empty or global).

#### 3. Steps to fix (direct fix)

1. (Optional) On the action, open **Remediation preview** (dry-run) and confirm it reports non-compliant and `will_apply: true`.
2. On the action, choose **Run fix** (mode **Direct fix**).
3. Wait for the remediation run to complete (worker must be running).
4. **Verify in the app:** Run status **success**; logs show pre-check, apply, post-check; outcome indicates success or “Already compliant”.
5. **Verify in AWS:** **S3** → **Block Public Access settings for this account** — all four blocks should be **On**.

---

### Use case 6 — SecurityHub.1: Security Hub disabled in region

**Control:** SecurityHub.1  
**Action type:** `enable_security_hub`

#### 1. Create the state that triggers the finding

1. In **AWS Console** → **Security Hub** → switch to a **region** where Security Hub is enabled (e.g. `us-east-1`).
2. **Disable** Security Hub for that region (Settings → Disable Security Hub).
3. Security Hub may not report itself in that region after disable; the finding can appear from a **different region** that still has Security Hub enabled and evaluates the standard, or you may need to re-enable Security Hub, run ingest, then disable again to get a fresh finding. Alternatively use an **account/region** where Security Hub was never enabled so the control fails.

**Practical note:** Easiest is to use a **second region** where Security Hub is not enabled; run ingest including that region; the finding for SecurityHub.1 will appear for that region.

#### 2. Get the finding and action in the app

1. **Refresh findings** for the account (include the region where Security Hub is off).
2. **Recompute actions**. Find the action for **SecurityHub.1** / “Enable Security Hub” for that **region**.

#### 3. Steps to fix (direct fix)

1. (Optional) **Remediation preview** — should say not compliant and will apply.
2. On the action, **Run fix** (Direct fix).
3. Wait for run to complete.
4. **Verify in the app:** Run success; logs and outcome OK.
5. **Verify in AWS:** **Security Hub** in that **region** → Security Hub is **Enabled**.

---

### Use case 7 — GuardDuty.1: GuardDuty disabled in region

**Control:** GuardDuty.1  
**Action type:** `enable_guardduty`

#### 1. Create the state that triggers the finding

1. In **AWS Console** → **GuardDuty** → select a **region** where GuardDuty is enabled.
2. **Disable** GuardDuty for that region (or use a region where it was never enabled).
3. Security Hub FSBP will report **GuardDuty.1** as failed for that region.

#### 2. Get the finding and action in the app

1. **Refresh findings** for the account (include that region).
2. **Recompute actions**. Find the action for **GuardDuty.1** / “Enable GuardDuty” for that **region**.

#### 3. Steps to fix (direct fix)

1. (Optional) **Remediation preview** — not compliant, will apply.
2. On the action, **Run fix** (Direct fix).
3. Wait for run to complete.
4. **Verify in the app:** Run success.
5. **Verify in AWS:** **GuardDuty** in that **region** → GuardDuty is **Enabled**.

---

## Part 3: Remediation preview (dry-run)

**Purpose:** Check current state and whether a direct fix would apply, **without** making changes.

#### Steps

1. Pick an action that supports **direct fix** (S3.1, SecurityHub.1, or GuardDuty.1) and ensure the account has **WriteRole**.
2. Open the action detail and use **Remediation preview** (or call `GET /api/actions/{action_id}/remediation-preview?mode=direct_fix` with auth).
3. **Verify response:**
   - **compliant:** `true` if already fixed, `false` if not.
   - **message:** describes current state (e.g. “S3 Block Public Access is already enabled” or “Security Hub is disabled in region X”).
   - **will_apply:** `true` if the fix would change something, `false` if already compliant.
4. **Verify:** No remediation run is created; no changes in AWS.

---

## Part 4: Weekly digest

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

## Part 5: Evidence export (2 cases)

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

## Part 6: Baseline report

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
| S3.1         | s3_block_public_access           | Direct     | Turn off account-level S3 Block Public Access   |
| S3.2         | s3_bucket_block_public_access    | PR bundle  | Create S3 bucket without block public access     |
| S3.4         | s3_bucket_encryption             | PR bundle  | Create S3 bucket without default encryption     |
| EC2.18       | sg_restrict_public_ports          | PR bundle  | Create SG with 0.0.0.0/0 on 22 or 3389          |
| CloudTrail.1 | cloudtrail_enabled               | PR bundle  | No CloudTrail (or delete trail)                 |
| SecurityHub.1| enable_security_hub              | Direct     | Disable Security Hub in a region                |
| GuardDuty.1  | enable_guardduty                 | Direct     | Disable GuardDuty in a region                   |

---

*Last updated: 2026-02-03*
