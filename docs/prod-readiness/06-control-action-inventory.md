# 06 Control/Action Inventory (Consolidated from Task1-Task6 Raw Extractions)

> Scope date: 2026-02-25 historical consolidation snapshot.
>
> Current contract note (2026-03-19): current `master` exposes ReadRole-only onboarding plus customer-run PR bundles only. Historical `direct_fix` / `both` rows below preserve the extraction snapshot and should not be read as current live capability.

## Scope and constraints used
- Source files used: `06-task1-file-map.md`, `06-task2-raw-controls.md`, `06-task3-raw-action-types.md`, `06-task4-raw-id-registries.md`, `06-task5-raw-direct-fix.md`, `06-task6-raw-pr-bundle.md`
- No other project files were used for this consolidation.
- Conflict resolution rule applied: registry entry > class definition > comment.

## STEP 1 - Deduplication and conflict handling
- Duplicate control/action references across raw files were merged into one canonical row when values matched.
- Case-format conflicts were normalized to task4 registry values (more specific source):

| Conflict seen in raw files | Canonical value used | Why |
|---|---|---|
| `SECURITYHUB.1` vs `SecurityHub.1` | `SecurityHub.1` | task4 registry is authoritative mapping source |
| `GUARDDUTY.1` vs `GuardDuty.1` | `GuardDuty.1` | task4 registry is authoritative mapping source |
| `CLOUDTRAIL.1` vs `CloudTrail.1` | `CloudTrail.1` | task4 registry is authoritative mapping source |
| `CONFIG.1` vs `Config.1` | `Config.1` | task4 registry is authoritative mapping source |

- `UNKNOWN` class/field placeholders in task2 were treated as non-control metadata and excluded from confirmed control IDs.

## STEP 2 - CONFIRMED CONTROL INVENTORY

| Control ID | Control Name | AWS Service | What it checks | Action Type |
|------------|-------------|-------------|----------------|-------------|
| S3.1 | S3 account public access hardening | s3control | Account-level S3 public access block posture | historical both (pre-2026-03-19 snapshot: `direct_fix` preview mode; `pr_bundle` mode) |
| SecurityHub.1 | Enable Security Hub | securityhub | Security Hub account enablement state | historical both (pre-2026-03-19 snapshot: `direct_fix` preview mode; `pr_bundle` mode) |
| GuardDuty.1 | Enable GuardDuty | guardduty | GuardDuty detector enabled state | historical both (pre-2026-03-19 snapshot: `direct_fix` preview mode; `pr_bundle` mode) |
| S3.2 | Enforce S3 bucket public access hardening | s3 | Bucket-level public access hardening | pr-bundle |
| S3.4 | Enforce S3 bucket encryption | s3 | Bucket encryption configuration is enforced | pr-bundle |
| EC2.53 | Restrict security-group public ports | ec2 | Ingress rules restricted from public exposure | pr-bundle |
| CloudTrail.1 | Enable CloudTrail | cloudtrail | CloudTrail trail/logging enabled state | pr-bundle |
| Config.1 | Enable AWS Config recording | config | AWS Config recorder and delivery state | pr-bundle |
| SSM.7 | Block public SSM document sharing | ssm | SSM document public-sharing block setting | pr-bundle |
| EC2.182 | Restrict EBS snapshot public sharing | ec2 | EBS snapshot block-public-access state | pr-bundle |
| EC2.7 | Enable EBS default encryption | ec2 | EBS default encryption (and KMS default key path) | historical both (pre-2026-03-19 snapshot: `direct_fix` preview mode; `pr_bundle` mode) |
| S3.5 | Enforce SSL-only S3 access | s3 | Bucket policy requires TLS/SSL transport | pr-bundle |
| IAM.4 | Remove IAM root access keys | iam | Root account access keys should be absent | pr-bundle |
| S3.9 | Enable S3 bucket access logging | s3 | Bucket server access logging configuration | pr-bundle |
| S3.11 | Configure S3 bucket lifecycle | s3 | Bucket lifecycle rules present | pr-bundle |
| S3.15 | Enforce S3 bucket SSE-KMS encryption | s3 | Bucket encryption uses SSE-KMS | pr-bundle |
| S3.3 | Alias of S3.2 | s3 | Alias path mapped to same bucket public access hardening action as S3.2 | pr-bundle |
| S3.8 | Alias of S3.2 | s3 | Alias path mapped to same bucket public access hardening action as S3.2 | pr-bundle |
| S3.17 | Alias of S3.2 | s3 | Alias path mapped to same bucket public access hardening action as S3.2 | pr-bundle |
| EC2.13 | Alias of EC2.53 | ec2 | Alias path mapped to same SG public-port restriction action as EC2.53 | pr-bundle |
| EC2.18 | Alias of EC2.53 | ec2 | Alias path mapped to same SG public-port restriction action as EC2.53 | pr-bundle |
| EC2.19 | Alias of EC2.53 | ec2 | Alias path mapped to same SG public-port restriction action as EC2.53 | pr-bundle |
| RDS.PUBLIC_ACCESS | RDS instance public network exposure (inventory-only signal) | rds | RDS DB instance `PubliclyAccessible` should be `false`; `true` means non-compliant public exposure | `pr_only` (explicitly UNSUPPORTED remediation) |
| RDS.ENCRYPTION | RDS storage encryption at rest (inventory-only signal) | rds | RDS DB instance `StorageEncrypted` should be `true`; `false` means non-compliant encryption posture | `pr_only` (explicitly UNSUPPORTED remediation) |
| EKS.PUBLIC_ENDPOINT | EKS API public endpoint exposure (inventory-only signal) | eks | EKS cluster control-plane endpoint is publicly reachable from `0.0.0.0/0` or an empty public CIDR allowlist | `pr_only` (explicitly UNSUPPORTED remediation) |
| ARC-008 | DR architecture objective metadata | infrastructure/cloudformation | DR backup stack objective reference tag (`ArchitectureObjectiveId`) for audit traceability | INFRA_METADATA_ONLY (not runtime control) |

Notes:
- `ARC-008` is treated as architecture/audit metadata in DR IaC (`ArchitectureObjectiveId`) and is intentionally excluded from runtime control/action registries.
- For controls marked `historical both`, the extraction snapshot recorded mode-driven branching: direct-fix when execution mode was `direct_fix`; PR/IaC path when mode was `pr_bundle` (or `pr_only` where applicable). Current product contract exposes only the PR-bundle path.

## STEP 3 - STEP 4: CONFIRMED ACTION TYPE INVENTORY

| Action ID | Action Name | Type (historical direct-fix / pr-bundle snapshot) | AWS API or IaC change required |
|-----------|-------------|-------------------------------|-------------------------------|
| pr_only | PR-only action (unmapped/default) | pr-bundle | UNKNOWN (execution-mode/default marker only in extracted data) |
| direct_fix | historical `direct_fix` mode marker (preview path) | direct-fix | UNKNOWN (execution-mode marker only in extracted data) |
| pr_bundle | PR bundle mode | pr-bundle | UNKNOWN (execution-mode marker only in extracted data) |
| s3_block_public_access | S3 account public access hardening | historical both | API: `s3control.put_public_access_block`; IaC: `aws_s3_account_public_access_block`, `AWS::CloudFormation::WaitConditionHandle` |
| enable_security_hub | Enable Security Hub | historical both | API: `securityhub.enable_security_hub`; IaC: `aws_securityhub_account`, `AWS::SecurityHub::Hub` |
| enable_guardduty | Enable GuardDuty | historical both | API: `guardduty.create_detector`, `guardduty.update_detector`; IaC: `aws_guardduty_detector`, `AWS::GuardDuty::Detector` |
| s3_bucket_block_public_access | Enforce S3 bucket public access hardening | pr-bundle | IaC: `aws_s3_bucket_public_access_block`, `AWS::S3::Bucket` (strategy `s3_migrate_cloudfront_oac_private` adds `aws_cloudfront_origin_access_control`, `aws_cloudfront_distribution`, `aws_s3_bucket_policy`) |
| s3_bucket_encryption | Enforce S3 bucket encryption | pr-bundle | IaC: `aws_s3_bucket_server_side_encryption_configuration`, `AWS::S3::Bucket` |
| s3_bucket_access_logging | Enable S3 bucket access logging | pr-bundle | IaC: `aws_s3_bucket_logging`, `AWS::S3::Bucket` |
| s3_bucket_lifecycle_configuration | Configure S3 bucket lifecycle | pr-bundle | IaC: `aws_s3_bucket_lifecycle_configuration`, `AWS::S3::Bucket` |
| s3_bucket_encryption_kms | Enforce S3 bucket SSE-KMS encryption | pr-bundle | IaC: `aws_s3_bucket_server_side_encryption_configuration`, `AWS::S3::Bucket` |
| sg_restrict_public_ports | Restrict security-group public ports | pr-bundle | IaC: `aws_vpc_security_group_ingress_rule`, `AWS::EC2::SecurityGroupIngress` (plus Terraform `null_resource` wrapper in extracted output) |
| cloudtrail_enabled | Enable CloudTrail | pr-bundle | IaC: `aws_cloudtrail`, `AWS::CloudTrail::Trail` |
| aws_config_enabled | Enable AWS Config recording | pr-bundle | IaC: `AWS::Config::ConfigurationRecorder`, `AWS::Config::DeliveryChannel` (strategy `config_enable_account_local_delivery` includes `AWS::S3::Bucket`; Terraform output includes `null_resource`) |
| ssm_block_public_sharing | Block public SSM document sharing | pr-bundle | IaC: `aws_ssm_service_setting`, `Custom::SSMServiceSetting` (+ `AWS::IAM::Role`, `AWS::Lambda::Function`) |
| ebs_snapshot_block_public_access | Restrict EBS snapshot public sharing | pr-bundle | IaC: `aws_ebs_snapshot_block_public_access`, `AWS::EC2::SnapshotBlockPublicAccess` |
| ebs_default_encryption | Enable EBS default encryption | historical both | API: `ec2.enable_ebs_encryption_by_default`, `ec2.modify_ebs_default_kms_key_id`; IaC: `aws_ebs_encryption_by_default`, `aws_ebs_default_kms_key`, `Custom::EbsDefaultEncryption` (+ `AWS::IAM::Role`, `AWS::Lambda::Function`) |
| s3_bucket_require_ssl | Enforce SSL-only S3 access | pr-bundle | IaC: `aws_s3_bucket_policy`, `AWS::S3::BucketPolicy` |
| iam_root_access_key_absent | Remove IAM root access keys | pr-bundle | IaC: Terraform `null_resource` only in extracted PR-bundle data; no direct AWS API call extracted |

## STEP 5 - CONFIDENCE REPORT

| Item ID | Item Type | Confidence | Reason | Missing Information |
|---------|----------|-----------|--------|-------------------|
| S3.1 | control | HIGH | Found in task2 literals, task4 mapping, and task5/task6 execution data via mapped action. | None in extracted set. |
| SecurityHub.1 | control | HIGH | Found in task2 (case variant) and task4 canonical mapping plus task5/task6 action evidence. | None in extracted set. |
| GuardDuty.1 | control | HIGH | Found in task2 (case variant) and task4 canonical mapping plus task5/task6 action evidence. | None in extracted set. |
| S3.2 | control | HIGH | Found in task2, task4 mapping, and task6 IaC action output. | None in extracted set. |
| S3.4 | control | HIGH | Found in task2, task4 mapping, and task6 IaC action output. | None in extracted set. |
| EC2.53 | control | HIGH | Found in task2, task4 mapping, and task6 IaC action output. | None in extracted set. |
| CloudTrail.1 | control | HIGH | Found in task2 (case variant), task4 mapping, and task6 IaC action output. | None in extracted set. |
| Config.1 | control | HIGH | Found in task2 (case variant), task4 mapping, and task6 IaC action output. | None in extracted set. |
| SSM.7 | control | HIGH | Found in task2, task4 mapping, and task6 IaC action output. | None in extracted set. |
| EC2.182 | control | HIGH | Found in task2, task4 mapping, and task6 IaC action output. | None in extracted set. |
| EC2.7 | control | HIGH | Found in task2, task4 mapping, and both task5 API + task6 IaC action output. | None in extracted set. |
| S3.5 | control | HIGH | Found in task2, task4 mapping, and task6 IaC action output. | None in extracted set. |
| IAM.4 | control | HIGH | Found in task2, task4 mapping, and task6 action output. | Concrete historical direct-fix API path not extracted. |
| S3.9 | control | HIGH | Found in task2, task4 mapping, and task6 IaC action output. | None in extracted set. |
| S3.11 | control | HIGH | Found in task2, task4 mapping, and task6 IaC action output. | None in extracted set. |
| S3.15 | control | HIGH | Found in task2, task4 mapping, and task6 IaC action output. | None in extracted set. |
| S3.3 | control | HIGH | Found in task2 and task4 alias mapping to S3.2 action with task6 IaC output. | Alias-specific semantics not separately described. |
| S3.8 | control | HIGH | Found in task2 and task4 alias mapping to S3.2 action with task6 IaC output. | Alias-specific semantics not separately described. |
| S3.17 | control | HIGH | Found in task2 and task4 alias mapping to S3.2 action with task6 IaC output. | Alias-specific semantics not separately described. |
| EC2.13 | control | HIGH | Found in task2 and task4 alias mapping to EC2.53 action with task6 IaC output. | Alias-specific semantics not separately described. |
| EC2.18 | control | HIGH | Found in task2 and task4 alias mapping to EC2.53 action with task6 IaC output. | Alias-specific semantics not separately described. |
| EC2.19 | control | HIGH | Found in task2 and task4 alias mapping to EC2.53 action with task6 IaC output. | Alias-specific semantics not separately described. |
| RDS.PUBLIC_ACCESS | control | HIGH | Explicit unsupported decision is encoded in `backend/services/control_scope.py` and propagated in `backend/workers/services/inventory_reconcile.py` evidence metadata. | No executable remediation path by design; inventory-only visibility. |
| RDS.ENCRYPTION | control | HIGH | Explicit unsupported decision is encoded in `backend/services/control_scope.py` and propagated in `backend/workers/services/inventory_reconcile.py` evidence metadata. | No executable remediation path by design; inventory-only visibility. |
| EKS.PUBLIC_ENDPOINT | control | HIGH | Explicit unsupported decision is encoded in `backend/services/control_scope.py` and propagated in `backend/workers/services/inventory_reconcile.py` evidence metadata. | No executable remediation path by design; inventory-only visibility. |
| ARC-008 | architecture_objective | HIGH | Present as DR IaC metadata key (`ArchitectureObjectiveId`) and intentionally outside runtime control mapping paths. | None. |
| pr_only | action | LOW | Appears as mode/default in task3/task4 but without concrete task5 API or task6 IaC entry for this action ID itself. | Concrete executable change model for this ID. |
| direct_fix | action | LOW | Appears as a historical execution-mode marker in task3; not a concrete API action ID in task5 extraction. | Concrete API mapping for this ID (if intended as action). |
| pr_bundle | action | LOW | Appears as execution mode marker in task3; not a concrete IaC resource action ID in task6 extraction. | Concrete IaC mapping for this ID (if intended as action). |
| s3_block_public_access | action | HIGH | Found in task3 name, task4 control mapping, task5 API call, and task6 IaC resources. | None in extracted set. |
| enable_security_hub | action | HIGH | Found in task3 name, task4 control mapping, task5 API call, and task6 IaC resources. | None in extracted set. |
| enable_guardduty | action | HIGH | Found in task3 name, task4 control mapping, task5 API call, and task6 IaC resources. | None in extracted set. |
| s3_bucket_block_public_access | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| s3_bucket_encryption | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| s3_bucket_access_logging | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| s3_bucket_lifecycle_configuration | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| s3_bucket_encryption_kms | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| sg_restrict_public_ports | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| cloudtrail_enabled | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| aws_config_enabled | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| ssm_block_public_sharing | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| ebs_snapshot_block_public_access | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| ebs_default_encryption | action | HIGH | Found in task3 name, task4 control mapping, task5 API calls, and task6 IaC resources. | None in extracted set. |
| s3_bucket_require_ssl | action | HIGH | Found in task3 name, task4 control mapping, and task6 IaC resources. | None in extracted set. |
| iam_root_access_key_absent | action | LOW | Found in task3/task4/task6, but task6 records Terraform `null_resource` only and no direct API operation in task5. | Concrete executable API/IaC resource beyond `null_resource`. |

## STEP 6 - GAPS THAT BLOCK FULL CHARACTERIZATION

| Item | Missing information | File to read next to resolve | Gap type |
|------|---------------------|------------------------------|----------|
| pr_only | Ambiguous whether this is a UI/execution mode only or an executable action type with its own change implementation | `backend/services/action_engine.py` and `backend/routers/actions.py` | Documentation gap |
| direct_fix | Captured as a historical mode label; no concrete action-ID-level API mapping extracted under this ID | `backend/services/action_engine.py`, `backend/routers/actions.py`, `backend/workers/services/direct_fix.py` | Documentation gap |
| pr_bundle | Captured as mode label; no concrete action-ID-level IaC mapping extracted under this ID | `backend/services/action_engine.py`, `backend/routers/actions.py`, `backend/services/pr_bundle.py` | Documentation gap |
| iam_root_access_key_absent | Only Terraform `null_resource` captured in PR-bundle extract; concrete operation details absent in extracted set | `backend/services/pr_bundle.py` and `backend/workers/services/direct_fix.py` | Code gap |

## Final counts
- Total controls inventoried: 25
- Total actions inventoried: 19
- Confidence breakdown (all inventory items combined):
  - HIGH: 41
  - MEDIUM: 0
  - LOW: 4
  - MISSING: 0
- UNCLASSIFIED controls count: 0
- Gaps requiring further investigation: 4

## Stop gate
Per instruction, architecture work should not begin until there is explicit confirmation of the two inventory tables above.
