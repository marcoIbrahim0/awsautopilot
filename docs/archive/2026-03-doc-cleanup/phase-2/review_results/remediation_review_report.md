# Executive Summary

## Overall Risk Posture
The overarching risk posture for automated remediations is **Mixed**. Simple, single-resource API toggles (like adjusting default EBS encryption or S3 bucket encryption) are highly safe and reliable. However, complex remediations that involve rewriting foundational components (like S3 Bucket Policies in S3.5) or restricting live network paths (EC2.53) pose critical operational risks. Furthermore, deploying Terraform locally on heterogeneous customer PCs without central remote state locking creates significant systemic vulnerability to interrupted applies and state corruption.

## Estimated Average Success Rate
The estimated average success rate across all 16 remediations is approximately **80%**. This breaks down into highly reliable simple components (90-99%) and volatile, dependency-heavy components like AWS Config or CloudTrail (40-75%) that frequently collide with existing configurations or SCPs.

## Safest to Automate First (Auto-Run)
- **S3.4** (S3 Bucket Encryption)
- **S3.9** (S3 Bucket Access Logging)
- **S3.11** (S3 Lifecycle Optimization)
- **EC2.7** (EBS Default Encryption)
- **EC2.182** (EBS Snapshot Public Block)
- **GuardDuty.1** (GuardDuty Enablement)
- **SSM.7** (SSM Public Sharing Block)

## Most Likely to Cause Outages or Lockouts
- **S3.5 (S3 Bucket SSL Enforcement)**: Terraform `aws_s3_bucket_policy` entirely overwrites or destroys existing complex merged policies, threatening total data lockout.
- **EC2.53 (Security Group Hardening)**: Revoking `0.0.0.0/0` on active SSH/RDP ports (22/3389) immediately breaks legitimate remote administration flows.
- **IAM.4 (Root Access Keys)**: Not automatable via API; attempting to automate gives false confidence.

## Top 5 Platform Improvements
1. **Dynamic Account Constraints**: Inject `allowed_account_ids = ["<target_id>"]` into generated Terraform `aws` providers to absolutely prevent cross-account misfires.
2. **Centralized Remote State**: Migrate from customer-local `.tfstate` files to SaaS-managed DynamoDB/S3 remote state locking to prevent orphaned states from interrupted PC processes.
3. **IAM Preflight Probes**: Execute strict granular IAM permission checks for the required remediation actions *before* initiating terraform runs.
4. **Approval Gating**: Build a UI flow requiring explicit customer consent for high-risk, destructive-capable remediations (e.g., S3.5, EC2.53).
5. **Non-Destructive S3 Policies**: Rewrite S3.5 to utilize granular policy appending logic or the exact AWS CLI rather than declarative Terraform replacement.

# Action-by-Action Table

| Control ID | Safety Class | Safety Score | Top Risk |
| --- | --- | --- | --- |
| S3.1 | Moderate | 60 | Unexpected outage for public-facing assets. |
| S3.2 | Moderate | 75 | Broken static websites or public asset delivery. |
| S3.4 | Low | 95 | Slight performance overhead (negligible). |
| S3.5 | Critical | 30 | Complete loss of legitimate access due to overwritten or deleted bucket policy. |
| S3.9 | Low | 90 | Storage cost increases in the log bucket. |
| S3.11 | Low | 90 | None significant, unless legitimate uploads take > 7 days. |
| S3.15 | Moderate | 65 | AccessDenied errors for principals lacking KMS cryptographic permissions. |
| EC2.7 | Low | 85 | Potential issues launching very old instance types that do not support encrypted EBS. |
| EC2.53 | High | 40 | Immediate lockout of legitimate administrative traffic. |
| EC2.182 | Low | 90 | Intentional public snapshots will begin failing. |
| SecurityHub.1 | Low | 95 | Minor AWS cost increases. |
| GuardDuty.1 | Low | 95 | Minor AWS cost increases. |
| CloudTrail.1 | Moderate | 75 | Orphaned S3 buckets and IAM roles if execution fails midway. |
| Config.1 | Moderate | 70 | Conflict with an already existing Configuration Recorder. |
| SSM.7 | Low | 95 | None expected. |
| IAM.4 | Critical | 10 | Irreversible destruction of root access keys actively used by legacy systems. |


# Detailed Findings

## S3.1 Account-level Public Access Block
### Failure Modes

**Failure Mode 1: Permission denied / missing IAM action (s3:PutAccountPublicAccessBlock)**
- **Severity**: Medium, **Likelihood**: Medium
- **Detection Method**: Terraform apply fails with AccessDenied
- **User/Customer Impact**: Remediation fails to apply; no disruption to workloads
- **Containment Strategy**: Run fails fast; state is unchanged.
- **Fix Recommendation**: Update operator IAM role to include account-level S3 permissions.
- **Evidence**: Observed via missing permissions checks in preflight logic.

**Failure Mode 2: Existing workloads relying on public S3 buckets break abruptly**
- **Severity**: Critical, **Likelihood**: High
- **Detection Method**: Customer reports 403 Access Denied from end-users/applications.
- **User/Customer Impact**: Severe outage for public-facing web assets (CloudFront lacking OAC, public websites, public downloads).
- **Containment Strategy**: Manual rollback via CLI.
- **Fix Recommendation**: Perform complete inventory of public dependencies before applying account-level blocks.
- **Evidence**: Account-level block restricts all buckets regardless of individual bucket policies.

### Safety Assessment

- **Safety Score**: 60/100
- **Safety Class**: Moderate
- **Blast Radius**: Account-wide (High)
- **Reversibility**: Easy (CLI command). Terraform state is consistent.
- **Permission Sensitivity**: Moderate (Requires account-level S3 permissions)
- **Service Continuity Risk**: High if existing workloads rely on public buckets
- **Rationale**: Account-wide S3 Public Access Block affects all buckets in the account. While reversible, it can abruptly break public workloads across the entire account.
- **Top Safety Risk**: Unexpected outage for public-facing assets.
- **Confidence**: High

### Inventory

- **Control ID**: S3.1
- **Terraform module/resource(s)**: aws_s3_account_public_access_block
- **File paths**: backend/services/pr_bundle.py (s3_block_public_access.tf)
- **Trigger condition / input parameters**: Account ID
- **AWS APIs/resources affected**: S3 Control API (PutPublicAccessBlock)
- **Required IAM permissions**: s3:PutAccountPublicAccessBlock
- **Scope**: account-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws s3control delete-public-access-block)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 65/100
- **Estimated Success Rate**: 85-95%
- **Preconditions Validation**: 10/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 15/15
- **Main Failure Driver**: Missing IAM cross-account permissions during apply.
- **Missing Evidence**: No explicit IAM permission check before execution, No rollback automation logic in PR bundle worker
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Manual approval required
- **Rationale**: Account-wide block public access can immediately break untracked public workloads across the entire account.
- **Mandatory Preconditions**: Account-wide public asset inventory scan and confirmation.
- **Biggest Risk**: Account-wide outage for public assets.
- **Most Important Fix**: Perform comprehensive preflight checks for CloudFront distributions and public website buckets before proposing.

## S3.2 Bucket-level Public Access Block
### Failure Modes

**Failure Mode 1: Permission denied / missing IAM action (s3:PutBucketPublicAccessBlock)**
- **Severity**: Medium, **Likelihood**: Medium
- **Detection Method**: Terraform apply fails with AccessDenied.
- **User/Customer Impact**: Remediation fails; bucket remains public.
- **Containment Strategy**: Run fails fast.
- **Fix Recommendation**: Verify bucket policies and IAM role for s3:PutBucketPublicAccessBlock.
- **Evidence**: Missing pre-execution IAM checks.

**Failure Mode 2: Target bucket hosts an active static website**
- **Severity**: Critical, **Likelihood**: Medium
- **Detection Method**: s3_website_hosting_active=True logged during preflight.
- **User/Customer Impact**: If applied, active static website goes offline.
- **Containment Strategy**: Preflight detects website hosting configuration.
- **Fix Recommendation**: Abort apply and require manual migration to CloudFront+OAC.
- **Evidence**: pr_bundle_preflight.py website hosting probe.

### Safety Assessment

- **Safety Score**: 75/100
- **Safety Class**: Moderate
- **Blast Radius**: Bucket-level (Moderate)
- **Reversibility**: Easy (CLI command). Revert bucket public access block.
- **Permission Sensitivity**: Low
- **Service Continuity Risk**: High for the targeted bucket if it hosts a website
- **Rationale**: Scoped to a single bucket, but blocking public access can break web hosting or public assets. Preflight checks for website hosting help mitigate risk.
- **Top Safety Risk**: Broken static websites or public asset delivery.
- **Confidence**: High

### Inventory

- **Control ID**: S3.2
- **Terraform module/resource(s)**: aws_s3_bucket_public_access_block / aws_cloudfront_origin_access_control
- **File paths**: backend/services/pr_bundle.py (s3_bucket_block_public_access.tf, s3_cloudfront_oac_private_s3.tf)
- **Trigger condition / input parameters**: Bucket Name
- **AWS APIs/resources affected**: S3 API (PutBucketPublicAccessBlock), CloudFront (CreateDistribution)
- **Required IAM permissions**: s3:PutBucketPublicAccessBlock, cloudfront:*
- **Scope**: bucket-level
- **Idempotent**: Yes
- **Preflight validation**: Yes (backend/workers/services/pr_bundle_preflight.py probes website hosting and public ACLs)
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws s3api delete-public-access-block)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 75/100
- **Estimated Success Rate**: 80-90%
- **Preconditions Validation**: 20/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 15/15
- **Main Failure Driver**: Websites breaking due to public block; IAM permission limits.
- **Missing Evidence**: No explicit IAM permission check, No automated rollback for disrupted websites
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Manual approval required
- **Rationale**: Applying bucket-level blocks can break existing websites or public asset delivery.
- **Mandatory Preconditions**: Verify no `s3:GetObject` public traffic in access logs.
- **Biggest Risk**: Broken static websites.
- **Most Important Fix**: Implement log analysis to prove the bucket is not legitimately serving public traffic.

## S3.4 S3 Bucket Encryption
### Failure Modes

**Failure Mode 1: Permission denied / missing IAM action (s3:PutEncryptionConfiguration)**
- **Severity**: Low, **Likelihood**: Low
- **Detection Method**: Terraform apply fails.
- **User/Customer Impact**: Bucket remains unencrypted (default).
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Grant s3:PutEncryptionConfiguration to executor role.
- **Evidence**: IAM lacks checks.

### Safety Assessment

- **Safety Score**: 95/100
- **Safety Class**: Low
- **Blast Radius**: Bucket-level (Low)
- **Reversibility**: Easy (Remove default encryption).
- **Permission Sensitivity**: Low
- **Service Continuity Risk**: Low (AES256 is transparent to clients)
- **Rationale**: Enabling AES256 default encryption on a bucket is generally transparent and does not break existing access patterns.
- **Top Safety Risk**: Slight performance overhead (negligible).
- **Confidence**: High

### Inventory

- **Control ID**: S3.4
- **Terraform module/resource(s)**: aws_s3_bucket_server_side_encryption_configuration
- **File paths**: backend/services/pr_bundle.py (s3_bucket_encryption.tf)
- **Trigger condition / input parameters**: Bucket Name
- **AWS APIs/resources affected**: S3 API (PutBucketEncryption)
- **Required IAM permissions**: s3:PutEncryptionConfiguration
- **Scope**: bucket-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws s3api delete-bucket-encryption)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 60/100
- **Estimated Success Rate**: 90-95%
- **Preconditions Validation**: 10/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 15/15
- **Main Failure Driver**: General Terraform apply failures or missing permissions.
- **Missing Evidence**: No IAM check, No rollback automation
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run
- **Rationale**: SSE-S3 default encryption is completely transparent to clients.
- **Mandatory Preconditions**: Basic permission checks.
- **Biggest Risk**: None significant.
- **Most Important Fix**: Add IAM preflight checks for `s3:PutEncryptionConfiguration`.

## S3.5 S3 Bucket SSL Enforcement
### Specific Field Execution Risk
- Highly sensitive to interrupted applies, as an incomplete bucket policy overwrite could lock everyone out of the bucket permanently.

### Failure Modes

**Failure Mode 1: Existing bucket policy overwritten or destroyed**
- **Severity**: Critical, **Likelihood**: High
- **Detection Method**: Terraform plan shows replacement/deletion of existing policy blocks.
- **User/Customer Impact**: Legitimate applications or cross-account access abruptly lose access.
- **Containment Strategy**: None. Reverting destroys the entire policy.
- **Fix Recommendation**: Require manual review of existing bucket policies; do not blindly overwrite them.
- **Evidence**: aws_s3_bucket_policy manages the entire policy object. Rollback command explicitly notes 'removes entire merged policy'.

**Failure Mode 2: Policy size exceeds AWS limits (20KB)**
- **Severity**: Low, **Likelihood**: Low
- **Detection Method**: Terraform apply fails with MalformedPolicy/EntityTooLarge.
- **User/Customer Impact**: Remediation fails.
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Consolidate policy statements.
- **Evidence**: Bucket policies have strict size bounds.

### Safety Assessment

- **Safety Score**: 30/100
- **Safety Class**: Critical
- **Blast Radius**: Bucket-level (Moderate)
- **Reversibility**: Hard (Applying new bucket policy can overwrite/delete existing statements. Rollback destroys the entire policy).
- **Permission Sensitivity**: High (Bucket policies control fundamental access)
- **Service Continuity Risk**: High (Clients not enforcing TLS will break)
- **Rationale**: Applying a bucket policy for SSL enforcement can inadvertently overwrite existing access rules. Un-applying it via the provided rollback (deleting the policy entirely) is destructive.
- **Top Safety Risk**: Complete loss of legitimate access due to overwritten or deleted bucket policy.
- **Confidence**: High

### Inventory

- **Control ID**: S3.5
- **Terraform module/resource(s)**: aws_s3_bucket_policy
- **File paths**: backend/services/pr_bundle.py (s3_bucket_require_ssl.tf)
- **Trigger condition / input parameters**: Bucket Name
- **AWS APIs/resources affected**: S3 API (PutBucketPolicy)
- **Required IAM permissions**: s3:PutBucketPolicy
- **Scope**: bucket-level
- **Idempotent**: Yes
- **Preflight validation**: Yes (backend/workers/services/pr_bundle_preflight.py checks for existing Allow statements)
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws s3api delete-bucket-policy)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 50/100
- **Estimated Success Rate**: 60-75%
- **Preconditions Validation**: 15/30
- **Error Handling**: 5/20
- **Idempotency**: 10/15
- **Dependency Fragility**: 10/15
- **Main Failure Driver**: Bucket policy conflicting limits or exceeding max policy size.
- **Missing Evidence**: No IAM check, No automated rollback to perfectly restore old bucket policy
- **Confidence**: Medium

### Guardrails and Rollout Recommendations

- **Recommendation**: Disabled until fixed
- **Rationale**: Overwriting bucket policies with Terraform is highly destructive to existing complex merged policies.
- **Mandatory Preconditions**: Robust policy parser that strictly appends `Deny` statements without touching existing rules.
- **Biggest Risk**: Irreversible deletion of critical bucket access policies.
- **Most Important Fix**: Move away from declarative full-policy replacement (`aws_s3_bucket_policy`). Use granular API appending or CLI.

## S3.9 S3 Bucket Access Logging
### Failure Modes

**Failure Mode 1: Dependency missing (logging bucket lacks ACL/Policy for log delivery)**
- **Severity**: Medium, **Likelihood**: Medium
- **Detection Method**: Terraform apply fails with InvalidTargetBucketForLogging.
- **User/Customer Impact**: Remediation fails.
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Ensure target log bucket has LogDeliveryWrite ACL or appropriate IAM policy.
- **Evidence**: S3 access logging requires destination bucket permissions.

### Safety Assessment

- **Safety Score**: 90/100
- **Safety Class**: Low
- **Blast Radius**: Bucket-level (Low)
- **Reversibility**: Easy (Disable logging)
- **Permission Sensitivity**: Low
- **Service Continuity Risk**: Low
- **Rationale**: Enabling access logging simply writes logs to a target bucket. Impact is minimal.
- **Top Safety Risk**: Storage cost increases in the log bucket.
- **Confidence**: High

### Inventory

- **Control ID**: S3.9
- **Terraform module/resource(s)**: aws_s3_bucket_logging
- **File paths**: backend/services/pr_bundle.py (s3_bucket_access_logging.tf)
- **Trigger condition / input parameters**: Bucket Name, Log Bucket Name
- **AWS APIs/resources affected**: S3 API (PutBucketLogging)
- **Required IAM permissions**: s3:PutBucketLogging
- **Scope**: bucket-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws s3api put-bucket-logging empty status)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 65/100
- **Estimated Success Rate**: 80-90%
- **Preconditions Validation**: 15/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 15/15
- **Main Failure Driver**: Target logging bucket missing proper ACLs or policy for delivery.
- **Missing Evidence**: Log bucket existence verification is implicit, No IAM check
- **Confidence**: Medium

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run
- **Rationale**: Enabling logging is non-disruptive.
- **Mandatory Preconditions**: Verify log destination bucket exists and has correct ACLs.
- **Biggest Risk**: Target bucket missing proper permissions, causing apply failure.
- **Most Important Fix**: Add dependency check for log bucket ACLs.

## S3.11 S3 Lifecycle Optimization
### Failure Modes

**Failure Mode 1: Existing lifecycle rules overwritten**
- **Severity**: High, **Likelihood**: High
- **Detection Method**: Terraform plan replaces old rules.
- **User/Customer Impact**: Existing data transitions or expirations immediately stop functioning.
- **Containment Strategy**: Terraform must be configured to append rules, not overwrite.
- **Fix Recommendation**: Use aws_s3_bucket_lifecycle_configuration carefully with existing rules.
- **Evidence**: aws_s3_bucket_lifecycle_configuration is authoritative for the entire bucket.

### Safety Assessment

- **Safety Score**: 90/100
- **Safety Class**: Low
- **Blast Radius**: Bucket-level (Low)
- **Reversibility**: Easy
- **Permission Sensitivity**: Low
- **Service Continuity Risk**: Low (Only aborts failed incomplete uploads after 7 days)
- **Rationale**: Adding a lifecycle rule to abort incomplete multipart uploads is very low risk. It cleans up unused data.
- **Top Safety Risk**: None significant, unless legitimate uploads take > 7 days.
- **Confidence**: High

### Inventory

- **Control ID**: S3.11
- **Terraform module/resource(s)**: aws_s3_bucket_lifecycle_configuration
- **File paths**: backend/services/pr_bundle.py (s3_bucket_lifecycle_configuration.tf)
- **Trigger condition / input parameters**: Bucket Name, abort_incomplete_multipart_days
- **AWS APIs/resources affected**: S3 API (PutLifecycleConfiguration)
- **Required IAM permissions**: s3:PutLifecycleConfiguration
- **Scope**: bucket-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws s3api delete-bucket-lifecycle)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 60/100
- **Estimated Success Rate**: 85-95%
- **Preconditions Validation**: 10/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 15/15
- **Main Failure Driver**: Lack of correct IAM permissions for s3:PutLifecycleConfiguration.
- **Missing Evidence**: No IAM check
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run
- **Rationale**: Cleaning up incomplete multipart uploads is safe and saves cost.
- **Mandatory Preconditions**: None strictly required beyond permissions.
- **Biggest Risk**: Overwriting existing lifecycle rules.
- **Most Important Fix**: Ensure terraform appends lifecycle rules rather than replacing all rules.

## S3.15 S3 Bucket KMS Encryption
### Failure Modes

**Failure Mode 1: Dependency missing / KMS key policy restricts usage**
- **Severity**: High, **Likelihood**: High
- **Detection Method**: Terraform apply fails with KMSAccessDenied, or subsequent GetObject data calls fail.
- **User/Customer Impact**: Data is locked out to consumers that lack kms:Decrypt.
- **Containment Strategy**: None post-apply.
- **Fix Recommendation**: Ensure callers have KMS permissions before enforcing SSE-KMS.
- **Evidence**: KMS requires explicit IAM and Key Policy allows.

### Safety Assessment

- **Safety Score**: 65/100
- **Safety Class**: Moderate
- **Blast Radius**: Bucket-level (Moderate)
- **Reversibility**: Moderate
- **Permission Sensitivity**: Moderate
- **Service Continuity Risk**: Moderate (KMS requires clients to have kms:GenerateDataKey permissions)
- **Rationale**: Switching default encryption to KMS requires all interacting IAM roles to have KMS permissions. This frequently breaks cross-account access and roles with tightly scoped inline policies.
- **Top Safety Risk**: AccessDenied errors for principals lacking KMS cryptographic permissions.
- **Confidence**: High

### Inventory

- **Control ID**: S3.15
- **Terraform module/resource(s)**: aws_s3_bucket_server_side_encryption_configuration
- **File paths**: backend/services/pr_bundle.py (s3_bucket_encryption_kms.tf)
- **Trigger condition / input parameters**: Bucket Name, KMS Key ARN
- **AWS APIs/resources affected**: S3 API (PutBucketEncryption), KMS
- **Required IAM permissions**: s3:PutEncryptionConfiguration
- **Scope**: bucket-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws s3api put-bucket-encryption with AES256)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 50/100
- **Estimated Success Rate**: 70-85%
- **Preconditions Validation**: 5/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 10/15
- **Main Failure Driver**: KMS key policy denies usage to S3 or cross-account callers.
- **Missing Evidence**: No check if specified KMS key exists or is accessible, No IAM check
- **Confidence**: Medium

### Guardrails and Rollout Recommendations

- **Recommendation**: Manual approval required
- **Rationale**: Enforcing KMS encryption requires modifying cross-account role policies and KMS key policies.
- **Mandatory Preconditions**: Verify KMS key policies allow access to all roles currently reading the bucket.
- **Biggest Risk**: AccessDenied for consumers lacking KMS decrypt permissions.
- **Most Important Fix**: Perform IAM Access Analyzer checks to validate KMS access paths.

## EC2.7 EBS Default Encryption
### Failure Modes

**Failure Mode 1: Permission denied (ec2:EnableEbsEncryptionByDefault)**
- **Severity**: Low, **Likelihood**: Low
- **Detection Method**: Terraform apply fails.
- **User/Customer Impact**: Remediation fails; applies to region.
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Update role with EC2 management permissions.
- **Evidence**: Standard IAM limits.

### Safety Assessment

- **Safety Score**: 85/100
- **Safety Class**: Low
- **Blast Radius**: Region-wide (High)
- **Reversibility**: Easy
- **Permission Sensitivity**: Low
- **Service Continuity Risk**: Low (Only affects new volumes. Might impact ancient instance types)
- **Rationale**: Region-wide default EBS encryption only applies to newly created volumes. It is non-disruptive to running instances.
- **Top Safety Risk**: Potential issues launching very old instance types that do not support encrypted EBS.
- **Confidence**: High

### Inventory

- **Control ID**: EC2.7
- **Terraform module/resource(s)**: aws_ebs_encryption_by_default
- **File paths**: backend/services/pr_bundle.py (ebs_default_encryption.tf)
- **Trigger condition / input parameters**: Region
- **AWS APIs/resources affected**: EC2 API (EnableEbsEncryptionByDefault)
- **Required IAM permissions**: ec2:EnableEbsEncryptionByDefault
- **Scope**: region-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws ec2 disable-ebs-encryption-by-default)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 60/100
- **Estimated Success Rate**: 90-99%
- **Preconditions Validation**: 10/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 15/15
- **Main Failure Driver**: Insufficient ec2:EnableEbsEncryptionByDefault permissions.
- **Missing Evidence**: No IAM check
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run
- **Rationale**: Region-wide default EBS encryption only applies to newly created volumes.
- **Mandatory Preconditions**: Permission checks.
- **Biggest Risk**: Extremely old legacy instance types failing to launch.
- **Most Important Fix**: Add IAM preflight checks.

## EC2.53 Security Group Hardening
### Specific Field Execution Risk
- State loss during apply means Terraform forgets it revoked the rules. Manual intervention is required to understand what was changed.

### Failure Modes

**Failure Mode 1: Lockout of active administrators via RDP/SSH**
- **Severity**: High, **Likelihood**: High
- **Detection Method**: Terraform apply revokes 0.0.0.0/0 on 22/3389.
- **User/Customer Impact**: Legitimate admin scripts, pipelines, and humans lose access.
- **Containment Strategy**: Preflight probe checks for active ENIs attached to the SG.
- **Fix Recommendation**: Require fallback allow-lists or SSM Session Manager implementation before blocking.
- **Evidence**: pr_bundle_preflight.py captures active ENIs but cannot verify human usage.

**Failure Mode 2: State drift prevents exact rollback**
- **Severity**: Medium, **Likelihood**: Medium
- **Detection Method**: Manual terraform rollback fails to reinstate complex legacy rules.
- **User/Customer Impact**: Extended outage while manual recreation is performed.
- **Containment Strategy**: Capture pre-apply tfvars carefully.
- **Fix Recommendation**: Save the original API output of describe-security-group-rules.
- **Evidence**: Terraform revokes specific rules but manual rollback is required.

### Safety Assessment

- **Safety Score**: 40/100
- **Safety Class**: High
- **Blast Radius**: Resource-level / Security Group (Moderate)
- **Reversibility**: Hard (Revoking a rule in Terraform may not easily recreate the exact original rule if undone manually, tf state drift).
- **Permission Sensitivity**: Moderate
- **Service Continuity Risk**: High (Revoking 0.0.0.0/0 on port 22/3389 immediately breaks active remote administration).
- **Rationale**: Removing public SSH/RDP access immediately closes network paths. If legitimate administrators or automated deployment scripts rely on this, they will be instantly locked out.
- **Top Safety Risk**: Immediate lockout of legitimate administrative traffic.
- **Confidence**: High

### Inventory

- **Control ID**: EC2.53
- **Terraform module/resource(s)**: aws_vpc_security_group_ingress_rule
- **File paths**: backend/services/pr_bundle.py (sg_restrict_public_ports.tf)
- **Trigger condition / input parameters**: Security Group ID
- **AWS APIs/resources affected**: EC2 API (RevokeSecurityGroupIngress / AuthorizeSecurityGroupIngress)
- **Required IAM permissions**: ec2:RevokeSecurityGroupIngress, ec2:AuthorizeSecurityGroupIngress
- **Scope**: resource-level (Security Group)
- **Idempotent**: Yes
- **Preflight validation**: Yes (backend/workers/services/pr_bundle_preflight.py checks for active ENIs attached)
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual terraform apply with previous.tfvars or CLI
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 65/100
- **Estimated Success Rate**: 75-85%
- **Preconditions Validation**: 20/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 10/15
- **Main Failure Driver**: Security group modified natively during PR apply; state drift lockout.
- **Missing Evidence**: Cannot strictly verify if 0.0.0.0 is used by human admins in preflight, No IAM check
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Manual approval required
- **Rationale**: Revoking 0.0.0.0/0 on 22/3389 immediately terminates active SSH/RDP access.
- **Mandatory Preconditions**: SSM Session Manager must be verified as active and usable before locking down ports.
- **Biggest Risk**: Lockout of legitimate administration.
- **Most Important Fix**: Integrate SSM agent health checks into preflight.

## EC2.182 EBS Snapshot Public Block
### Failure Modes

**Failure Mode 1: Permission denied (ec2:EnableSnapshotBlockPublicAccess)**
- **Severity**: Low, **Likelihood**: Low
- **Detection Method**: Terraform apply fails.
- **User/Customer Impact**: Remediation fails; applies to region.
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Update role with EC2 management permissions.
- **Evidence**: Standard IAM limits.

### Safety Assessment

- **Safety Score**: 90/100
- **Safety Class**: Low
- **Blast Radius**: Region-wide (High)
- **Reversibility**: Easy
- **Permission Sensitivity**: Low
- **Service Continuity Risk**: Low
- **Rationale**: Blocking public snapshots at the region level prevents accidental data exposure and does not impact private snapshot sharing.
- **Top Safety Risk**: Intentional public snapshots will begin failing.
- **Confidence**: High

### Inventory

- **Control ID**: EC2.182
- **Terraform module/resource(s)**: aws_ec2_snapshot_block_public_access
- **File paths**: backend/services/pr_bundle.py (ebs_snapshot_block_public_access.tf)
- **Trigger condition / input parameters**: Region
- **AWS APIs/resources affected**: EC2 API (EnableSnapshotBlockPublicAccess)
- **Required IAM permissions**: ec2:EnableSnapshotBlockPublicAccess
- **Scope**: region-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws ec2 disable-snapshot-block-public-access)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 60/100
- **Estimated Success Rate**: 90-99%
- **Preconditions Validation**: 10/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 15/15
- **Main Failure Driver**: Insufficient EC2 permissions.
- **Missing Evidence**: No IAM check
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run
- **Rationale**: Blocking public snapshots at the region level is safe and prevents exposure.
- **Mandatory Preconditions**: Permission checks.
- **Biggest Risk**: Intentional public snapshots fail.
- **Most Important Fix**: Add IAM preflight checks.

## SecurityHub.1 Security Hub Enablement
### Failure Modes

**Failure Mode 1: AWS Config prerequisite missing**
- **Severity**: Medium, **Likelihood**: High
- **Detection Method**: Terraform apply fails or Security Hub enters inactive state.
- **User/Customer Impact**: Security Hub fails to enable or function.
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Validate AWS Config enablement beforehand or bundle remediation.
- **Evidence**: Security Hub relies on Config.

### Safety Assessment

- **Safety Score**: 95/100
- **Safety Class**: Low
- **Blast Radius**: Region-wide (Moderate)
- **Reversibility**: Easy
- **Permission Sensitivity**: Low
- **Service Continuity Risk**: Low
- **Rationale**: Enabling Security Hub is a read-only observability change.
- **Top Safety Risk**: Minor AWS cost increases.
- **Confidence**: High

### Inventory

- **Control ID**: SecurityHub.1
- **Terraform module/resource(s)**: aws_securityhub_account
- **File paths**: backend/services/pr_bundle.py (enable_security_hub.tf)
- **Trigger condition / input parameters**: Region
- **AWS APIs/resources affected**: SecurityHub API (EnableSecurityHub)
- **Required IAM permissions**: securityhub:EnableSecurityHub, iam:CreateServiceLinkedRole
- **Scope**: region-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws securityhub disable-security-hub)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 50/100
- **Estimated Success Rate**: 80-90%
- **Preconditions Validation**: 5/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 10/15
- **Main Failure Driver**: AWS Config not enabled or IAM missing for Service Linked Role.
- **Missing Evidence**: No check if AWS Config is enabled (SecurityHub prerequisite), No IAM check
- **Confidence**: Medium

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run with canary
- **Rationale**: Enabling Security Hub is safe but depends on AWS Config.
- **Mandatory Preconditions**: Verify AWS Config is enabled in the region.
- **Biggest Risk**: Config dependency missing.
- **Most Important Fix**: Bundle Config enablement or add strict preflight check.

## GuardDuty.1 GuardDuty Enablement
### Failure Modes

**Failure Mode 1: Missing IAM permission for Service Linked Role creation**
- **Severity**: Low, **Likelihood**: Medium
- **Detection Method**: Terraform apply fails with AccessDenied for iam:CreateServiceLinkedRole.
- **User/Customer Impact**: Remediation fails.
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Ensure iam:CreateServiceLinkedRole is allowed.
- **Evidence**: GuardDuty requires an SLR.

### Safety Assessment

- **Safety Score**: 95/100
- **Safety Class**: Low
- **Blast Radius**: Region-wide (Moderate)
- **Reversibility**: Easy
- **Permission Sensitivity**: Low
- **Service Continuity Risk**: Low
- **Rationale**: Enabling GuardDuty is an unintrusive observability change.
- **Top Safety Risk**: Minor AWS cost increases.
- **Confidence**: High

### Inventory

- **Control ID**: GuardDuty.1
- **Terraform module/resource(s)**: aws_guardduty_detector
- **File paths**: backend/services/pr_bundle.py (enable_guardduty.tf)
- **Trigger condition / input parameters**: Region
- **AWS APIs/resources affected**: GuardDuty API (CreateDetector)
- **Required IAM permissions**: guardduty:CreateDetector, iam:CreateServiceLinkedRole
- **Scope**: region-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws guardduty delete-detector)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 50/100
- **Estimated Success Rate**: 85-95%
- **Preconditions Validation**: 5/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 10/15
- **Main Failure Driver**: Missing IAM permission for Service Linked Role creation.
- **Missing Evidence**: No IAM check
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run
- **Rationale**: Observability enablement is safe.
- **Mandatory Preconditions**: iam:CreateServiceLinkedRole permissions.
- **Biggest Risk**: None.
- **Most Important Fix**: Add IAM preflight checks.

## CloudTrail.1 CloudTrail Enablement
### Specific Field Execution Risk
- Partial apply can leave orphaned S3 buckets if the trail itself fails to create.

### Failure Modes

**Failure Mode 1: S3 bucket name collision globally**
- **Severity**: Medium, **Likelihood**: High
- **Detection Method**: Terraform apply fails during aws_s3_bucket create.
- **User/Customer Impact**: Partial apply. Trail might not be fully configured.
- **Containment Strategy**: Terraform halts.
- **Fix Recommendation**: Use highly randomized bucket names with account ID.
- **Evidence**: Review of Terraform structure indicates an S3 bucket is created inline.

**Failure Mode 2: SCP / Organization trails prevent local trail creation**
- **Severity**: Medium, **Likelihood**: Medium
- **Detection Method**: Terraform apply fails indicating max trails reached or insufficient org permissions.
- **User/Customer Impact**: Remediation fails.
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Detect Organization trails before running local remediations.
- **Evidence**: Common SMB scenario where AWS ProServe/MSP setup exists.

### Safety Assessment

- **Safety Score**: 75/100
- **Safety Class**: Moderate
- **Blast Radius**: Region-wide (Advanced dependencies)
- **Reversibility**: Moderate (Leaves behind S3 buckets or roles if not fully destroyed)
- **Permission Sensitivity**: Moderate
- **Service Continuity Risk**: Low
- **Rationale**: Enabling CloudTrail requires coordinating S3 buckets, bucket policies, and IAM roles. Failures midway can leave orphaned resources, and rollback requires careful cleanup.
- **Top Safety Risk**: Orphaned S3 buckets and IAM roles if execution fails midway.
- **Confidence**: High

### Inventory

- **Control ID**: CloudTrail.1
- **Terraform module/resource(s)**: aws_cloudtrail
- **File paths**: backend/services/pr_bundle.py (cloudtrail_enabled.tf)
- **Trigger condition / input parameters**: Region
- **AWS APIs/resources affected**: CloudTrail API (CreateTrail, StartLogging)
- **Required IAM permissions**: cloudtrail:CreateTrail, cloudtrail:StartLogging
- **Scope**: region-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws cloudtrail stop-logging)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 40/100
- **Estimated Success Rate**: 60-75%
- **Preconditions Validation**: 5/30
- **Error Handling**: 5/20
- **Idempotency**: 10/15
- **Dependency Fragility**: 10/15
- **Main Failure Driver**: Global S3 bucket name collision or partial resource creation failure.
- **Missing Evidence**: No S3 bucket global uniqueness verification, No rollback automation on partial trail failure
- **Confidence**: Medium

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run with canary
- **Rationale**: Dependency heavy, but generally safe if resources are uniquely named.
- **Mandatory Preconditions**: Check for existing organization trails or SCPs.
- **Biggest Risk**: Partial apply leaving orphaned buckets.
- **Most Important Fix**: Ensure highly randomized S3 bucket naming and automatic rollback on failure.

## Config.1 AWS Config Enablement
### Specific Field Execution Risk
- Partial apply can leave orphaned S3 buckets, SNS topics, or IAM roles without a recorder.

### Failure Modes

**Failure Mode 1: Existing Configuration Recorder collision (Max 1 per region)**
- **Severity**: Medium, **Likelihood**: High
- **Detection Method**: Terraform apply fails with MaxNumberOfConfigurationRecordersExceededException.
- **User/Customer Impact**: Remediation fails entirely.
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Pre-check region for existing recorders before executing.
- **Evidence**: AWS hard limit on Config.

### Safety Assessment

- **Safety Score**: 70/100
- **Safety Class**: Moderate
- **Blast Radius**: Region-wide (Advanced dependencies)
- **Reversibility**: Moderate (Leaves behind delivery channels, buckets)
- **Permission Sensitivity**: Moderate
- **Service Continuity Risk**: Low
- **Rationale**: Setting up AWS Config requires S3 buckets, SNS topics, and IAM roles. AWS limits one configuration recorder per region, making concurrency/conflicts highly likely if one already exists.
- **Top Safety Risk**: Conflict with an already existing Configuration Recorder.
- **Confidence**: High

### Inventory

- **Control ID**: Config.1
- **Terraform module/resource(s)**: aws_config_configuration_recorder, aws_config_delivery_channel
- **File paths**: backend/services/pr_bundle.py (aws_config_enabled.tf)
- **Trigger condition / input parameters**: Region
- **AWS APIs/resources affected**: Config API (PutConfigurationRecorder, PutDeliveryChannel, StartConfigurationRecorder)
- **Required IAM permissions**: config:PutConfigurationRecorder, config:PutDeliveryChannel, config:StartConfigurationRecorder
- **Scope**: region-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws configservice stop-configuration-recorder)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 30/100
- **Estimated Success Rate**: 40-60%
- **Preconditions Validation**: 5/30
- **Error Handling**: 5/20
- **Idempotency**: 5/15
- **Dependency Fragility**: 5/15
- **Main Failure Driver**: Hard AWS limit of 1 ConfigurationRecorder per region limits automation success.
- **Missing Evidence**: Does not verify if a ConfigurationRecorder already exists in the region
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run with canary
- **Rationale**: Safe, but frequently collides with existing recorders.
- **Mandatory Preconditions**: Verify region does not already have a Configuration Recorder.
- **Biggest Risk**: Apply failure due to 1-recorder-per-region limit.
- **Most Important Fix**: Add strict preflight to check `aws configservice describe-configuration-recorders`.

## SSM.7 SSM Public Sharing Block
### Failure Modes

**Failure Mode 1: Permission denied (ssm:UpdateServiceSetting)**
- **Severity**: Low, **Likelihood**: Low
- **Detection Method**: Terraform apply fails.
- **User/Customer Impact**: Remediation fails.
- **Containment Strategy**: Fail fast.
- **Fix Recommendation**: Ensure policy grants SSM settings update.
- **Evidence**: Standard API check.

### Safety Assessment

- **Safety Score**: 95/100
- **Safety Class**: Low
- **Blast Radius**: Region-wide (Moderate)
- **Reversibility**: Easy
- **Permission Sensitivity**: Low
- **Service Continuity Risk**: Low
- **Rationale**: Blocking public sharing of SSM documents is highly safe as public documents are extremely rare and usually a mistake.
- **Top Safety Risk**: None expected.
- **Confidence**: High

### Inventory

- **Control ID**: SSM.7
- **Terraform module/resource(s)**: aws_ssm_service_setting
- **File paths**: backend/services/pr_bundle.py (ssm_block_public_sharing.tf)
- **Trigger condition / input parameters**: Region
- **AWS APIs/resources affected**: SSM API (UpdateServiceSetting)
- **Required IAM permissions**: ssm:UpdateServiceSetting
- **Scope**: region-level
- **Idempotent**: Yes
- **Preflight validation**: No
- **Post-apply verification**: Yes (backend/workers/services/post_apply_reconcile.py enqueues targeted inventory sync to verify state)
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: Yes (Terraform plan phase is executed as RemediationRunExecutionPhase.plan in backend/workers/jobs/remediation_run_execution.py)
- **Rollback mechanism / fallback path**: Manual CLI (aws ssm update-service-setting --setting-value Enable)
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 60/100
- **Estimated Success Rate**: 90-99%
- **Preconditions Validation**: 10/30
- **Error Handling**: 10/20
- **Idempotency**: 15/15
- **Dependency Fragility**: 15/15
- **Main Failure Driver**: Missing ssm:UpdateServiceSetting permission.
- **Missing Evidence**: No IAM check
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Auto-run
- **Rationale**: Blocking public SSM document sharing is non-disruptive.
- **Mandatory Preconditions**: Permission checks.
- **Biggest Risk**: None.
- **Most Important Fix**: Add IAM preflight checks.

## IAM.4 Root Access Key Removal
### Failure Modes

**Failure Mode 1: Remediation impossible via automation**
- **Severity**: Low, **Likelihood**: High
- **Detection Method**: User tries to apply; fails gracefully.
- **User/Customer Impact**: Customer must log in manually to delete root keys.
- **Containment Strategy**: Remediation bundle outputs instructions instead of tf resource.
- **Fix Recommendation**: Provide clear manual guidance.
- **Evidence**: AWS prevents programmatic access to root keys.

### Safety Assessment

- **Safety Score**: 10/100
- **Safety Class**: Critical
- **Blast Radius**: Account-level (High)
- **Reversibility**: Hard (Once root access keys are deleted, they cannot be automatically restored. Requires manual root login).
- **Permission Sensitivity**: Critical (Root account access)
- **Service Continuity Risk**: Critical (If production workloads rely on root keys, they will suffer immediate, permanent outages)
- **Rationale**: Root access keys should not exist, but if they do and are deleted, anything using them will break permanently. Terraform cannot manage root keys, meaning this involves manual high-stakes intervention.
- **Top Safety Risk**: Irreversible destruction of root access keys actively used by legacy systems.
- **Confidence**: High

### Inventory

- **Control ID**: IAM.4
- **Terraform module/resource(s)**: N/A (Instructions only)
- **File paths**: backend/services/pr_bundle.py (_generate_for_iam_root_access_key_absent)
- **Trigger condition / input parameters**: Account ID
- **AWS APIs/resources affected**: None via API. Requires root account login.
- **Required IAM permissions**: None (Root account credentials required)
- **Scope**: account-level
- **Idempotent**: N/A
- **Preflight validation**: No
- **Post-apply verification**: N/A
- **Timeout/retry logic**: Timeout=300s via subprocess in backend/workers/jobs/remediation_run_execution.py. No internal retry; relies on SQS visibility timeout if worker crashes.
- **Dry-run or plan-only mode**: N/A
- **Rollback mechanism / fallback path**: N/A
- **Execution locking**: Yes (Database row-level status lock via RemediationRunExecution in backend/workers/jobs/remediation_run_execution.py)


### Reliability Assessment

- **Total Reliability Score**: 0/100
- **Estimated Success Rate**: 0% (Manual intervention required)
- **Preconditions Validation**: 0/30
- **Error Handling**: 0/20
- **Idempotency**: 0/15
- **Dependency Fragility**: 0/15
- **Main Failure Driver**: Cannot be automated via standard AWS APIs or Terraform.
- **Missing Evidence**: APIs cannot rotate/delete root keys
- **Confidence**: High

### Guardrails and Rollout Recommendations

- **Recommendation**: Disabled until fixed
- **Rationale**: Standard AWS APIs cannot manage root credentials.
- **Mandatory Preconditions**: N/A
- **Biggest Risk**: Tooling pretends to work but does nothing, or gives false confidence.
- **Most Important Fix**: Convert to a purely manual workflow checklist.

# Platform Findings
## Platform-Wide Mandatory Guardrails

- Preflight permission checks: Validate that the executing IAM role has the exact granular permissions required before modifying state.
- Dependency checks: Validate AWS Config for Security Hub; log bucket ACLs for S3.9; KMS key policies for S3.15.
- Backup/state snapshot strategy: Automatically output `describe` API calls to a local `rollback.json` before mutating state.
- Tenant/account targeting verification: Inject `allowed_account_ids = ["<target_id>"]` into all generated Terraform `aws` providers to absolutely prevent cross-account misfires.
- Terraform state locking and conflict prevention: Migrate customer PC state to a centralized SaaS-managed DynamoDB/S3 remote state bucket, or use ephemeral CloudFormation stacks instead of local Terraform.
- Rollback playbooks: Generate explicit CLI rollback commands during failure.
- Post-change health checks: Continuously run `pr_bundle_preflight` probes *after* apply to assert desired state.
- Structured impact logging: Log specific resource IDs affected to the backend.
- Kill switch: Implement a global SaaS kill-switch to pause generating all PR bundles.
- Approval workflow: High-risk remediations (S3.5, EC2.53) must require explicit customer acknowledgement of risks in the UI before granting the bundle.


## Test Environment Maturity
- **Status**: No explicit evidence of a fully functional, heterogeneous staging/sandbox environment that mimics SMB customer drift.
- **Mocks/Tests**: Lacking comprehensive mocks for AWS APIs. The pr_bundle logic is only tested via basic unit tests, out-of-band.
- **Canary Strategy**: None. Bundles are run directly by the customer on their PC.
- **Missing Before Rollout**: Need an automated e2e test suite that deploys realistic 'bad' infrastructure and asserts that the PR bundles fix them without breaking adjacent mock workloads.

## Concurrency & Edge Cases
- **Concurrent Execution**: Customers run the bundle locally. The backend locks the `RemediationRunExecution` row, but there is no AWS-level locking preventing out-of-band changes.
- **Terraform State Locking**: State is kept locally in the `.tfstate` file on the customer's PC during the group run. No central S3 backend state locking is utilized, risking orphaned states if the PC dies.
- **Conflicts**: High risk for S3 bucket policies or global account settings if multiple developers within the same SMB try to run different bundles simultaneously.
- **Rate Limits & Partial Failures**: Terraform handles basic AWS rate limits, but partial failures leave the local state file out of sync with the backend.

## Compliance & Risk Boundaries
- **Never Fully Automated**: IAM.4 (Root Access Keys), S3.5 (Bucket Policies), EC2.53 (Security Group 0.0.0.0/0 Revoke)
- **Needs Audit Trails**: All changes need an audit trail, but the current system does not log the exact diff applied to the backend for auditing purposes (only simple status).
- **IAM.4 Safely Gated**: No, IAM.4 requires manual console access which is completely out of band and not observable.
- **Manual-Only Default**: EC2.53 (Security Group), CloudTrail.1 (Complex deps), Config.1 (Complex deps), S3.5 (Bucket policies)
- **SOC2 Evidence Sufficient**: No. We lack the actual applied terraform plan diffs in the database. Customer approval is also out-of-band.

## Field Execution Risks (Customer PC + Terraform)
### Local Terraform version mismatch
- **Implementation Status**: Worker relies on the terraform binary installed on the executing PC.
- **Risk Level**: Medium
- **Detection Method**: Terraform init/plan fails with syntax errors.
- **User Impact**: Remediation won't run.
- **Recommended Guardrail**: Embed a version constraint in the generated `providers.tf` (e.g., `required_version = ">= 1.3.0"`).

### Provider version mismatch
- **Implementation Status**: No `.terraform.lock.hcl` is distributed with the bundle.
- **Risk Level**: Medium
- **Detection Method**: Different provider versions downloaded, potentially causing behavioral drift.
- **User Impact**: Unpredictable resource mapping changes.
- **Recommended Guardrail**: Pin the exact AWS provider version in `providers.tf`.

### Missing/misconfigured backend state locking
- **Implementation Status**: State is entirely local to the temp directory on the customer PC.
- **Risk Level**: High
- **Detection Method**: Customer PC reboots during apply; next run attempts to recreate resources instead of updating them.
- **User Impact**: Duplicate resources (e.g., trying to create a second CloudTrail bucket) or complete failure to manage existing changes.
- **Recommended Guardrail**: Transition to a managed remote state (e.g., S3 + DynamoDB locking) managed by the SaaS, or generate ephemeral CloudFormation instead.

### Interrupted applies / partial applies
- **Implementation Status**: The python worker spawns a subprocess for `terraform apply`. If the user hits Ctrl+C or the machine sleeps, it hard-kills the process.
- **Risk Level**: High
- **Detection Method**: Incomplete AWS resources; `terraform.tfstate` might be corrupted.
- **User Impact**: Stranded resources or locked state requiring manual state surgery.
- **Recommended Guardrail**: Catch interrupt signals, safely drain terraform, and output an exact recovery command.

### Wrong credentials / wrong AWS account or region
- **Implementation Status**: Relies heavily on ambient environment variables (AWS_PROFILE, AWS_ACCESS_KEY_ID).
- **Risk Level**: Critical
- **Detection Method**: Terraform apply creates resources in `us-east-1` instead of `eu-west-1`, or against Account A instead of Account B.
- **User Impact**: Applying security configurations to the wrong environment entirely.
- **Recommended Guardrail**: Inject `allowed_account_ids = ["<target_id>"]` into the `aws` provider block in `providers.tf`.


## Test Environment Maturity

## Concurrency and Edge Cases

## Compliance / Risk Boundaries

## Field Execution Risks (Customer PC + Terraform)

# Guardrails and Rollout Recommendations

# Definition of “Safe” and Failure-Rate Targets

# Cross-Cutting Platform Improvements

# 30 / 60 / 90 Day Plan

# Changelog

- `{timestamp}` - Task 0 created the files and initialized the schema
- `2026-02-24T17:50:02.074691` - Task 1: Built remediation inventory mapping to terraform implementations.
- `2026-02-24T17:54:33.040239` - Task 2: Performed safety assessment and scoring for all remediations.
- `2026-02-24T17:57:29.571909` - Task 3: Performed reliability and success rate assessment for all remediations.
- `2026-02-24T17:59:40.153150` - Task 4: Performed failure mode analysis mapping IAM and operational risks for each remediation.
- `2026-02-24T18:08:32.597777` - Task 5: Assessed platform-level unknowns, test maturity, compliance boundaries, and local terraform field execution risks.
- `2026-02-24T18:11:36.100038` - Task 6: Documented platform guardrails, rollout recommendations per control, and definitions of safe targets.
- `2026-02-24T18:17:09.145867` - Task 7: Final Report & Sign-Off. Synthesized executive summary, cross-cutting platform improvements, and 30/60/90 day plan.
- `2026-02-24T18:20:37.022760` - QA Audit: Performed QA review of all outputs, verified consistency, and documented minor issues and corrections.
