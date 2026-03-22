# Remediation Safety — Implementation Task List
**Source:** remediation-safety-complete-plan.md | **Date:** 2026-03-03

Tasks are grouped into **Immediate** (P0, block launch) and **Near-term** (P1, current sprint).
Live tests appear after every 2–3 tasks to validate as you go.

---

## IMMEDIATE — Must ship before any customer onboarding

---

### Task 1: S3.1 — Fix CloudFormation No-Op Bundle

**What to do:**
Replace the `WaitConditionHandle` placeholder in `_cloudformation_s3_content()` with a Lambda Custom Resource that calls `s3control:PutPublicAccessBlock` with all four flags set to `true`.

**Files to change:**
- `backend/services/pr_bundle.py` → `_cloudformation_s3_content()` (line 869)

**Pattern to follow:** Same Lambda custom resource pattern already used in:
- SSM.7 CF bundle: `_cloudformation_ssm_block_public_sharing_content()` (line 2733)
- EC2.7 CF bundle: `_cloudformation_ebs_default_encryption_content()` (line 2836)

**Lambda role permissions needed:** `s3control:PutPublicAccessBlock`

**Unit tests:**
- Generate CF bundle for `s3_block_public_access` action → assert output contains no `WaitConditionHandle`
- Assert output contains `AWS::Lambda::Function` and `Custom::` resource type
- Assert Lambda code calls `s3control.put_public_access_block` with `BlockPublicAcls=True, IgnorePublicAcls=True, BlockPublicPolicy=True, RestrictPublicBuckets=True`
- Assert `Delete` RequestType in Lambda returns SUCCESS without mutation (idempotent delete)

---

### Task 2: EC2.53 — Make Revoke Opt-In + Add CF Fail-Closed Checklist

**What to do (Terraform path):**
In `_terraform_sg_restrict_content()`, wrap the `null_resource.revoke_public_admin_ingress` block so it only executes when a new variable `remove_existing_public_rules` is set to `true`. Default must be `false`.

**What to do (CloudFormation path):**
In `_cloudformation_sg_restrict_content()`, add a `Metadata` note and a top-of-file step explicitly stating the customer MUST manually revoke `0.0.0.0/0` rules on ports 22/3389. Add a warning that the stack only adds restricted rules; it does not remove existing public ones.

**Files to change:**
- `backend/services/pr_bundle.py` → `_terraform_sg_restrict_content()` (line 1933)
- `backend/services/pr_bundle.py` → `_cloudformation_sg_restrict_content()` (line 2039)
- Bundle steps list for both formats → add "IMPORTANT: review `remove_existing_public_rules` variable before applying"

**Unit tests:**
- Generate Terraform bundle → assert `remove_existing_public_rules` variable exists with `default = false`
- Generate Terraform bundle → assert the `null_resource` block is conditional on `var.remove_existing_public_rules == true`
- Generate CF bundle → assert `Metadata` section contains language about manual revoke requirement
- Generate CF bundle → assert no `RevokeSecurityGroupIngress` API calls in the template (CF path should not auto-revoke)

---

### 🔴 Live Test A — After Tasks 1 & 2

**Scope:** S3.1 CF bundle + EC2.53 Terraform bundle

**Tests to run:**

| # | Test | Pass condition |
|---|---|---|
| A1 | Deploy S3.1 CF stack to a real test account | Stack reaches CREATE_COMPLETE; verify `aws s3control get-public-access-block` returns all 4 flags `true` |
| A2 | Deploy S3.1 CF stack and then delete it | Stack deletes cleanly; `get-public-access-block` may or may not revert (Lambda Delete handler returns SUCCESS without mutating) |
| A3 | Generate EC2.53 Terraform bundle (default settings); run `terraform plan` against a group with `0.0.0.0/0` on port 22 | Plan shows **zero** revocations; only additions of restricted rules |
| A4 | Generate EC2.53 Terraform bundle with `remove_existing_public_rules = true`; run `terraform plan` | Plan shows revocation of `0.0.0.0/0` rule and addition of restricted rule |
| A5 | Deploy EC2.53 CF bundle to a group with `0.0.0.0/0` on port 22 | Stack succeeds; public rule still present (CF path is additive); README warns about manual revoke |

---

### Task 3: IAM.4 — Add MFA Preflight Gate to Delete Path

> ✅ Status: Implemented on 2026-03-03 (runtime probe + API strategy hard-block + worker delete hard-stop + UI gate messaging)

**What to do:**
1. In `remediation_runtime_checks.py`, add a probe for `iam_root_access_key_absent` action type + `iam_root_key_delete` strategy: call `iam:GetAccountSummaryReport` and check `AccountMFAEnabled`. If `0`, return a hard block.
2. In `root_key_remediation_executor_worker.py` `execute_delete()` (line 295), add a guard before proceeding: call the new MFA probe and raise `_mark_needs_attention` with reason `root_mfa_not_enrolled` if MFA is not enrolled.
3. In `remediation_strategy.py`, promote the existing warning for `iam_root_key_delete` to include: *"Root MFA must be active before this path is selectable."*

**Files to change:**
- `backend/services/remediation_runtime_checks.py` → add `probe_root_mfa_enrolled()` or extend `probe_direct_fix_permissions()`
- `backend/services/root_key_remediation_executor_worker.py` → `execute_delete()` (line 295)
- `backend/services/remediation_strategy.py` → `iam_root_key_delete` warnings (line 449)
- Frontend: UI strategy selection for `iam_root_key_delete` must surface gate message if MFA probe fails

**Required permission:** `iam:GetAccountSummaryReport` must be present in the platform read role (`upload_read_role_template.py`)

**Unit tests:**
- Mock `GetAccountSummaryReport` → `AccountMFAEnabled = 0` → assert strategy selection returns hard error (not warning)
- Mock `GetAccountSummaryReport` → `AccountMFAEnabled = 1` → assert strategy selection proceeds normally
- `execute_delete()` with mock MFA=0 → assert transitions to `needs_attention` with reason `root_mfa_not_enrolled`
- `execute_delete()` with mock MFA=1 and no active keys → assert normal delete flow continues

---

### 🔴 Live Test B — After Task 3

**Scope:** IAM.4 MFA gate

**Status:** Completed on 2026-03-03.
**Evidence:** `docs/audit-remediation/evidence/phase2-live-test-b-20260303T175808Z/`
**Result summary:** `B1 PASS`, `B2 PASS`, `B3 PASS`.

| # | Test | Pass condition |
|---|---|---|
| B1 | Attempt to select `iam_root_key_delete` strategy on a test account with **root MFA disabled** | Hard gate blocks selection; error message shown |
| B2 | Attempt to select `iam_root_key_delete` on test account with **root MFA enabled** | Strategy is selectable; proceeds to bundle generation |
| B3 | Simulate `execute_delete()` in worker with MFA=0 injected | Run transitions to `needs_attention`; not deleted |

---

## NEAR-TERM — Current sprint

---

### Task 4: EC2.53 CF — Full Revoke Parity (Lambda Custom Resource)

**What to do:**
Add a Lambda Custom Resource to the EC2.53 CloudFormation bundle that calls `ec2:RevokeSecurityGroupIngress` for `0.0.0.0/0` and `::/0` on ports 22 and 3389 before the ingress rules are added. This replaces the manual-revoke checklist from Task 2 with full automation parity.

**Dependency:** Task 2 must ship first. This is the follow-on that achieves full CF/Terraform parity.

**Files to change:**
- `backend/services/pr_bundle.py` → `_cloudformation_sg_restrict_content()` (line 2039)

**Lambda permissions needed:** `ec2:RevokeSecurityGroupIngress`, `ec2:DescribeSecurityGroupRules`

**Unit tests:**
- Generate CF bundle → assert `AWS::Lambda::Function` present with revoke logic
- Assert Lambda calls `revoke_security_group_ingress` for `0.0.0.0/0` on 22 and 3389
- Assert Lambda Delete handler is a no-op (does not re-add public rules on stack delete)
- Assert ingress resources have `DependsOn` pointing to the custom resource (revoke happens first)

---

### Task 5: CloudTrail.1 — Add Required S3 Bucket Policy to Bundle

> ✅ Status: Implemented on 2026-03-03 (Terraform + CloudFormation required CloudTrail bucket policy statements, `create_bucket_policy` default-true toggle, and opt-out tests).

**What to do:**
Add the CloudTrail-required S3 bucket policy to both Terraform and CloudFormation CloudTrail bundles. The policy needs two statements:
- `s3:GetBucketAcl` for `cloudtrail.amazonaws.com` on the bucket
- `s3:PutObject` for `cloudtrail.amazonaws.com` on `AWSLogs/<account-id>/CloudTrail/*` with condition `s3:x-amz-acl: bucket-owner-full-control`

**Files to change:**
- `backend/services/pr_bundle.py` → `_terraform_cloudtrail_content()` (line 2183): add `aws_s3_bucket_policy.cloudtrail_delivery` resource
- `backend/services/pr_bundle.py` → `_cloudformation_cloudtrail_content()` (line 2206): add `AWS::S3::BucketPolicy` resource
- Add a variable/parameter `create_bucket_policy = true` (default true) so customers using a pre-existing policy-managed bucket can opt out

**Unit tests:**
- Generate Terraform bundle → assert `aws_s3_bucket_policy` resource present
- Assert policy JSON contains `cloudtrail.amazonaws.com` as principal
- Assert policy contains `s3:PutObject` on `AWSLogs/*/CloudTrail/*`
- Generate CF bundle → assert `AWS::S3::BucketPolicy` resource present with same statements
- Assert `create_bucket_policy = false` generates bundle without the policy resource

---

### Task 6: S3.5 — Two-Step Policy Capture + Merge

> ✅ Status: Step 6a implemented on 2026-03-03; Step 6b implemented on 2026-03-04 and validated by Live Test C rerun (`C1`–`C5` all pass).

**Step 6a (remediation_runtime_checks.py — do first):**
Add bucket policy JSON capture for the `s3_bucket_require_ssl` action type in `collect_runtime_risk_signals()`. Follow the exact same pattern as S3.2 (captures `existing_bucket_policy_json` and `existing_bucket_policy_statement_count` into risk evidence). Key lines to reference: `remediation_runtime_checks.py` line 380 (S3.5 current probe), line 441 (S3.2 policy capture pattern).

**Step 6b (pr_bundle.py — after 6a):**
Implemented policy-preserving merge behavior and fail-closed enforcement:
- S3.5 Terraform bundle now merges policies via `aws_iam_policy_document` (`source_policy_documents` + `override_policy_documents`) and writes preserved baseline policy JSON into `terraform.auto.tfvars.json` when runtime evidence includes existing statements.
- S3.5 CloudFormation bundle now uses a Lambda-backed `Custom::S3SslPolicyMerge` resource that fetches/merges existing bucket policy statements instead of replacing policy via `AWS::S3::BucketPolicy`.
- Generation now fails closed with `bucket_policy_preservation_evidence_missing` when `existing_bucket_policy_statement_count > 0` but preservation JSON evidence is missing.
- Runtime `risk_snapshot` evidence is now passed into S3.5 bundle generation so preservation checks are enforced during build time.

**Required permission:** `s3:GetBucketPolicy` in read role

**Unit tests (Step 6a):**
- Mock `s3:GetBucketPolicy` returning a policy with 2 statements → assert risk evidence contains `existing_bucket_policy_json` and `existing_bucket_policy_statement_count = 2`
- Mock `s3:GetBucketPolicy` → NoSuchBucketPolicy → assert `existing_bucket_policy_statement_count = 0`
- Mock `s3:GetBucketPolicy` → AccessDenied → assert probe marks path as unavailable (does not hard-block)

**Unit tests (Step 6b):**
- Generate Terraform bundle with risk evidence containing 2-statement policy → assert `terraform.auto.tfvars.json` present with `existing_bucket_policy_json`
- Generate Terraform bundle with `existing_bucket_policy_statement_count = 0` → assert no tfvars file (no policy to preserve)
- Generate Terraform bundle with `existing_bucket_policy_statement_count = 2` but no JSON → assert `bucket_policy_preservation_evidence_missing` error raised
- Apply Terraform against bucket with existing Deny statement → assert Deny statement still present in final policy

---

### 🔴 Live Test C — After Tasks 5 & 6

**Scope:** CloudTrail.1 bucket policy + S3.5 policy merge

**Status:** Completed with final rerun pass on 2026-03-04.
**Evidence (final):** `docs/audit-remediation/evidence/phase2-live-test-c-20260303T234636Z/`
**Evidence (initial failing run):** `docs/audit-remediation/evidence/phase2-live-test-c-20260303T224523Z/`
**Result summary (final):** `C1 PASS`, `C2 PASS`, `C3 PASS`, `C4 PASS`, `C5 PASS`.

| # | Test | Pass condition |
|---|---|---|
| C1 | Apply CloudTrail Terraform bundle to a test account; trail bucket created fresh | `aws cloudtrail get-trail-status` shows `IsLogging: true`, no S3 delivery errors after ~5 min |
| C2 | Apply CloudTrail bundle pointing to an existing bucket with a pre-existing policy | Existing policy is supplemented (not replaced); CloudTrail delivery still works |
| C3 | Apply S3.5 Terraform bundle to a bucket with an existing Deny statement | `aws s3api get-bucket-policy` shows both the original Deny AND the new SSL-deny statement |
| C4 | Apply S3.5 bundle to a bucket with no prior policy | SSL-deny statement is the only statement; no error |
| C5 | Attempt to generate S3.5 bundle when `existing_bucket_policy_statement_count = 2` but no JSON | Bundle generation fails with `bucket_policy_preservation_evidence_missing` error |

---

### Task 7: Config.1 — Pre-Flight Recorder Inspection

**Status:** ✅ Implemented (2026-03-04)

**Implemented behavior:**
1. Terraform Config bundle now probes existing recorder state and defaults to preserving existing recorder scope via `overwrite_recording_group = false`.
2. Existing recorder name is reused when present; overwrite path remains explicit opt-in.
3. Delivery-channel preflight now inspects current channel bucket and emits mismatch warning text; README includes a Config.1 preflight safeguards section with the warning behavior.
4. Local delivery bucket policy path now reads existing policy and merges required AWS Config statements before `put-bucket-policy`.
5. Read-role permission sources were updated to include:
   - `config:DescribeConfigurationRecorders` (AWS CLI operation: `configservice:DescribeConfigurationRecorders`)
   - `config:DescribeDeliveryChannels` (AWS CLI operation: `configservice:DescribeDeliveryChannels`)

**Validation added:**
- selective recorder mode preservation by default
- recorder-name reuse behavior
- delivery-channel mismatch warning surfaced in README
- merged policy-write behavior (merge preflight + merged write payload)

---

### Task 8: S3.11 — Fix CloudFormation Lifecycle Bundle

> ✅ Status: Implemented on 2026-03-04 (CloudFormation S3.11 now uses Lambda custom resource with `PutLifecycleConfiguration` create/update and delete no-op).

**What to do:**
Replace `AWS::S3::Bucket` in `_cloudformation_s3_bucket_lifecycle_configuration_content()` with a Lambda Custom Resource that calls `s3:PutLifecycleConfiguration` on the existing bucket. The resource type `AWS::S3::Bucket` cannot safely target pre-existing buckets managed outside CloudFormation.

**Files to change:**
- `backend/services/pr_bundle.py` → `_cloudformation_s3_bucket_lifecycle_configuration_content()` (line 1723)

**Pattern to follow:** Same as SSM.7 CF bundle (`_cloudformation_ssm_block_public_sharing_content()`, line 2733)

**Lambda code must:**
- On `Create`/`Update`: call `s3:PutLifecycleConfiguration` with `AbortIncompleteMultipartUpload` rule, status `Enabled`
- On `Delete`: no mutation (leave lifecycle config in place; deleting it is not part of remediation rollback)

**Lambda permissions:** `s3:PutLifecycleConfiguration`, `s3:GetLifecycleConfiguration`

**Unit tests:**
- Generate CF bundle → assert `AWS::S3::Bucket` is NOT in the output
- Assert `AWS::Lambda::Function` present with `PutLifecycleConfiguration` call
- Assert Delete handler is a no-op
- Simulate CF deploy against pre-existing bucket → no `ROLLBACK` or bucket deletion

---

### Task 9: S3.9 — Fix Self-Referencing Log Bucket Default

> ✅ Status: Implemented on 2026-03-04 (`S3.9` now fails closed unless `strategy_inputs.log_bucket_name` is set to a dedicated bucket).

**What to do:**
In both Terraform and CloudFormation S3.9 generators:
1. Change `log_bucket_name`/`LogBucketName` default from `{bucket}` to `REPLACE_LOG_BUCKET_NAME` when no override is provided
2. Add `REPLACE_LOG_BUCKET_NAME` as the explicit placeholder when bucket cannot be defaulted
3. Add `REPLACE_LOG_BUCKET_NAME` to `_BLOCKED_PLACEHOLDER_TOKENS` in `pr_bundle.py` (line 137) so bundle generation fails if log bucket is not provided
4. Add step to bundle instructions: *"Do not use the source bucket as the log destination. Specify a dedicated logging bucket."*

**Files to change:**
- `backend/services/pr_bundle.py` → `_terraform_s3_bucket_access_logging_content()` (line 1583): change `log_bucket_name` default
- `backend/services/pr_bundle.py` → `_cloudformation_s3_bucket_access_logging_content()` (line 1617): change `LogBucketName` default
- `backend/services/pr_bundle.py` → `_BLOCKED_PLACEHOLDER_TOKENS` (line 137): add `"REPLACE_LOG_BUCKET_NAME"`

**Unit tests:**
- Generate S3.9 Terraform bundle → assert `log_bucket_name` default is NOT equal to source bucket name
- Generate bundle without providing a log bucket → assert `PRBundleGenerationError` with code `unresolved_placeholder_token`
- Generate bundle WITH a valid log bucket override → assert bundle generates cleanly
- Assert blocked placeholder check catches `REPLACE_LOG_BUCKET_NAME` in the same way it catches `REPLACE_BUCKET_NAME`

---

### 🔴 Live Test D — After Tasks 7, 8 & 9

**Status:** Completed on 2026-03-04.
**Evidence:** `docs/audit-remediation/evidence/phase2-live-test-d-20260304T013004Z/`
**Result summary:** `D1 PASS`, `D2 PASS`, `D3 PASS`, `D4 PASS`, `D5 PASS`.
**Rerun (D1/D2 only after Config.1 robustness patch):** Completed on 2026-03-04.
**Rerun evidence:** `docs/audit-remediation/evidence/phase2-live-test-d-rerun-d1d2-20260304T021949Z/`
**Rerun summary:** `D1 PASS`, `D2 PASS`, `D1a (centralized unreachable-bucket fail-closed check) PASS`.

**Scope:** Config.1 + S3.11 CF + S3.9

| # | Test | Pass condition |
|---|---|---|
| D1 | Apply Config.1 bundle to a test account that already has a running selective recorder | Recorder name is reused; `recordingGroup` is unchanged; no `allSupported` overwrite |
| D2 | Apply Config.1 bundle to a fresh account (no existing recorder) | Recorder created with `allSupported: true`; delivery channel created; recording starts |
| D3 | Deploy S3.11 CF bundle against a pre-existing unmanaged bucket | Stack reaches CREATE_COMPLETE; no bucket deletion or failure; `GetLifecycleConfiguration` shows rule applied |
| D4 | Attempt to generate S3.9 bundle without providing a log bucket | Bundle generation fails with `unresolved_placeholder_token` error |
| D5 | Generate S3.9 bundle with a valid separate log bucket; apply it | `GetBucketLogging` on source bucket shows `TargetBucket` = the separate log bucket, not itself |

---

## POST-LAUNCH — Communication & Access Guidance

---

### Task 10: Add Post-Fix Access Guidance to Bundle READMEs

**Status:** Completed on 2026-03-04.
**Implementation:** `backend/services/pr_bundle.py` (`_maybe_append_terraform_readme()`, `_generate_for_s3_bucket_block_public_access()`, `_generate_for_sg_restrict_public_ports()`, `_generate_for_s3_bucket_require_ssl()`, `_generate_for_ssm_block_public_sharing()`)
**Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_step7_components.py -k "post_fix_access_guidance"` (`8 passed`)

Terraform README and CloudFormation instruction outputs now include the required post-fix sections (`what changes`, `how to access now`, `verify`, `rollback`) for these controls:

| Control | Implemented post-fix guidance |
|---|---|
| EC2.53 | SSM Session Manager access command (`aws ssm start-session`), SG-rule verification command, scoped ingress rollback command |
| S3.2 (block public) | CloudFront usage note for post-fix access path, block-public-access verification command, emergency rollback command |
| S3.5 (SSL enforcement) | Explicit HTTPS requirement, HTTPS/HTTP curl verification examples, bucket-policy rollback command |
| SSM.7 (block sharing) | Private-sharing guidance (`aws ssm modify-document-permission`), service-setting verification command, emergency rollback command |

---

### Task 11: Retroactive Verification Check (Backend Job)

**Status:** Completed on 2026-03-04.
**Implementation:** `scripts/check_s3_cf_noop_runs.py`
**Validation:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_check_s3_cf_noop_runs.py` (`2 passed`)

**What to do:**
Write a one-time script (or scheduled job) that:
1. Queries `remediation_runs` for records where `action_type = s3_block_public_access`, `format = cloudformation`, `status = completed`
2. For each match, update run status to `verification_required` and set a flag for UI banner display
3. Log results for PM review

**Note:** Per confirmed answers, current DB shows 0 such runs. But this job should exist before CF path is re-enabled so it auto-runs after any future CF applies.

**Files to create:**
- `scripts/check_s3_cf_noop_runs.py` — one-time audit script

**Tests:**
- Unit test with mock DB: 3 matching runs → assert all 3 updated to `verification_required`
- Unit test with no matching runs → assert no writes, script exits cleanly
- Do not run as a live test (no production impact confirmed; run in staging only)

---

## Dependency Order Summary

```
Task 1 (S3.1 CF)        ─┐
Task 2 (EC2.53 TF+CF)   ─┼──► Live Test A
                          |
Task 3 (IAM.4 MFA)      ─┼──► Live Test B

Task 4 (EC2.53 CF parity)   [depends on Task 2]
Task 5 (CloudTrail.1)    ─┐
Task 6a (S3.5 capture)   ─┤
Task 6b (S3.5 merge)     ─┼──► Live Test C  [6b depends on 6a]

Task 7 (Config.1)        ─┐
Task 8 (S3.11 CF)        ─┤
Task 9 (S3.9)            ─┼──► Live Test D

Task 10 (README guidance)    [no dependencies; can parallelize]
Task 11 (retroactive job)    [no dependencies; can parallelize]
```
