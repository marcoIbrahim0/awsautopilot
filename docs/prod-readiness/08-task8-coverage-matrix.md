# 08 Task 8 Coverage Matrix

## DELIVERABLE 1 — COVERAGE MATRIX

| Control ID | Architecture | Group A Resource | Group C Resource | Group B Resource | Adversarial Scenario |
|---|---|---|---|---|---|
| S3.1 | Architecture 1 | MISSING | arch1_account_pab_c | MISSING | basic coverage only — no adversarial validation |
| SecurityHub.1 | Architecture 2 | MISSING | arch2_securityhub_account_c | MISSING | basic coverage only — no adversarial validation |
| GuardDuty.1 | Architecture 2 | MISSING | arch2_guardduty_detector_c | MISSING | basic coverage only — no adversarial validation |
| S3.2 | Architecture 1 | arch1_bucket_website_a1 | arch1_bucket_ingest_c | arch1_bucket_evidence_b1 | A1, B1 |
| S3.4 | Architecture 1 | MISSING | arch1_bucket_ingest_c | MISSING | basic coverage only — no adversarial validation |
| EC2.53 | Architecture 1 | arch1_sg_dependency_a2 | arch1_vpc_main | arch1_sg_app_b2 | A2, B2 |
| CloudTrail.1 | Architecture 2 | MISSING | arch2_cloudtrail_main_c | MISSING | basic coverage only — no adversarial validation |
| Config.1 | Architecture 2 | MISSING | arch2_config_delivery_channel_c | MISSING | basic coverage only — no adversarial validation |
| SSM.7 | Architecture 2 | MISSING | arch2_ssm_sharing_block_c | MISSING | basic coverage only — no adversarial validation |
| EC2.182 | Architecture 2 | MISSING | arch2_snapshot_block_public_access_c | MISSING | basic coverage only — no adversarial validation |
| EC2.7 | Architecture 2 | MISSING | arch2_ebs_default_encryption_c | MISSING | basic coverage only — no adversarial validation |
| S3.5 | Architecture 1 | arch1_bucket_policy_website_a1 | arch1_bucket_policy_ingest_c | arch1_bucket_policy_evidence_b1 | A1, B1 |
| IAM.4 | Architecture 2 | arch2_shared_compute_role_a3 | arch2_root_credentials_state_c | arch2_mixed_policy_role_b3 | A3, B3 |
| S3.9 | Architecture 1 | MISSING | arch1_bucket_logging_target_c | MISSING | basic coverage only — no adversarial validation |
| S3.11 | Architecture 1 | MISSING | arch1_bucket_ingest_c | MISSING | basic coverage only — no adversarial validation |
| S3.15 | Architecture 1 | MISSING | arch1_bucket_ingest_c | MISSING | basic coverage only — no adversarial validation |
| S3.3 | Architecture 1 | arch1_bucket_website_a1 | arch1_bucket_ingest_c | arch1_bucket_evidence_b1 | A1, B1 |
| S3.8 | Architecture 1 | arch1_bucket_website_a1 | arch1_bucket_ingest_c | arch1_bucket_evidence_b1 | A1, B1 |
| S3.17 | Architecture 1 | arch1_bucket_website_a1 | arch1_bucket_ingest_c | arch1_bucket_evidence_b1 | A1, B1 |
| EC2.13 | Architecture 1 | arch1_sg_dependency_a2 | arch1_vpc_main | arch1_sg_app_b2 | A2, B2 |
| EC2.18 | Architecture 1 | arch1_sg_dependency_a2 | arch1_vpc_main | arch1_sg_app_b2 | A2, B2 |
| EC2.19 | Architecture 1 | arch1_sg_dependency_a2 | arch1_vpc_main | arch1_sg_app_b2 | A2, B2 |
| RDS.PUBLIC_ACCESS | Architecture 2 | MISSING | arch2_rds_primary_c | MISSING | basic coverage only — no adversarial validation |
| RDS.ENCRYPTION | Architecture 2 | MISSING | arch2_rds_primary_c | MISSING | basic coverage only — no adversarial validation |
| EKS.PUBLIC_ENDPOINT | Architecture 2 | MISSING | arch2_eks_cluster_c | MISSING | basic coverage only — no adversarial validation |
| ARC-008 | N/A (infra metadata only) | MISSING | MISSING | MISSING | basic coverage only — no adversarial validation |

### COVERAGE GAP

Controls missing one or more required Group A/B/C resources (cross-checked against `08-task1-resource-inventory.md`):

- S3.1 — missing Group A and Group B
- SecurityHub.1 — missing Group A and Group B
- GuardDuty.1 — missing Group A and Group B
- S3.4 — missing Group A and Group B
- CloudTrail.1 — missing Group A and Group B
- Config.1 — missing Group A and Group B
- SSM.7 — missing Group A and Group B
- EC2.182 — missing Group A and Group B
- EC2.7 — missing Group A and Group B
- S3.9 — missing Group A and Group B
- S3.11 — missing Group A and Group B
- S3.15 — missing Group A and Group B
- RDS.PUBLIC_ACCESS — missing Group A and Group B
- RDS.ENCRYPTION — missing Group A and Group B
- EKS.PUBLIC_ENDPOINT — missing Group A and Group B
- ARC-008 — missing Group A, Group B, and Group C

## DELIVERABLE 2 — PR PROOF VALIDATION CHECKLIST

| Resource | Architecture | C1 Scope | C2 Validation | C3 Traffic | C4 Rollback | C5 Preserved | Pass/Fail |
|---|---|---|---|---|---|---|---|
| arch1_sg_dependency_a2 | Architecture 1 | MISSING | MISSING | MISSING | MISSING | N/A | FAILING |
| arch1_bucket_evidence_b1 | Architecture 1 | MISSING | MISSING | MISSING | MISSING | MISSING | FAILING |
| arch2_shared_compute_role_a3 | Architecture 2 | MISSING | MISSING | MISSING | MISSING | N/A | FAILING |
| arch2_mixed_policy_role_b3 | Architecture 2 | MISSING | MISSING | MISSING | MISSING | MISSING | FAILING |

## VALIDATION SUMMARY

- Total controls: 26
- Controls with full Group A/B/C coverage: 10
- Controls with adversarial validation: 10
- Controls with basic coverage only: 16
- Coverage gaps (missing any group): S3.1, SecurityHub.1, GuardDuty.1, S3.4, CloudTrail.1, Config.1, SSM.7, EC2.182, EC2.7, S3.9, S3.11, S3.15, RDS.PUBLIC_ACCESS, RDS.ENCRYPTION, EKS.PUBLIC_ENDPOINT, ARC-008
- PR targets PASSING: 0 of 4
- PR targets FAILING:
  - arch1_sg_dependency_a2 (missing: C1 Scope, C2 Validation, C3 Traffic, C4 Rollback)
  - arch1_bucket_evidence_b1 (missing: C1 Scope, C2 Validation, C3 Traffic, C4 Rollback, C5 Preserved)
  - arch2_shared_compute_role_a3 (missing: C1 Scope, C2 Validation, C3 Traffic, C4 Rollback)
  - arch2_mixed_policy_role_b3 (missing: C1 Scope, C2 Validation, C3 Traffic, C4 Rollback, C5 Preserved)
