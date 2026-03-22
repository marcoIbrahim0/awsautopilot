# AWS Security Autopilot — Remediation Safety Complete Plan
**Date:** 2026-03-03 | **Last updated:** 2026-03-03 (verification gaps resolved) | **Scope:** All 16 in-scope remediation controls + user communication + post-fix access guidance

> ⚠️ Status note (2026-03-04): This document is the planning baseline. Execution status for Tasks 5/6 and Live Test C final rerun is tracked in `docs/phase-2/remediation-safety-tasks.md` and `docs/audit-remediation/evidence/phase2-live-test-c-20260303T234636Z/summary.md`.

---

## Part 1: Re-Audit Results

### A) Executive Summary

- **Total flagged areas: 8** (prior audit had 7 — one additional miss found)
- **1 new miss identified:** S3.9 self-referencing log bucket default (P2)
- **S3.5 severity upgraded to P1+:** IaC overwrites existing bucket policy with no merge
- **3 out-of-scope controls confirmed correctly excluded** (not silently dropped)
- **Top 3 highest-risk items:**
  1. **S3.1 (P0):** CloudFormation bundle is a no-op placeholder — deploys a green stack but never blocks public S3 access
  2. **EC2.53 (P0):** Terraform auto-revokes public SSH/RDP rules before adding restricted ones — no confirmed alternative access path required
  3. **IAM.4 (P0):** Delete path has no MFA or break-glass preflight check — permanent, irreversible action without fallback validation

---

### B) Scope Validation Table

| Control | In Scope? | Audited? | Outcome | Notes |
|---|---|---|---|---|
| S3.1 | Yes | Yes | **Flagged P0** | CF bundle is a WaitConditionHandle no-op |
| SecurityHub.1 | Yes | Yes | Clean | Idempotent enable; safe |
| GuardDuty.1 | Yes | Yes | Clean | Idempotent enable; safe |
| S3.2 (account) | Yes | Yes | Clean | All 4 flags set; CF path uses CLI-only (correct) |
| S3.4 | Yes | Yes | Clean | SSE-AES256; additive; no overwrite |
| EC2.53 (+EC2.13/18/19) | Yes | Yes | **Flagged P0** | Pre-revoke local-exec; no fallback confirmation |
| CloudTrail.1 | Yes | Yes | **Flagged P1** | Bundle creates trail but not the required S3 bucket policy |
| Config.1 | Yes | Yes | **Flagged P1** | Overwrites existing recorder recordingGroup + delivery channel |
| SSM.7 | Yes | Yes | Clean | Account-level toggle; low blast radius; reversible |
| EC2.182 | Yes | Yes | Clean | EBS snapshot block; low blast radius; strategy variants labeled |
| EC2.7 | Yes | Yes | Clean | EBS default encryption; additive; new volumes only |
| S3.5 | Yes | Yes | **Flagged P1+** | IaC overwrites bucket policy; no merge of existing statements |
| IAM.4 | Yes | Yes | **Flagged P0** | Delete path: no MFA/break-glass preflight |
| S3.9 | Yes | Yes | **Flagged P2** | Default log bucket = source bucket; self-logging risk |
| S3.11 | Yes | Yes | **Flagged P1** | CF `AWS::S3::Bucket` risks re-creating existing bucket |
| S3.15 | Yes | Yes | Clean | SSE-KMS; defaults to aws/s3 alias; KMS caveat documented |
| RDS.PUBLIC_ACCESS | No | No | Out-of-scope by design | Correctly excluded |
| RDS.ENCRYPTION | No | No | Out-of-scope by design | Correctly excluded |
| EKS.PUBLIC_ENDPOINT | No | No | Out-of-scope by design | Correctly excluded |

---

### C) Confirmed Issues

---

#### Issue 1: S3.1 — CloudFormation Bundle is a No-Op (P0)

**Why illogical (PM language):** CloudFormation format generates a `WaitConditionHandle` placeholder. Deploying it produces a green "CREATE_COMPLETE" stack but does nothing to block public S3 access. Customer believes they're protected — they are not.

**Evidence:** `pr_bundle.py` → `_cloudformation_s3_content()`, line 904: `Type: AWS::CloudFormation::WaitConditionHandle`.

**Fix:**
- Replace with a Lambda Custom Resource that calls `s3control:PutPublicAccessBlock` (same pattern as SSM.7/EC2.7 CF bundles)
- OR remove the CF option entirely and surface a clear redirect to Terraform + CLI

**Acceptance criteria:** After stack apply, `aws s3control get-public-access-block --account-id <ID>` must return all four flags as `true`.

**Owner:** Backend (pr_bundle.py) | **Rollout:** Immediate

---

#### Issue 2: EC2.53 — Pre-Revoke Without Fallback Access Validation (P0)

**Why illogical (PM language):** Terraform bundle runs a `null_resource` local-exec script that automatically revokes all `0.0.0.0/0` and `::/0` rules on ports 22 and 3389 before adding restricted ones. If the customer's only access path is public SSH/RDP, applying this locks them out permanently.

**Evidence:** `pr_bundle.py` → `_terraform_sg_restrict_content()`, lines 1966–1993. `null_resource.revoke_public_admin_ingress` runs before ingress rules are added via `depends_on`. Errors suppressed with `|| true`.

**Fix (Terraform path):**
- Add `remove_existing_public_rules = false` variable (default `false` — opt-in)
- Customer must explicitly set to `true` to enable auto-revoke
- Add a pre-apply confirmation step in the UI and bundle instructions

**Fix (CloudFormation path — CF parity required):** ✅ Decision confirmed 2026-03-03
The CF path is additive-only (adds restricted rules, does not revoke `0.0.0.0/0`). This is operationally incomplete — noncompliant public rules remain in place after apply. Two acceptable options:
1. Add a Custom Resource Lambda that calls `ec2:RevokeSecurityGroupIngress` for the public rules (full parity with Terraform path)
2. Add explicit **fail-closed** language in the CF bundle: a step that says *"You MUST manually revoke existing 0.0.0.0/0 rules on ports 22/3389 before this remediation is considered complete"* and surface this as a required checklist item in the UI run status

Option 2 is lower risk to ship first; option 1 achieves full automation parity.

**Acceptance criteria (Terraform):** With default settings, `terraform plan` against a group with `0.0.0.0/0` on port 22 must show zero revocations.
**Acceptance criteria (CloudFormation):** Bundle README must include a mandatory manual-revoke checklist. Run status must show "Verification required" until the user confirms manual revoke is complete.

**Owner:** Backend (pr_bundle.py) + PM (UI confirmation step + CF checklist) | **Rollout:** Immediate

---

#### Issue 3: IAM.4 — Delete Path Has No Fallback Preflight (P0)

**Why illogical (PM language):** The delete root access key path permanently removes root API access. The bundle verifies the caller is root and matches the account, but does not check whether root MFA is enrolled or a break-glass process exists. Without MFA, if root console login also fails, the account requires AWS Support intervention.

**Evidence:** `pr_bundle.py` lines 2994–3055: checks account ID + root ARN only. `root_key_remediation_executor_worker.py` `execute_delete()` (lines 295–394): gates on `window_clean`, `active_key_gate`, feature flags, and self-cutoff guard — **confirmed: no MFA check present** (`root_key_remediation_executor_worker.py` lines 295, 603). Strategy registry warning (line 454) is advisory only, not a blocking gate.

**Fix:**
- Add preflight: check `iam:GetAccountSummaryReport` → `AccountMFAEnabled`. Block delete strategy selection if MFA not enrolled
- Add UI checkbox: "I confirm root console MFA is active and a break-glass process is documented"
- Promote warning to a hard gate at run creation time in `execute_delete` or at strategy validation

**Acceptance criteria:** `iam_root_key_delete` strategy must fail to proceed (hard error, not warning) when root MFA is disabled.

**Owner:** Backend (root_key_remediation_executor_worker.py, remediation_runtime_checks.py) + PM (UI gate) | **Rollout:** Immediate

---

#### Issue 4: S3.5 — SSL Policy Overwrites Existing Bucket Policy (P1+)

**Why illogical (PM language):** The SSL enforcement bundle writes a complete `aws_s3_bucket_policy` with only the SSL-deny statement. Any existing policy (cross-account grants, existing Deny statements, KMS conditions) is silently overwritten. Instructions say "merge" but the IaC does not merge.

**Evidence:** `pr_bundle.py` → `_terraform_s3_bucket_require_ssl_content()` lines 2904–2951. `resource "aws_s3_bucket_policy"` sets policy directly with no `source_policy_documents` from existing policy. Same issue in CloudFormation path (lines 2954–2991).

**Confirmed gap (2026-03-03):** `remediation_runtime_checks.py` line 380 + line 441 confirm that existing-policy capture is **not implemented** for S3.5. Only `s3_policy_analysis_possible` (readability flag) is collected. Full policy JSON capture exists only for S3.2 CloudFront migration (`pr_bundle.py` line 224). The S3.5 fix therefore requires **two** backend changes:

**Fix:**
1. **`remediation_runtime_checks.py`**: Add bucket policy JSON capture for `s3_bucket_require_ssl` action type (same pattern as S3.2 — capture `existing_bucket_policy_json` + `existing_bucket_policy_statement_count` in risk evidence)
2. **`pr_bundle.py`**: Add `data "aws_s3_bucket_policy" "existing"` + merge via `source_policy_documents` in Terraform generator; surface captured policy in `terraform.auto.tfvars.json` (same as CloudFront OAC migration pattern at line 1196–1211)
3. Add fail-closed: if policy evidence is missing at bundle generation time, raise `bucket_policy_preservation_evidence_missing` error (same pattern used at line 255)

**Acceptance criteria:** After apply, all pre-existing bucket policy statements must still be present. Test: apply against bucket with existing Deny statement; verify Deny persists.

**Owner:** Backend (pr_bundle.py, remediation_runtime_checks.py) | **Rollout:** Near-term

---

#### Issue 5: CloudTrail.1 — Trail Created Without S3 Bucket Policy (P1)

**Why illogical (PM language):** The bundle creates a CloudTrail Trail pointing to a user-specified S3 bucket, but does not configure the required bucket policy. Without `s3:GetBucketAcl` and `s3:PutObject` on `AWSLogs/*` for the `cloudtrail.amazonaws.com` principal, CloudTrail cannot deliver logs. The trail shows as "Enabled" but nothing is recorded.

**Evidence:** `pr_bundle.py` → `_terraform_cloudtrail_content()` lines 2183–2203: creates `aws_cloudtrail` resource with `s3_bucket_name` but no `aws_s3_bucket_policy` resource. CloudFormation template (lines 2206–2227): same gap.

**Fix:**
- Add `aws_s3_bucket_policy.cloudtrail_delivery` to the Terraform bundle with the required statements
- Add same via `AWS::S3::BucketPolicy` in the CloudFormation template
- If the delivery bucket is pre-existing (not created by the bundle), add a step requiring the customer to confirm bucket policy is configured, with the exact policy JSON to apply

**Acceptance criteria:** After apply, `aws cloudtrail get-trail-status --name security-autopilot-trail` must show `IsLogging: true` with no delivery errors.

**Owner:** Backend (pr_bundle.py, CloudTrail generator) | **Rollout:** Near-term

---

#### Issue 6: Config.1 — Overwrites Existing Recorder and Delivery Channel (P1)

**Why illogical (PM language):** The bundle detects the existing recorder name then calls `put-configuration-recorder` unconditionally with `allSupported: true`. If a custom `recordingGroup` exists (recording only specific resource types to reduce cost), it is overwritten. Similarly, `put-delivery-channel` silently redirects Config delivery, potentially disrupting centralized log pipelines.

**Sub-issue:** When creating a local delivery bucket, the bundle calls `put-bucket-policy` with a hardcoded two-statement policy, overwriting any existing bucket policy.

**Evidence:** `pr_bundle.py` lines 2643–2665. Lines 2636–2641: hardcoded bucket policy overwrite.

**Fix:**
- Pre-flight: call `describe-configuration-recorders` and check if recorder exists and is running. Surface a warning before overwriting `recordingGroup`
- Make `recording_all_resources` a variable defaulting to `false`
- For delivery channel: check existing bucket before redirecting
- For bucket policy: read existing policy and merge rather than replace

**Acceptance criteria:** Bundle applied to account with running selective recorder must not change its `resourceTypes` list without explicit opt-in.

**Owner:** Backend (pr_bundle.py) | **Rollout:** Near-term

---

#### Issue 7: S3.11 — CloudFormation Bundle Risks Re-Creating Existing Bucket (P1)

**Why illogical (PM language):** The CloudFormation template uses `AWS::S3::Bucket` to configure a lifecycle policy. Applied to an existing bucket managed outside CloudFormation, this can cause conflicts, unexpected updates, or bucket re-creation attempts — risking data loss. The Terraform path correctly uses `aws_s3_bucket_lifecycle_configuration` (standalone, targeting existing bucket).

**Evidence:** `pr_bundle.py` → `_cloudformation_s3_bucket_lifecycle_configuration_content()` lines 1723–1753. `Type: AWS::S3::Bucket` used instead of a targeted lifecycle resource.

**Fix:**
- Replace with a Lambda Custom Resource that calls `s3:PutLifecycleConfiguration` on the existing bucket directly (same pattern as SSM.7 and EC2.7 CF bundles)

**Acceptance criteria:** Deploying the CF bundle against a pre-existing unmanaged bucket must not result in stack failure or bucket deletion.

**Owner:** Backend (pr_bundle.py CloudFormation generator) | **Rollout:** Near-term

---

#### Issue 8: S3.9 — Default Log Bucket Equals Source Bucket (P2)

**NEW — not in prior audit.**

**Why illogical (PM language):** Both `source_bucket_name` and `log_bucket_name` default to the same bucket. Logging a bucket to itself creates a recursive write loop — every log entry creates a new object, which triggers another log write. This causes runaway storage cost and unusable log data.

**Evidence:** `pr_bundle.py` → `_terraform_s3_bucket_access_logging_content()` lines 1583–1614. Both variables default to `{bucket}`. Same in CloudFormation template (lines 1617–1648): `Default: "{bucket}"` for both `BucketName` and `LogBucketName`.

**Fix:**
- Change `log_bucket_name` default to empty or an explicit blocked placeholder (`REPLACE_LOG_BUCKET_NAME`)
- Add `REPLACE_LOG_BUCKET_NAME` to `_BLOCKED_PLACEHOLDER_TOKENS` in `pr_bundle.py` so bundle cannot be generated without a valid log bucket
- Add step: "Do not use the source bucket as the log destination"

**Acceptance criteria:** Bundle must fail generation (or require explicit override) when `log_bucket_name` equals `source_bucket_name`.

**Owner:** Backend (pr_bundle.py) | **Rollout:** Near-term

---

### D) Items Reviewed and Not Flagged

| Control | Action Type | Reason |
|---|---|---|
| SecurityHub.1 | `enable_security_hub` | Additive enable; idempotent; no existing config overwritten |
| GuardDuty.1 | `enable_guardduty` | Additive enable; idempotent |
| S3.4 | `s3_bucket_encryption` | SSE-AES256; additive; does not touch access policy |
| S3.15 | `s3_bucket_encryption_kms` | Defaults to `aws/s3` alias (safe); CMK instructions clear |
| SSM.7 | `ssm_block_public_sharing` | Account-scope toggle; reversible; no data affected |
| EC2.182 | `ebs_snapshot_block_public_access` | Account-scope toggle; strategy variants labeled; low blast radius |
| EC2.7 | `ebs_default_encryption` | Affects new volumes only; explicit strategy for AWS-managed vs CMK |
| S3.2 (account) | `s3_block_public_access` | All 4 flags set; CF uses CLI-only with clear guidance |

---

## Part 2: User Communication Plan

### Principle: Show changes at the moment of impact, not at login

#### Change Type A — Hard gate added (something that used to work now requires approval first)
*Applies to: IAM.4 delete (MFA gate), S3.9 (log bucket required)*

- Surface a clear inline gate message at the exact decision point (run creation or strategy selection)
- One-time modal on first encounter; do not repeat on every visit
- Message must state: what is now required, and why

#### Change Type B — Generated IaC is different (same action, different output)
*Applies to: EC2.53 (revoke now opt-in), S3.5 (policy now merges instead of overwrites)*

- Add a `Changelog` section to the bundle README.txt with: what changed, what variable/parameter is affected, and what to review before applying
- If a prior run exists for the same action, surface a banner on the run detail page: *"A newer bundle version is available with updated defaults. Regenerate to get the latest."*

#### Change Type C — Retroactive correction (fix was applied but did nothing)
*Applies to: S3.1 CloudFormation no-op*

- Backend job: identify runs with `status=completed`, `format=cloudformation`, `action_type=s3_block_public_access`
- Mark those runs as **"Verification required"** (not "Failed") in the UI
- Surface a persistent banner on affected runs: *"Your CloudFormation stack for S3 account-level block public access did not apply the actual setting. Please re-run using Terraform or the updated CloudFormation bundle."*
- Send a single email notification to affected tenants — this is the only change that warrants email

---

## Part 3: Post-Fix Access Guidance

### Every fix that removes access must include a replacement access path

The current bundles warn that access will change but do not tell users how to access their resources afterward. This must be added to every high-impact bundle.

#### Required bundle sections (add to README.txt for impacted controls)

| Section | Content |
|---|---|
| **Before apply** | Plain-English: what access will be lost (e.g., "Direct SSH from the internet will be blocked") |
| **After apply — how to access your resource** | Step-by-step alternative: SSM, VPN + SSH, bastion, CloudFront domain, etc. |
| **How to verify the fix worked** | One CLI command confirming the security setting is active |
| **How to roll back** | Specific CLI command to restore access if something breaks |

#### Control-specific post-fix access guidance needed

| Control | What's Removed | Replacement to Document |
|---|---|---|
| EC2.53 | Public SSH/RDP (`0.0.0.0/0`) | SSM Session Manager: `aws ssm start-session --target <instance-id>`, or VPN + SSH to `<allowed_cidr>` |
| S3.2 (block public access) | Direct public object URLs | CloudFront domain output: `<output.cloudfront_domain_name>`; update all clients and internal references |
| S3.5 (SSL enforcement) | HTTP requests (will get 403) | Update SDK/CLI to use HTTPS endpoints; test with `aws s3 cp --endpoint-url https://...` |
| SSM.7 (block public sharing) | Publicly accessible SSM documents | Internal access still works via SSM console; share via resource-based policy with specific accounts instead |

---

## Part 4: Prioritized Rollout Plan

### Immediate (block any public release or new customer onboarding)

| # | Control | Fix |
|---|---|---|
| 1 | S3.1 | Replace CF placeholder with Lambda custom resource or remove CF option |
| 2 | EC2.53 | Default `remove_existing_public_rules = false`; add UI confirmation step |
| 3 | IAM.4 | Add MFA preflight gate; block delete if MFA not enrolled |

> **Must-have before rollout:** A customer hitting S3.1 CF no-op, EC2.53 instance lockout, or IAM.4 accidental root key delete is a trust-ending event. These three must ship together.

### Near-term (current sprint/milestone)

| # | Control | Fix | Dependency |
|---|---|---|---|
| 4 | EC2.53 (CF) | Add fail-closed manual-revoke checklist to CF bundle; or add Lambda revoke custom resource for full parity | EC2.53 Terraform fix (item 2, Immediate) ships first |
| 5 | CloudTrail.1 | Add S3 bucket policy to bundle | None |
| 6 | S3.5 | Add policy capture to `remediation_runtime_checks.py`; merge via `source_policy_documents` in bundle | `s3:GetBucketPolicy` in read role |
| 7 | Config.1 | Pre-flight recorder inspection; make `recordingGroup` opt-in | `configservice:DescribeConfigurationRecorders` in read role |
| 8 | S3.11 | Replace CF `AWS::S3::Bucket` with Lambda custom resource | None |
| 9 | S3.9 | Change log bucket default to invalid placeholder; add to blocked token set | None |

### Later (backlog)

- Automate post-apply re-verification (background re-eval 15–30 min after run completion, not manual "Recompute actions")
- Audit the exception flow governance: time-bounding, approvals, re-justification cadence
- Standardize all CloudFormation bundles for existing resource modification to use Lambda custom resource pattern (remove all `AWS::S3::Bucket` used on existing buckets)
- Add `bundle_version` metadata field to every README.txt for support traceability

---

## Part 5: Permission Prerequisites for New Preflight Checks

The following API permissions must be added to the platform read role before the near-term fixes can be implemented:

| Fix | Required Permission | Why |
|---|---|---|
| IAM.4 MFA gate | `iam:GetAccountSummaryReport` | Check `AccountMFAEnabled` before allowing delete strategy |
| Config.1 recorder inspection | `configservice:DescribeConfigurationRecorders` | Check existing recorder before overwriting |
| Config.1 delivery check | `configservice:DescribeDeliveryChannels` | Check existing delivery channel before redirecting |
| S3.5 policy merge | `s3:GetBucketPolicy` | Read existing policy for merge |

> ❓ **Needs verification:** Confirm current read role (`upload_read_role_template.py`) includes or can be extended with these permissions before implementation begins.

---

## Part 6: Verification Gaps — All Resolved ✅

**All 5 open questions answered on 2026-03-03.**

| # | Question | Answer | Impact on Plan |
|---|---|---|---|
| 1 | Does runtime check capture existing policy for S3.5? | **No.** `remediation_runtime_checks.py` line 380+441 captures only `s3_policy_analysis_possible` (readability flag). Full policy JSON capture is S3.2-only. | S3.5 fix now requires adding policy capture to `remediation_runtime_checks.py` first, then bundle merge. Two-step implementation. |
| 2 | Does `execute_delete` check root MFA enrollment? | **No.** Gates on window_clean, active-key presence, feature flags, and self-cutoff only (lines 295, 603). No MFA check anywhere in the delete path. | IAM.4 MFA gate is confirmed fully absent. Must be added to `execute_delete` preflight and/or strategy validation. |
| 3 | Should EC2.53 CF path also revoke public rules? | **Yes — parity required.** CF-additive-only is operationally incomplete (noncompliant public rules remain). Decision: ship fail-closed manual-revoke checklist first; upgrade to Lambda revoke for full parity in a follow-on. | EC2.53 near-term item added to rollout plan (item 4). |
| 4 | Has S3.9 self-referencing log bundle been applied to any customer account? | **Test apply found, no customer impact.** Artifact evidence shows a self-referencing apply on 2026-02-20 (`terraform_transcript.json` line 23, `stage5_result.json` line 11), but live DB snapshot shows 0 S3.9 remediation runs. Impact is test/script-only; no customer cost exposure confirmed. | No retroactive notification needed. Fix still required pre-launch. |
| 5 | Has S3.1 CF no-op been used by any production tenant? | **No.** DB shows 0 S3.1 remediation runs; all recorded bundle formats are Terraform. CF path has not been exercised in production. | No retroactive notification needed. Fix required before any customer accesses the CF path. |
