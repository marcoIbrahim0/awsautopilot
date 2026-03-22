# Remediation Safety Score Upgrade Plan: Path to 95-100

## 1. Executive Plan Overview
The goal is to elevate all automated and guided AWS security remediations to a 95-100 Safety Score (Low Risk). Currently, Terraform bundles run unsupervised on disparate customer machines without explicit IAM preflight checks, backend state locking, rollback artifacts, or target pinning. This introduces unacceptable risks of applying the wrong configuration to the wrong account, causing accidental lockouts, or destroying non-standard configurations.

This plan introduces a rigid Safety Framework built on two core principles:
1. **Never Assume:** Explictly probe dependencies, explicitly verify permissions, explicitly snapshot pre-state, and pin target execution (Account/Region).
2. **First-class Execution Failures:** Treat customer PC flakiness (interrupted terraform applies, version mismatches, wrong AWS_PROFILE) as critical failure vectors needing automated containment.

This is implemented via a **Platform-wide Safety Framework (A1-A8)** protecting the execution boundary, and **Control-Specific Upgrades** tailored to the unique blast radius of each of the 16 targeted remediations.

---

## 2. Platform-Wide Safety Framework (A1–A8)

### A1) Hard Targeting Guardrails (Wrong Account/Region Prevention)
- **Status (2026-02-24):** Implemented in `backend/services/pr_bundle.py` with `allowed_account_ids` enforced in all Terraform provider templates (`_terraform_s3_providers_content`, `_terraform_security_hub_providers_content`, `_terraform_guardduty_providers_content`, `_terraform_regional_providers_content`), with test coverage and Terraform mismatch validation captured.
- **Current State (pre-implementation baseline):** Providers were dynamically generated in `backend/services/pr_bundle.py` but relied on the customer's local `AWS_PROFILE` taking matching effect. README guidance existed, but there was no hard enforcement in provider blocks.
- **Design Proposal:** Use Terraform `allowed_account_ids` to force a fail-closed if the customer applies against the wrong AWS account.
- **Implementation:**
  - Update `_terraform_*_providers_content` in `pr_bundle.py` to inject `allowed_account_ids = ["{account_id}"]`.
- **Acceptance Criteria:** `terraform plan` fails instantly if executed under an incorrect AWS_PROFILE.
- **Test Plan:** Unit test the generated `providers.tf`. E2E test by attempting `terraform apply` with a disjoint account ID in the environment.

### A2) Terraform Execution Reliability
- **Current State:** Generates raw `.tf` files. No backend state tracking, no provider locking, no concurrency handling. State file is `.terraform.tfstate` on the customer's PC.
- **Design Proposal:** 
  1. Distribute a `.terraform.lock.hcl` with every bundle. 
  2. Implement an execution wrapper (e.g. `install.sh` or a local Go binary) that isolates the state or shifts to a lightweight "apply-only container" or temporary AWS-side state backend (S3+DynamoDB).
  3. Given SMB constraints, if local execution remains, we must append a pre-run script verifying `terraform version` and warning on partial state (`terraform state list`).
- **Implementation:**
  - Include a minimal wrapper script in the bundle: `run.sh` / `run.ps1` that wraps `terraform apply`, checks for interrupted state, and traps errors.
- **Test Plan:** E2E test simulating a SIGINT during `terraform apply` and verifying the script's recovery guidance.

### A3) Preflight Permission Probing
- **Status (2026-02-24):** Implemented for PR-bundle execution preflight. `STRATEGY_REGISTRY` now declares `required_permissions`, generated bundles include `required_permissions.json`, and backend execution fails closed with exact `missing_actions` when IAM simulation denies required actions.
- **Closure (2026-02-24):** ✅ Closed for current Phase 2 scope.
- **Current State (pre-implementation baseline):** None. Bundles assumed the executor had `AdministratorAccess` or sufficient privileges.
- **Design Proposal:** The backend pre-computes an IAM policy snippet required for the bundle. The UI exposes a "Check Permissions" button or the wrapper runs `aws iam simulate-principal-policy` against the executor's identity prior to `terraform plan`.
- **Implementation:**
  - Add standard IAM requirements into `STRATEGY_REGISTRY` in `remediation_strategy.py`.
- **Test Plan:** E2E test with a restricted IAM role; verify preflight fails cleanly with exact missing actions.

### A4) Dependency Validation Framework
- **Status (2026-02-24):** Closed — implemented for PR-bundle and direct-fix execution paths with fail-closed runtime probe gating.
- **Current State (pre-implementation baseline):** Findings analysis and strategy risk checks existed, but worker-time dependency probes were advisory and could not block bundle generation. `s3_block_public_access` included manual README dependency checklists.
- **Design Proposal:** Convert manual checklist guidance into executable preflight probes and block remediation when prerequisites fail.
- **Implementation:**
  - Added structured dependency preflight framework in `backend/workers/services/pr_bundle_preflight.py` returning `checks`, `failure_reasons`, `remediation_hints`, and `blocked` status.
  - Added reusable runtime probes for:
    - S3 account-level public dependency checks (`s3_block_public_access`)
    - S3 bucket website/public ACL dependency checks (`s3_bucket_block_public_access`)
    - S3 CloudFront/OAC origin dependency checks (`s3_bucket_block_public_access`)
    - S3 SSE-KMS key viability + `kms:GenerateDataKey` checks (`s3_bucket_encryption_kms`)
    - S3 SSL strict-deny policy dependency checks (`s3_bucket_require_ssl`)
    - SG + SSM access-path validation (`sg_restrict_public_ports`)
    - CloudTrail prerequisites (org trail overlap, log-bucket availability, existing logging status)
    - AWS Config prerequisites (recorder/channel inventory + centralized bucket reachability)
    - SSM public-sharing dependency checks (public document sharing detection)
  - Wired fail-closed gating into `backend/workers/jobs/remediation_run.py` for both direct-fix and PR-bundle paths:
    - Direct-fix runs now execute dependency preflight before `assume_role` and fail closed on blocked/uncertain checks.
    - Single/group PR-bundle flows continue to fail closed before bundle generation.
    - On preflight failure, run is marked `failed` before bundle generation.
    - Logs include explicit failure reasons and remediation hints.
    - Probe evidence is persisted to artifacts (`dependency_preflight` / `group_dependency_preflight`).
  - Added/updated tests:
    - `tests/test_pr_bundle_preflight.py`
    - `tests/test_remediation_run_worker.py`

### A5) Non-Destructive Change Strategy
- **Current State:** Remediations overwrite authoritative resources (e.g., `aws_s3_bucket_policy`).
- **Design Proposal:** Switch to additive methods or data-driven patching. For S3 bucket policies, the bundle must use an external data source or `aws_iam_policy_document` to merge the existing policy with the new Deny statements. Pre-change states must be dumped to a `.backup` directory by the wrapper script.
- **Implementation:** Replace raw `aws_s3_bucket_policy` overwrites with custom local execution wrappers or `null_resource` fetching the existing policy and appending to it.

### A6) Post-Apply Verification Contract
- **Status (2026-02-24):** ✅ Closed for current supported remediation controls (direct-fix + PR-bundle apply paths).
- **Implementation:**
  - Added A6 verification contract service:
    - `backend/services/remediation_verification.py`
  - Contract fields persisted at `remediation_runs.artifacts.post_apply_verification`:
    - `status`, `control_id`, `account_id`, `region`, `resource_id`, `check_name`, `expected`, `observed`, `verified_at`, `failure_reason`
  - Added run-level status marker:
    - `remediation_runs.artifacts.verification_status` (`applied_unverified` | `verified_closed`)
  - Added control-specific read-after-apply handlers for all currently supported non-manual remediation controls:
    - `s3_block_public_access` (`s3control.get_public_access_block`)
    - `enable_security_hub` (`securityhub.describe_hub`)
    - `enable_guardduty` (`guardduty.list_detectors/get_detector`)
    - `ebs_default_encryption` (`ec2.get_ebs_encryption_by_default`, optional KMS key check)
    - `s3_bucket_block_public_access` (`s3.get_public_access_block`)
    - `s3_bucket_encryption` (`s3.get_bucket_encryption`)
    - `s3_bucket_access_logging` (`s3.get_bucket_logging`)
    - `s3_bucket_lifecycle_configuration` (`s3.get_bucket_lifecycle_configuration`)
    - `s3_bucket_encryption_kms` (`s3.get_bucket_encryption`)
    - `s3_bucket_require_ssl` (`s3.get_bucket_policy`)
    - `sg_restrict_public_ports` (`ec2.describe_security_groups`)
    - `cloudtrail_enabled` (`cloudtrail.describe_trails/get_trail_status`)
    - `aws_config_enabled` (`config.describe_configuration_recorders/status/delivery_channels`)
    - `ssm_block_public_sharing` (`ssm.get_service_setting`)
    - `ebs_snapshot_block_public_access` (`ec2.get_snapshot_block_public_access_state`, strategy-aware expected state)
  - Wired verification outcome handling into workers:
    - `backend/workers/jobs/remediation_run.py` (direct-fix apply)
    - `backend/workers/jobs/remediation_run_execution.py` (SaaS apply)
  - Verification outcomes now update state:
    - `verified_closed`: action set to `resolved`; linked findings set `RESOLVED` with `resolved_at` when loaded
    - `applied_unverified`: action transitions from `open` to `in_progress`; finding close is deferred
  - Added API-visible fields for frontend rendering:
    - `verification_status`
    - `post_apply_verification`
    - surfaced by `backend/routers/remediation_runs.py` list/detail serializers
- **Added/updated tests:**
  - `tests/test_remediation_verification.py`
  - `tests/test_remediation_run_worker.py`
  - `tests/test_remediation_run_execution.py`
  - `tests/test_remediation_runs_api.py`

### A7) Rollback Playbooks + Containment
- **Status (2026-02-24):** Implemented.
- **Closure (2026-02-24):** ✅ Closed for current PR-bundle execution scope.
- **Implementation:**
  - Added rollback artifact generator:
    - `backend/workers/services/rollback_playbooks.py`
  - Every generated PR bundle action now includes rollback artifacts:
    - `rollback/rollback-metadata.json`
    - `rollback/rollback_tool.py`
    - `rollback.sh`
    - `rollback.ps1`
  - Single-action bundle execution now always uses wrapper scripts and captures pre-state before apply:
    - `run.sh` delegates to `run_bundle.sh`
    - `run_bundle.sh` runs rollback-tool capture before `terraform init/plan/apply`
    - backup capture failure is fail-closed (`exit 42`) before any apply operation
  - Group bundle execution now enforces backup capture per action folder before apply:
    - `run_all.sh` path enforces `capture_prestate_backup` fail-closed gating
    - reporting wrapper path (`run_all.sh` + `run_actions.sh`) captures all action backups before delegating to runner
  - Captured pre-state snapshots are written to a predictable folder structure:
    - `rollback/pre-state/<timestamp-run-id>/`
    - includes `backup-manifest.json`
    - latest pointer tracked in `rollback/latest-backup-dir.txt`
  - Rollback execution is control-aware and idempotent where possible:
    - restore logic keyed by `action_type` with targeted AWS CLI restore calls
    - duplicate/not-found API errors are treated as idempotent no-op where safe
- **Added/updated tests:**
  - `tests/test_remediation_run_worker.py`
    - `test_pr_only_bundle_includes_rollback_artifacts_and_backup_fail_closed_gate`
    - `test_pr_only_group_bundle_generates_single_combined_bundle` (backup/rollback assertions)
    - `test_group_bundle_runner_template_uses_s3_when_configured` (central template wrapper path assertions)

### A8) Structured Impact + Audit Logging
- **Status (2026-02-24):** Implemented.
- **Closure (2026-02-24):** ✅ Closed for current Phase 2 scope.
- **Implementation:**
  - Added `POST /api/v1/telemetry/remediation` ingestion endpoint (`backend/routers/remediation_telemetry.py`) with signed token validation + run/action/account consistency checks.
  - Added `remediation_telemetry_events` persistence model + migration:
    - `backend/models/remediation_telemetry_event.py`
    - `alembic/versions/0035_remediation_telemetry_events.py`
  - Added telemetry token issue/verify service:
    - `backend/services/remediation_telemetry_tokens.py`
  - Added telemetry integration points:
    - run creation embeds `artifacts.telemetry` callback/token payloads for PR-only runs (`backend/routers/remediation_runs.py`, `backend/routers/action_groups.py`)
    - downloaded wrappers emit structured lifecycle events (`run_started`, `precheck_completed`, `apply_started`, `apply_finished`, `verification_finished`, `verification-result-link`, `run_succeeded`/`run_failed`) (`backend/workers/jobs/remediation_run.py`)
    - wrapper emission includes timeout/retry controls and replay fallback (`TELEMETRY_TIMEOUT_SECONDS`, `TELEMETRY_MAX_ATTEMPTS`, `TELEMETRY_RETRY_DELAY_SECONDS`)
    - wrappers auto-replay saved telemetry payloads (`telemetry-*.json`) on subsequent runs and remove successfully replayed files
    - wrapper summaries/error payloads redact secret-like fields before callback/replay persistence
    - SaaS execution worker emits start/result/summary/stop events (`backend/workers/jobs/remediation_run_execution.py`)
- **Endpoint request contract:**
  - Required: `token`, `event_type`, `phase`, `status`
  - Optional: `timestamp`, `verification_state`, `error_class`, `error_message`, `bundle_id`, `bundle_run_id`, `remediation_run_id`, `summary`, `source`
- **Persisted telemetry fields (audit/troubleshooting):**
  - Context: `tenant_id`, `remediation_run_id`, `action_id`, `account_id`, `action_type`, `control_id`
  - Lifecycle: `event_type`, `phase`, `status`, `verification_state`
  - Diagnostics: `error_class`, `error_message`, `summary`
  - Correlation: `bundle_id`, `bundle_run_id`, `token_jti`
  - Timing: `occurred_at`, `created_at`, `updated_at`
- **Added/updated tests:**
  - `tests/test_remediation_telemetry_api.py` (auth + validation + persistence)
  - `tests/test_remediation_telemetry_tokens.py` (issue/verify token service)
  - `tests/test_remediation_runs_api.py` (telemetry artifact presence on PR run creation)
  - `tests/test_remediation_wrapper_telemetry.py` (wrapper payload schema + success/failure/retry emission behavior)
  - `tests/test_remediation_run_worker.py` / `tests/test_remediation_run_execution.py` (wrapper/execution integration stability)
- See also:
  - `docs/architecture/remediation-safety-model.md#remediation-telemetry-a8`
  - `docs/architecture/audit-semantics.md#remediation-telemetry-events-a8`

---

## 3. Control-Specific Upgrades (The 16 Controls)

## 3. Control-Specific Upgrades

### S3.1 Account-level Public Access Block
- **Why it is below 95-100 (Root Cause):** Applying blindly at the account level can break public websites/assets instantly.
- **Required Changes:** E2E explicit preflight checks verifying zero public traffic dependencies.
- **Mandatory Preflight Checks:** Scan all buckets in the account for `WebsiteConfiguration`, CloudFront connections, or public ACLs.
- **Mandatory Gating:** Manual approval required.
- **Post-Apply Verification:** Read `aws s3control get-public-access-block` for account ID.
- **Rollback Playbook:** Store pre-state JSON. Revert with `aws s3control put-public-access-block` payload.
- **Test Cases:** E2E test with a pre-existing public bucket website to ensure preflight aborts application without approval.
- **Expected Residual Risk:** Low (if approval explicitly gathered).

**Implementation update (2026-02-24):**
- Strategies are now mandatory for `s3_block_public_access`:
  - `s3_account_block_public_access_direct_fix`
  - `s3_account_block_public_access_pr_bundle`
  - `s3_account_keep_public_exception`
- Worker dependency preflight is fail-closed and blocks execution when any account-wide dependency scan is uncertain or unsafe.
- Account preflight checks now include:
  - bucket inventory read (`s3_account_bucket_inventory`)
  - website dependency scan (`s3_account_website_dependency`)
  - public ACL dependency scan (`s3_account_public_acl_dependency`)
  - CloudFront S3 origins without OAC (`s3_account_cloudfront_oac_dependency`)
- Risk snapshot always includes a manual-approval warning, and rejects when dependency scans fail or detect unsafe dependencies.

### S3.2 Bucket-level Public Access Block
- **Why it is below 95-100 (Root Cause):** Can break intentional public delivery on the target bucket.
- **Required Changes:** Restrict execution only if dependencies are mapped and mitigated via CloudFront OAC.
- **Mandatory Preflight Checks:** Check bucket `WebsiteConfiguration`, check for CloudFront OAC.
- **Mandatory Gating:** Manual approval required.
- **Post-Apply Verification:** Read `aws s3api get-public-access-block` on the bucket.
- **Rollback Playbook:** Store pre-state JSON. Revert via API with previous payload.
- **Test Cases:** Run against a bucket actively serving public CloudFront traffic without OAC.
- **Expected Residual Risk:** Low.

**Implementation update (2026-02-24):**
- Bucket preflight now includes explicit CloudFront/OAC dependency enforcement:
  - `s3_cloudfront_oac_dependency`
- `s3_bucket_block_public_access_standard` now fails closed when the target bucket is referenced by CloudFront origins without OAC.
- `s3_migrate_cloudfront_oac_private` remains allowed for no-OAC origins, but still requires explicit risk acknowledgement.
- Any dependency-scan uncertainty (for example CloudFront listing errors) blocks execution.

### S3.4 S3 Bucket Encryption (SSE-S3)
- **Why it is below 95-100 (Root Cause):** Overwrites authoritative bucket configuration, erasing any pre-existing custom settings unintentionally.
- **Required Changes:** Data-driven patching to retain other unrelated settings.
- **Mandatory Preflight Checks:** Validate bucket exists.
- **Mandatory Gating:** Auto-run allowed.
- **Post-Apply Verification:** Read `aws s3api get-bucket-encryption`.
- **Rollback Playbook:** Remove default encryption if none existed previously.
- **Test Cases:** Test against unencrypted bucket; test against bucket with different encryption.
- **Expected Residual Risk:** Almost Zero.

### S3.5 S3 Bucket SSL Enforcement (Bucket Policy)
- **Why it is below 95-100 (Root Cause):** Terraform overwrites the whole bucket policy, dropping vital existing statements.
- **Required Changes:** Implement safe policy patch/merge using a local script and `aws_iam_policy_document`.
- **Mandatory Preflight Checks:** Read existing policy. Validate existing policy size limits.
- **Mandatory Gating:** Manual approval required (due to potential for legacy non-SSL disruption).
- **Post-Apply Verification:** Read and lint the merged bucket policy over the API.
- **Rollback Playbook:** Store previous JSON policy. Revert with `aws s3api put-bucket-policy`.
- **Test Cases:** E2E test merging SSL enforcement into a sprawling 15KB bucket policy.
- **Expected Residual Risk:** Very Low.

### S3.9 S3 Bucket Access Logging
- **Why it is below 95-100 (Root Cause):** Log destination bucket might not exist or lack ACLs/permissions for the logging service principal.
- **Required Changes:** Validate destination bucket viability before apply.
- **Mandatory Preflight Checks:** Probe target sink bucket existence and `s3:PutObject` grants.
- **Mandatory Gating:** Auto-run allowed.
- **Post-Apply Verification:** Verify bucket logging status API.
- **Rollback Playbook:** Disable logging object on the source bucket.
- **Test Cases:** Configure with a nonexistent sink bucket -> ensure preflight failure.
- **Expected Residual Risk:** Almost Zero.

### S3.11 S3 Lifecycle Optimization (Abort Incomplete Multipart)
- **Why it is below 95-100 (Root Cause):** Overwriting existing lifecycle configurations destructively deletes user-defined transitions/expirations.
- **Required Changes:** Fetch current configurations, append new abort incomplete multipart rule.
- **Mandatory Preflight Checks:** Read existing `aws s3api get-bucket-lifecycle-configuration`.
- **Mandatory Gating:** Auto-run allowed.
- **Post-Apply Verification:** `get-bucket-lifecycle-configuration` contains the appended rule.
- **Rollback Playbook:** Dump old lifecycle JSON and re-apply on rollback.
- **Test Cases:** Merge with an existing complex 5-rule lifecycle.
- **Expected Residual Risk:** Almost Zero.

### S3.15 S3 Bucket KMS Encryption (SSE-KMS)
- **Why it is below 95-100 (Root Cause):** KMS misconfiguration results in permanent lockout/unreadability.
- **Required Changes:** Probe KMS key policies before applying encryption.
- **Mandatory Preflight Checks:** Probe `kms:GenerateDataKey`.
- **Mandatory Gating:** Manual approval required.
- **Post-Apply Verification:** Read `aws s3api get-bucket-encryption`.
- **Rollback Playbook:** Revert back to SSE-S3 or None depending on pre-state.
- **Test Cases:** Provide a restricted KMS key that denies use by the bucket, verify preflight fails.
- **Expected Residual Risk:** Low.

**Implementation update (2026-02-24):**
- Strategies are now mandatory for `s3_bucket_encryption_kms`:
  - `s3_bucket_encryption_kms_standard`
  - `s3_bucket_encryption_kms_keep_exception`
- Worker preflight now enforces fail-closed KMS viability checks:
  - bucket reachability (`s3_kms_bucket_reachable`)
  - key metadata viability (`s3_kms_key_viable`)
  - key-usage permission probe (`s3_kms_generate_data_key_permission`)
- `kms:GenerateDataKey` is now part of required permissions for this remediation path.
- API risk snapshots include mandatory manual-approval gating and block execution on failed KMS viability or permission probes.

### EC2.7 EBS Default Encryption
- **Why it is below 95-100 (Root Cause):** Custom KMS key requires robust cross-account and role IAM key policy grants, or new EC2s fail to launch.
- **Required Changes:** Differentiate between AWS Managed Key (safe) and Customer Managed Key (risky).
- **Mandatory Preflight Checks:** Probe `kms:CreateGrant` on the chosen key.
- **Mandatory Gating:** Managed Key: Auto-run. Custom KMS: Manual approval.
- **Post-Apply Verification:** Check `aws ec2 get-ebs-encryption-by-default`.
- **Rollback Playbook:** `aws ec2 disable-ebs-encryption-by-default` or restore previous key.
- **Test Cases:** Custom KMS key without appropriate grants. E2E test launching an instance post-apply.
- **Expected Residual Risk:** Low.

### EC2.53 Security Group Hardening (Remove 0.0.0.0/0 on 22/3389)
- **Why it is below 95-100 (Root Cause):** Removing admin access removes the ability to fix broken systems (admin lockout).
- **Required Changes:** Preflight check if SSM Session Manager is functional on the resources using this SG.
- **Mandatory Preflight Checks:** Validate SSM agent activity on attached ENIs.
- **Mandatory Gating:** Staged rollout / Manual approval.
- **Post-Apply Verification:** Read SG ingress rules via API.
- **Rollback Playbook:** Re-inject exactly the same CIDR blocks that were removed via API from dumped JSON.
- **Test Cases:** EC2 instance without SSM Session Manager attached to SG. Ensure explicit warning.
- **Expected Residual Risk:** Medium-Low.

### EC2.182 EBS Snapshot Public Block
- **Why it is below 95-100 (Root Cause):** Breaks intentional public AMI sharing invisibly.
- **Required Changes:** Validate local snapshot public dependencies beforehand.
- **Mandatory Preflight Checks:** Query for existing explicitly public snapshots.
- **Mandatory Gating:** Auto-run allowed with canary.
- **Post-Apply Verification:** Read snapshot block public access setting.
- **Rollback Playbook:** Disable snapshot block public access.
- **Test Cases:** Account actively sharing AMIs publicly -> observe canary warnings.
- **Expected Residual Risk:** Very Low.

### SecurityHub.1 Security Hub Enablement
- **Why it is below 95-100 (Root Cause):** Causes large cost spikes and conflicts with existing Config recording.
- **Required Changes:** Warn of price implications and check Config dependencies globally.
- **Mandatory Preflight Checks:** Verify Config is running properly.
- **Mandatory Gating:** Manual approval required.
- **Post-Apply Verification:** Run `aws securityhub describe-hub`.
- **Rollback Playbook:** `aws securityhub disable-security-hub`.
- **Test Cases:** Apply in an account without Config enabled -> ensure failure/warning.
- **Expected Residual Risk:** Low.

### GuardDuty.1 GuardDuty Enablement
- **Why it is below 95-100 (Root Cause):** Identical to Security Hub — cost implications for SMBs.
- **Required Changes:** Pre-calculate ingest cost warnings.
- **Mandatory Preflight Checks:** Verify no existing redundant detectors.
- **Mandatory Gating:** Manual approval required.
- **Post-Apply Verification:** List detectors logic.
- **Rollback Playbook:** Delete detector.
- **Test Cases:** Apply in a region already running GuardDuty -> verify idempotent behavior.
- **Expected Residual Risk:** Low.

### CloudTrail.1 CloudTrail Enablement
- **Why it is below 95-100 (Root Cause):** Missing S3 log buckets or KMS misconfigurations break trail writes. Overlaps with Org trails.
- **Required Changes:** Verify if an Org trail already covers the region. Create distinct S3 bucket for trails with proper policies.
- **Mandatory Preflight Checks:** Query for existing Org trails and check S3 Put rights.
- **Mandatory Gating:** Manual approval.
- **Post-Apply Verification:** Check trail status `IsLogging`.
- **Rollback Playbook:** Stop-logging and delete trail.
- **Test Cases:** Apply while an active Org trail natively captures all items.
- **Expected Residual Risk:** Low.

### Config.1 AWS Config Enablement
- **Why it is below 95-100 (Root Cause):** Config requires IAM roles and recording buckets which often collide with legacy configurations.
- **Required Changes:** Deploy local dependency verification.
- **Mandatory Preflight Checks:** Check for existing `default` recorders.
- **Mandatory Gating:** Manual approval required.
- **Post-Apply Verification:** Check configuration recorder status.
- **Rollback Playbook:** Stop configuration recorder execution.
- **Test Cases:** Legacy recorder exists in the region but is stopped -> verify update behavior.
- **Expected Residual Risk:** Low.

### SSM.7 SSM Public Sharing Block
- **Why it is below 95-100 (Root Cause):** Can break intentional sharing without robust warnings.
- **Required Changes:** Simple API validation but must support safe rollback.
- **Mandatory Preflight Checks:** Query for currently shared public SSM documents.
- **Mandatory Gating:** Auto-run allowed.
- **Post-Apply Verification:** Read the service setting state.
- **Rollback Playbook:** Re_enable public sharing service setting.
- **Test Cases:** Execute while a public doc relies on this sharing mechanism and catch warning.
- **Expected Residual Risk:** Very Low.

### IAM.4 Root Access Key Removal
- **Why it is below 95-100 (Root Cause):** Automation cannot manage root keys securely or reliably via standard APIs. Attempting automated TF deletion is a risky false promise.
- **Required Changes:** Discard Terraform bundle generation entirely. Replace with a guided manual workflow.
- **Mandatory Preflight Checks:** Detect root key presence via credential report.
- **Mandatory Gating:** Manual-only workflow.
- **Post-Apply Verification:** Ingest a fresh credential report proving absence.
- **Rollback Playbook:** N/A (Admin must manually rotate).
- **Test Cases:** Try to execute the automation automatically; require it to block and ask for evidence capture.
- **Expected Residual Risk:** Zero (execution shifted safely to user boundaries).

**Implementation update (2026-02-24):**
- IAM.4 is now enforced as **manual-only** in backend action/remediation handling.
- API now returns a structured `manual_workflow` payload (steps, required evidence, verification criteria) for IAM.4.
- Automatic run creation and PR-bundle execution paths return an explicit `Manual remediation required` error for IAM.4.
- Manual evidence upload/storage and validation are implemented:
  - `POST /api/actions/{action_id}/manual-workflow/evidence/upload`
  - `GET /api/actions/{action_id}/manual-workflow/evidence`
  - `GET /api/actions/{action_id}/manual-workflow/evidence/{evidence_id}/download`
  - `POST /api/actions/{action_id}/manual-workflow/validate`
- Validation now returns concrete completion states (`missing_required_evidence`, `complete`) based on required evidence keys.

---

## 4. Prioritized 30/60/90 Day Implementation Roadmap
**Next 30 Days (Execution Integrity & Quick Wins)**
- Implement A1 (Hard Targeting `allowed_account_ids` in all templates).
- Implement IAM.4 guided manual workflow (remove TF generation for it entirely).
- Implement A2 (Local wrapper script `run.sh` to trap errors).

**Next 60 Days (Preflight, Rollback, Data-driven Updates)**
- Overhaul S3.5 and S3.11 to use non-destructive policy merging.
- A7 (Rollback playbooks + containment) is implemented and closed (2026-02-24).
- A3 (Preflight static IAM probes) is implemented and closed (2026-02-24).

**Next 90 Days (Closed-loop Verification & Autonomy)**
- Keep A6 verification handlers aligned with any new remediation action types added after this closure.
- Convert low-risk controls (S3.9, EC2.182) to Auto-run with canary.
- Fully launch the 95-100 Safety Score Rubric in CI/CD.
- Execute follow-on F1-F4 backlog items below while preserving the current wrapper contract until redesign approval.

## 4.1 A7 Follow-on Plan (Out-of-Scope Items Now Planned)

### F1) API/DB persistence for backups + rollback state
> ⚠️ Status: Planned — not yet implemented
- **Scope:** Persist backup/rollback metadata currently stored only as bundle-local artifacts (`rollback/pre-state/...`) into backend-managed records.
- **Planned deliverables:** API endpoints for backup/rollback state, DB model + migration for artifact metadata, and artifact-reference linking from remediation run records.
- **Boundary:** Bundle-local artifacts remain the source of execution truth for rollback commands during this phase; persistence is additive for visibility/auditability.

### F2) UI rollback artifact visualization
> ⚠️ Status: Planned — not yet implemented
- **Scope:** Add frontend visibility for rollback readiness and backup capture details (metadata, latest backup pointer, artifact download/view links).
- **Planned deliverables:** Remediation run detail UI section for rollback artifacts, status indicators for backup capture success/failure, and action-level artifact navigation.
- **Dependency:** F1 backend/API persistence is the primary data source; until then, UI remains unchanged.

### F3) Execution-model redesign RFC (beyond wrapper contract)
> ⚠️ Status: Planned — not yet implemented
- **Scope:** Evaluate and document a v2 execution model beyond `run.sh` / `run_bundle.sh` / `run_all.sh` compatibility.
- **Planned deliverables:** Architecture decision record with options/tradeoffs, migration plan, and explicit backward-compatibility strategy.
- **Boundary:** No runtime redesign is introduced in current A7 closure; current wrapper contract remains in force.

Reference baseline for current implemented behavior: [Remediation Safety Model](../../architecture/remediation-safety-model.md#rollback-playbooks--containment-a7).

## 4.2 A8 Follow-on Plan (Wrapper Replay Centralization)

### F4) Centralized backend scheduler for telemetry replay
> ⚠️ Status: Planned — not yet implemented
- **Scope:** Add backend-managed replay orchestration for wrapper telemetry payloads that failed callback delivery, so replay does not depend only on subsequent local wrapper runs.
- **Planned deliverables:**
  - replay intake/persistence model for failed wrapper callback payload references
  - worker job + schedule for retrying failed telemetry callbacks with bounded retry policy
  - replay status fields (`pending`, `sent`, `exhausted`) exposed for operator troubleshooting
  - operational runbook section for replay queue triage and redrive
- **Boundary:** Existing wrapper-driven replay (`telemetry-*.json` resend on later runs) remains enabled as first-line fallback; centralized replay is additive, not a breaking contract change.

Reference baseline for current implemented behavior: [Remediation Safety Model](../../architecture/remediation-safety-model.md#remediation-telemetry-a8).

---

## 5. Definition of 95-100 Safety Rubric
Before any new remediation is released, it must pass this gate:
- [ ] **Targeting Pinned:** Provider strictly enforces `allowed_account_ids` and `region`.
- [ ] **Rollback Provisioned:** Pre-state is automatically dumped locally, and an inverse command script is provided.
- [ ] **Idempotent / Merging:** Does not overwrite non-target configurations (no raw policy overwrites).
- [ ] **Dependencies Probed:** Preflight validation of KMS Keys, S3 buckets, and IAM roles.
- [ ] **Closure Verifiable:** API read instructions or telemetry webhook explicitly verifies actual state post-apply.
- [ ] **Failure Handled:** Instructions/scripts explicitly catch partial apply or state corruption.

---

## 6. Gap List (Repo Deficiencies)
Currently missing in the repo preventing this:
1. No centralized backend scheduler for wrapper callback replay; replay is currently wrapper-driven on subsequent local runs.
2. No Terraform data source blocks (`data "aws_iam_policy_document"`) structured to handle merging existing policies.
3. IAM.4 validates required evidence-key presence, but does not parse credential report CSV contents to assert root-key flags.
4. No API/DB persistence exists yet for backup/rollback state; current rollback evidence remains bundle-local artifacts.
5. No frontend visualization exists yet for rollback artifacts/capture readiness in remediation run UX.
6. No approved execution-model redesign RFC exists yet for replacing/extending the current wrapper contract.
> ❓ Needs verification: Should backend parse uploaded credential reports and enforce semantic checks for `access_key_1_active` / `access_key_2_active`?
