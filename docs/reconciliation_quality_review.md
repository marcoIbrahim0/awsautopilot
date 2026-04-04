# Reconciliation Quality Review

Cross-reference:
- [E2E no-UI agent debug reference](runbooks/e2e-no-ui-agent-debug-reference.md)
- [Item 17 medium/low-confidence control coverage plan](prod-readiness/17-medium-low-confidence-control-coverage-plan.md)

Scope audited:
- `backend/workers/services/inventory_reconcile.py` (all collector functions currently present)
- `backend/workers/services/shadow_state.py` (shadow overlay + promotion join behavior)
- `backend/config.py` (control-plane promotion guardrail settings)
- Effective authoritative control list from `backend/.env` and `backend/workers/.env`
- Collector naming note: S3 account-level logic (`S3.1`) is implemented inside `_collect_s3_buckets`; `_collect_s3_account` does not exist in current code.
- Collector coverage note: `_collect_securityhub_account` exists in current code and is routed by `collect_inventory_snapshots`.

> ⚠️ Status: This document contains historical issue narratives plus closure updates.
>
> For current Item `17` execution planning and per-control done criteria, use [`docs/prod-readiness/17-medium-low-confidence-control-coverage-plan.md`](prod-readiness/17-medium-low-confidence-control-coverage-plan.md) as the authoritative checklist.
>
> ✅ Status update (2026-03-02): Item `17` core implementation now includes explicit medium/low branch handling in `inventory_reconcile` and `control_plane_events` for normal/access-denied/partial-data/API-error outcomes with stable `status_reason` and branch-tagged `evidence_ref`.

Identity-shape observations are based on no-UI agent raw finding payloads, with the checked-in fixture copy now living at `tests/fixtures/no_ui_agent/20260220T022820Z_findings_pre_raw.json`.

## Summary Table
| Control | Collector Function | Correctness | False Positive Risk | False Negative Risk | Error Handling | Identity Shape | Overall Risk |
|---|---|---|---|---|---|---|---|
| `S3.1` | `_collect_s3_buckets` | Strong | Low | Low | Partial (`AccessDenied` -> `SOFT_RESOLVED`) | Partial (`resource_id` format differs from ingested finding shape) | Low |
| `SecurityHub.1` | Missing (`_collect_securityhub_account` not implemented) | None | High | High | Missing | Missing | High |
| `GuardDuty.1` | `_collect_guardduty_account` | Moderate | Low | Medium | Partial (silent `get_detector` failures) | Partial (`resource_id` format differs) | Medium |
| `S3.2` | `_collect_s3_buckets` | Moderate | Medium | Medium | Explicit (collector raises on hard API failures) | Partial (collector emits bucket shape only; findings can be mixed) | Medium |
| `S3.4` | `_collect_s3_buckets` | Moderate | Medium | Medium | Explicit | Partial (collector emits bucket shape only; mixed finding shape risk) | Medium |
| `EC2.53` | `_collect_ec2_security_groups` | Moderate | Medium | Medium | Explicit (except missing-group skip) | Partial (`sg-*` IDs vs ARN findings; some findings are account-scoped) | Medium |
| `CloudTrail.1` | `_collect_cloudtrail_account` | Weak | Medium | High | Silent per-trail failures (`except Exception: continue`) | Partial (`resource_id` format differs) | High |
| `Config.1` | `_collect_config_account` | Moderate | Medium | Medium | Explicit | Partial (`resource_id` format differs) | Medium |
| `SSM.7` | `_collect_ssm_account` | Moderate | Medium | Medium | Partial (broad exception -> `SOFT_RESOLVED`) | Partial (`resource_id` format differs) | Medium |
| `EC2.182` | `_collect_ebs_account` | Strong | Low | Low | Explicit (`ClientError` classification; throttle/unknown re-raised) | Match (emits both account + ARN shapes) | Low |
| `EC2.7` | `_collect_ebs_account` | Strong | Low | Low | Explicit (collector raises on API failure) | Match | Low |
| `S3.5` | `_collect_s3_buckets` + `_policy_has_ssl_deny` | Weak | High | Medium | Explicit | Partial (collector emits bucket shape only; mixed finding shape risk) | High |
| `IAM.4` | `_collect_iam_account` | Strong | Low | Low | Explicit | Partial (`resource_id` format differs) | Low |
| `S3.9` | `_collect_s3_buckets` | Strong | Low | Low | Explicit | Partial (collector emits bucket shape only; mixed finding shape risk) | Low |
| `S3.11` | `_collect_s3_buckets` | Weak | High | Medium | Explicit | Partial (collector emits bucket shape only; mixed finding shape risk) | High |
| `S3.15` | `_collect_s3_buckets` | Strong | Low | Low | Explicit | Partial (collector emits bucket shape only; mixed finding shape risk) | Low |

## Per-Control Detail
### S3.1 — S3 account-level block public access is enabled
- **AWS API used:** `s3control.get_public_access_block(AccountId=account_id)`
- **What it checks:** all 4 account PAB flags (`BlockPublicAcls`, `IgnorePublicAcls`, `BlockPublicPolicy`, `RestrictPublicBuckets`) are `true`
- **What it should check:** current field check is aligned for this control
- **False positive scenario:** none identified
- **False negative scenario:** if the read role cannot call S3 Control, status becomes `SOFT_RESOLVED` (not `RESOLVED`) even when account is compliant
- **Error handling:** `NoSuchPublicAccessBlockConfiguration` is treated as non-compliant (`OPEN`); access denied is downgraded to `SOFT_RESOLVED`; other errors raise
- **Identity shape:** emits `resource_id=<12-digit-account>`, `resource_type=AwsAccount`; observed findings commonly use `resource_id=AWS::::Account:<account_id>`, `resource_type=AwsAccount`
- **Verdict:** GOOD
- **Required fix:** none

### SecurityHub.1 — Security Hub enabled
- **AWS API used:** none (no collector currently emits this control)
- **What it checks:** nothing in reconciliation for `SecurityHub.1`
- **What it should check:** account/region Security Hub enablement (for example `securityhub.describe_hub()` with explicit handling of not-enabled vs access-denied)
- **False positive scenario:** stale prior shadow state can remain while Security Hub is disabled because no new reconciliation signal is emitted
- **False negative scenario:** compliant Security Hub state cannot be auto-resolved by reconciliation
- **Error handling:** not implemented
- **Identity shape:** not implemented
- **Verdict:** UNRELIABLE
- **Required fix:** add `securityhub` service collector and route it in `collect_inventory_snapshots`
> ✅ Status update (2026-02-22): `_collect_securityhub_account` implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`; `securityhub` added to `INVENTORY_SERVICES_DEFAULT` and to `collect_inventory_snapshots` dispatch.
> ✅ Identity shape emitted by collector: `resource_id=account_id`, `resource_type=AwsAccount` (account-scoped pattern).
> ❓ Needs verification: live shadow-join confirmation is pending next natural `SecurityHub.1` finding recurrence. Current live validation hit `already_compliant_noop` with no eligible `SecurityHub.1` finding in artifacts, so join attachment could not be observed end-to-end.

### GuardDuty.1 — GuardDuty detector enabled
- **AWS API used:** `guardduty.list_detectors()`, then `guardduty.get_detector(DetectorId=...)`
- **What it checks:** at least one detector status is `ENABLED`
- **What it should check:** same enablement check, but with pagination and explicit per-detector error classification
- **False positive scenario:** none identified
- **False negative scenario:** if `get_detector` fails for all detectors, collector silently returns `OPEN` even when an enabled detector exists
- **Error handling:** access denied on `list_detectors` -> `SOFT_RESOLVED`; `get_detector` `ClientError` is silently skipped
- **Identity shape:** emits `resource_id=<12-digit-account>`, `resource_type=AwsAccount`; observed findings use `AWS::::Account:<account_id>` + `AwsAccount`
- **Verdict:** NEEDS IMPROVEMENT
- **Required fix:** paginate `list_detectors`; classify `get_detector` failures (`AccessDenied`/throttle/not-found) instead of silent continue
> ✅ Status update (2026-02-22): ISSUE-05 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. GuardDuty detector discovery now paginates `list_detectors` via `NextToken`, per-detector `get_detector` failures are explicitly classified with `ClientError` code handling, and detector-level access denial now emits `SOFT_RESOLVED` with `state_confidence=40` and reason `inventory_access_denied_guardduty_get_detector` instead of defaulting to `OPEN`.

### S3.2 — S3 bucket public access posture
- **AWS API used:** `s3.get_bucket_location`, `s3.get_public_access_block`, `s3.get_bucket_policy_status`
- **What it checks:** `OPEN` if bucket policy is public or any bucket-level PAB flag is off
- **What it should check:** keep current check, but handle mixed Security Hub identity shapes and explicitly validate edge cases where only account-scoped finding exists
- **False positive scenario:** bucket can be marked compliant if policy status is non-public but risky bucket/object ACL posture is not represented in this path
- **False negative scenario:** account-scoped `S3.2` findings (`AwsAccount`) can miss shadow attachment because collector emits only bucket-shaped `AwsS3Bucket` evaluations
- **Error handling:** helper functions normalize not-found responses; hard AWS API failures raise
- **Identity shape:** emits bucket ARN + `AwsS3Bucket`; observed findings are mixed (`AwsS3Bucket` and `AwsAccount`)
- **Verdict:** NEEDS IMPROVEMENT
- **Required fix:** emit dual-shape evaluations (bucket + account when applicable) or canonicalize targeted finding selection to bucket shape only
> ✅ Status update (2026-02-22): ISSUE-06 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. `S3.2` now emits a dual-shape companion evaluation per bucket: existing bucket-scoped (`resource_id=arn:aws:s3:::<bucket>`, `resource_type=AwsS3Bucket`) plus account-scoped (`resource_id=account_id`, `resource_type=AwsAccount`). Both `S3.2` evaluations share identical `status`, `status_reason`, and `state_confidence`.

### S3.4 — S3 bucket default encryption enabled
- **AWS API used:** `s3.get_bucket_encryption`
- **What it checks:** `RESOLVED` if first encryption rule contains any `SSEAlgorithm` value
- **What it should check:** enforce accepted algorithms (`AES256` or `aws:kms`) and evaluate active/default rule robustly
- **False positive scenario:** malformed or unexpected first-rule algorithm value still counts as compliant because check is `algo is not None`
- **False negative scenario:** if first rule is non-default/malformed but later rule is valid, collector can mark `OPEN`
- **Error handling:** missing encryption config -> `OPEN`; hard failures raise
- **Identity shape:** emits bucket ARN + `AwsS3Bucket`; no `S3.4` sample found in current artifacts to confirm live shape parity
- **Verdict:** NEEDS IMPROVEMENT
- **Required fix:** validate algorithm against allowed set and evaluate all rules safely instead of first-rule-only
> ✅ Status update (2026-02-22): ISSUE-07 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. S3.4 compliance now requires at least one default-encryption rule with approved algorithm in `{aes256, aws:kms}` using case-insensitive matching, evaluated across all returned encryption rules (not first-rule-only).

> ❓ Needs verification: In live data, are `S3.4` findings always bucket-scoped, or mixed with account-scoped `AwsAccount` resources?

### EC2.53 — Security group allows public SSH/RDP access
- **AWS API used:** `ec2.describe_security_groups` (direct by IDs or paginated for global sweep)
- **What it checks:** any ingress rule exposing admin ports (`22`/`3389` or protocol `-1`) to `0.0.0.0/0` or `::/0`
- **What it should check:** keep current core logic, but normalize targeted `resource_ids` from Security Hub ARN format before lookup
- **False positive scenario:** none identified in current field logic
- **False negative scenario:** targeted reconcile drops valid SG ARNs because only IDs beginning with `sg-` are accepted
- **Error handling:** `InvalidGroup.NotFound` is skipped; other failures raise
- **Identity shape:** emits `resource_id=sg-*`, `resource_type=AwsEc2SecurityGroup`; observed findings include SG ARN form and some `AwsAccount` form
- **Verdict:** NEEDS IMPROVEMENT
- **Required fix:** extract SG IDs from ARN-shaped `resource_ids` before filtering, and decide explicit handling for account-scoped EC2.53 findings
> ✅ Status update (2026-02-22): ISSUE-08 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. Targeted `EC2.53` reconcile now normalizes identifiers via `_security_group_id_from_any`: raw `sg-*` IDs are accepted unchanged, ARN-form identifiers are parsed to extract the `sg-*` suffix, and malformed/unsupported identifiers are warned and dropped without raising.

### CloudTrail.1 — CloudTrail multi-region trail enabled
- **AWS API used:** `cloudtrail.describe_trails(includeShadowTrails=False)`, `cloudtrail.get_trail_status(Name=...)`
- **What it checks:** at least one multi-region trail with `IsLogging=true`
- **What it should check:** include shadow trails/home-region scenarios and do not silently ignore per-trail API errors
- **False positive scenario:** none identified
- **False negative scenario:** compliant org can be marked `OPEN` when `get_trail_status` fails or when compliant trail is only visible as a shadow trail in region scope
- **Error handling:** any `get_trail_status` error is swallowed (`except Exception: continue`)
- **Identity shape:** emits `resource_id=<12-digit-account>`, `resource_type=AwsAccount`; observed findings use `AWS::::Account:<account_id>` + `AwsAccount`
- **Verdict:** UNRELIABLE
- **Required fix:** set `includeShadowTrails=True`, classify exceptions explicitly, and fail soft (not `OPEN`) when status cannot be determined
> ✅ Status update (2026-02-22): ISSUE-02 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py` with `describe_trails(includeShadowTrails=True)`, explicit per-trail `ClientError` classification, and `SOFT_RESOLVED` + `state_confidence=40` on `AccessDenied`/`AccessDeniedException` for `get_trail_status`.

### Config.1 — AWS Config recorder enabled
- **AWS API used:** `config.describe_configuration_recorders()`, `config.describe_configuration_recorder_status()`
- **What it checks:** `RESOLVED` if at least one recorder exists and any recorder status has `recording=true`
- **What it should check:** validate recorder coverage intent (for example all supported resources and expected recorder state), not just existence + one boolean
- **False positive scenario:** one recorder reports `recording=true` while required coverage is incomplete
- **False negative scenario:** multi-recorder edge cases can fail if expected recorder is healthy but status shape is unexpected
- **Error handling:** API errors raise (shard failure)
- **Identity shape:** emits `resource_id=<12-digit-account>`, `resource_type=AwsAccount`; observed findings use `AWS::::Account:<account_id>` + `AwsAccount`
- **Verdict:** NEEDS IMPROVEMENT
- **Required fix:** validate recorder configuration fields required by control intent (not only `recording`)
> ✅ Status update (2026-02-22): `config_enable_account_local_delivery` now applies the required AWS Config delivery bucket policy before `PutDeliveryChannel` in `/Users/marcomaher/AWS Security Autopilot/backend/services/pr_bundle.py`.
> ✅ Status update (2026-02-22): ISSUE-09 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. `Config.1` now validates recorder quality beyond existence: recorder `recording=true`, recorder role ARN presence, coverage scope (`allSupported=true` or explicit resource types), and delivery channel presence/configuration. Access denial on recorder status now emits `SOFT_RESOLVED` with `state_confidence=40`.
> ✅ Audit note (2026-02-22): In S6 reporting, a shadow join miss can be misread as `already_compliant_noop` if reviewed from KPI/outcome fields alone. For no-op runs, operators should cross-check `final_report.outcome_type` with the live finding `shadow.status_normalized`; expected no-op shape is `outcome_type=already_compliant_noop` with `shadow.status_normalized=RESOLVED`.

### SSM.7 — SSM document public sharing blocked
- **AWS API used:** `ssm.get_service_setting(SettingId="/ssm/documents/console/public-sharing-permission")`
- **What it checks:** setting value in `{enabled,true,1,on}` => `OPEN`; otherwise `RESOLVED`
- **What it should check:** preserve current setting check but classify API failure types explicitly
- **False positive scenario:** none identified
- **False negative scenario:** transient API failure marks `SOFT_RESOLVED`; persistent failures can mask unresolved state
- **Error handling:** broad `except Exception` sets `supported=False` and emits `SOFT_RESOLVED`
- **Identity shape:** emits `resource_id=<12-digit-account>`, `resource_type=AwsAccount`; observed findings use `AWS::::Account:<account_id>` + `AwsAccount`
- **Verdict:** NEEDS IMPROVEMENT
- **Required fix:** replace broad catch with explicit `ClientError` code handling and separate unknown failures from unsupported API
> ✅ Status update (2026-02-22): ISSUE-10 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. SSM.7 now classifies `ClientError` explicitly: access-denied emits `SOFT_RESOLVED` (`state_confidence=40`) with reason `inventory_access_denied_ssm_get_service_setting`; unsupported-operation emits `SOFT_RESOLVED` (`state_confidence=40`) with reason `inventory_unsupported_operation_ssm_default_host_management`; `ThrottlingException` is re-raised.

### EC2.182 — EBS snapshot public sharing block enabled
- **AWS API used:** `ec2.get_snapshot_block_public_access_state()`
- **What it checks:** `State == "block-all-sharing"` => `RESOLVED`; otherwise `OPEN`; unsupported API/access denial => `SOFT_RESOLVED`
- **What it should check:** current state check and error taxonomy are aligned
- **False positive scenario:** none identified
- **False negative scenario:** none identified in current logic
- **Error handling:** explicit `ClientError` classification: unsupported-operation and access-denied emit `SOFT_RESOLVED` (`state_confidence=40`), `ThrottlingException` and unknown `ClientError` are re-raised
- **Identity shape:** emits both account shape (`AwsAccount`) and ARN shape (`AwsEc2SnapshotBlockPublicAccess`), matching observed mixed findings
- **Verdict:** GOOD
- **Required fix:** none
> ✅ Status update (2026-02-22): ISSUE-11 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. `EC2.182` now uses explicit `ClientError` classification: unsupported-operation (`UnsupportedOperation`, `UnsupportedOperationException`, `InvalidRequest`, `OperationNotSupportedException`) and access-denied (`AccessDenied`, `AccessDeniedException`) emit `SOFT_RESOLVED` with `state_confidence=40`; `ThrottlingException` and unknown errors are re-raised.

### EC2.7 — EBS default encryption enabled
- **AWS API used:** `ec2.get_ebs_encryption_by_default()`
- **What it checks:** `EbsEncryptionByDefault=true` => `RESOLVED`; else `OPEN`
- **What it should check:** current check is aligned for this control
- **False positive scenario:** none identified
- **False negative scenario:** none identified
- **Error handling:** API failures raise (no silent status flip)
- **Identity shape:** emits `resource_id=AWS::::Account:<account_id>`, `resource_type=AwsAccount`; observed findings match
- **Verdict:** GOOD
- **Required fix:** none

### S3.5 — S3 bucket enforces SSL requests
- **AWS API used:** `s3.get_bucket_policy()` parsed by `_policy_has_ssl_deny(...)`
- **What it checks:** presence of any `Deny` statement with `Condition.Bool["aws:SecureTransport"] == "false"`
- **What it should check:** validate statement scope (`Principal`, `Action`, and `Resource` coverage for both bucket and objects), not just one condition key
- **False positive scenario:** narrow deny statement on one principal/path passes while bucket still allows insecure access elsewhere
- **False negative scenario:** equivalent policy expression using alternate condition operators can be compliant but missed
- **Error handling:** missing policy => `OPEN`; malformed JSON => treated as missing policy (`OPEN`); hard failures raise
- **Identity shape:** emits bucket ARN + `AwsS3Bucket`; observed findings are mixed (`AwsS3Bucket` and `AwsAccount`)
- **Verdict:** UNRELIABLE
- **Required fix:** implement full SSL-enforcement policy evaluation with scope validation and robust policy-operator handling
> ✅ Status update (2026-02-22): ISSUE-03 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. `_policy_has_ssl_deny` now enforces case-insensitive `aws:SecureTransport=false` detection, requires action coverage (`s3:*` or both `s3:GetObject` + `s3:PutObject`), and requires both bucket and object resource coverage (`arn:aws:s3:::bucket` + `arn:aws:s3:::bucket/*`) before marking `S3.5` compliant.

### IAM.4 — IAM root access key absent
- **AWS API used:** `iam.get_account_summary()`
- **What it checks:** `SummaryMap.AccountAccessKeysPresent == 0`
- **What it should check:** current check is aligned for this control
- **False positive scenario:** none identified
- **False negative scenario:** none identified
- **Error handling:** API failures raise
- **Identity shape:** emits `resource_id=<12-digit-account>`, `resource_type=AwsAccount`; observed findings use `AWS::::Account:<account_id>` + `AwsAccount`
- **Verdict:** GOOD
- **Required fix:** none

### S3.9 — S3 bucket access logging enabled
- **AWS API used:** `s3.get_bucket_logging()`
- **What it checks:** `LoggingEnabled` present/non-empty and logging destination quality (`TargetBucket` non-empty string + `TargetPrefix` key present)
- **What it should check:** current logging-quality check is aligned
- **False positive scenario:** none identified in current logic
- **False negative scenario:** API access issues fail shard instead of emitting controlled non-authoritative status
- **Error handling:** `NoSuchBucket` => `OPEN`; other errors raise
- **Identity shape:** emits bucket ARN + `AwsS3Bucket`; observed findings are mixed (`AwsS3Bucket` and `AwsAccount`)
- **Verdict:** GOOD
- **Required fix:** none
> ✅ Status update (2026-02-22): ISSUE-12 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. S3.9 now requires `LoggingEnabled` to be present and non-empty, `TargetBucket` to be a non-empty string, and `TargetPrefix` key presence (empty string allowed). The previous presence-only `bool(LoggingEnabled)` heuristic was removed.

### S3.11 — S3 bucket lifecycle rules configured
- **AWS API used:** `s3.get_bucket_lifecycle_configuration()`
- **What it checks:** `len(Rules) > 0` => `RESOLVED`
- **What it should check:** at least one enabled rule with meaningful lifecycle action, not just rule array existence
- **False positive scenario:** one lifecycle rule exists with `Status=Disabled`, yet control is marked `RESOLVED`
- **False negative scenario:** none identified beyond API/read failure paths
- **Error handling:** missing lifecycle config => `OPEN`; other errors raise
- **Identity shape:** emits bucket ARN + `AwsS3Bucket`; observed findings are mixed (`AwsS3Bucket` and `AwsAccount`)
- **Verdict:** UNRELIABLE
- **Required fix:** evaluate rule `Status` and action content (`Expiration`/`Transitions`) before resolving
> ✅ Status update (2026-02-22): ISSUE-04 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. S3.11 now requires at least one rule with `Status=Enabled` (case-insensitive) and meaningful lifecycle action (`Expiration` or non-empty `Transitions`); the previous rule-count-only heuristic was removed.

### S3.15 — S3 bucket uses SSE-KMS by default
- **AWS API used:** `s3.get_bucket_encryption()`
- **What it checks:** evaluates all returned default-encryption rules and resolves only when at least one rule has `SSEAlgorithm == "aws:kms"` (case-insensitive)
- **What it should check:** current KMS default evaluation is aligned
- **False positive scenario:** none identified in current logic
- **False negative scenario:** none identified in current logic
- **Error handling:** missing encryption config => `OPEN`; other errors raise
- **Identity shape:** emits bucket ARN + `AwsS3Bucket`; observed findings are mixed (`AwsS3Bucket` and `AwsAccount`)
- **Verdict:** GOOD
- **Required fix:** none
> ✅ Status update (2026-02-22): ISSUE-13 implemented in `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`. `S3.15` no longer relies on first-rule-only algorithm detection; it now evaluates all default-encryption rules and resolves only when SSE-KMS (`aws:kms`, case-insensitive) is present in at least one rule.

## Prioritized Fix List
1. **[CLOSED 2026-02-22] SecurityHub.1 collector coverage.** Implemented: `_collect_securityhub_account`, `securityhub` added to supported inventory services and collector dispatch.
2. **[CLOSED 2026-02-22] CloudTrail.1 status hardening.** Implemented: `includeShadowTrails=True`, explicit per-trail `ClientError` handling, `SOFT_RESOLVED` (`state_confidence=40`) on access denial.
3. **[CLOSED 2026-02-22] S3.5 policy scope validation.** Implemented: robust SSL deny evaluation with case-insensitive condition matching, action coverage checks, and required bucket+object resource coverage.
4. **[CLOSED 2026-02-22] S3.11 lifecycle semantics.** Implemented: compliance now requires at least one enabled rule with meaningful lifecycle action (`Expiration` or non-empty `Transitions`).
5. **[CLOSED 2026-02-22] GuardDuty.1 pagination + per-detector error handling.** Implemented: paginated `list_detectors` + explicit per-detector `ClientError` classification + `SOFT_RESOLVED` (`state_confidence=40`) on detector access denial.
6. **[CLOSED 2026-02-22] S3.2 mixed identity handling.** Implemented: dual-shape `S3.2` evaluation emission (bucket + account companion) with shared status/reason/confidence.
7. **[CLOSED 2026-02-22] S3.4 algorithm validation.** Implemented: approved algorithm set `{aes256, aws:kms}` with case-insensitive matching evaluated across all encryption rules.
8. **[CLOSED 2026-02-22] EC2.53 targeted ID normalization.** Implemented: `_security_group_id_from_any` accepts raw `sg-*`, extracts `sg-*` from ARN-form identifiers, and warns/drops invalid IDs.
9. **[CLOSED 2026-02-22] Config.1 check depth.** Implemented: recorder-quality validation with role ARN requirement, resource coverage check (`allSupported` or explicit resource types), delivery channel presence/configuration, and `SOFT_RESOLVED` on recorder-status access denial.
10. **[CLOSED 2026-02-22] SSM.7 exception taxonomy.** Implemented: explicit `ClientError` classification, `SOFT_RESOLVED` on access-denied/unsupported-operation, and `ThrottlingException` re-raised.
11. **[CLOSED 2026-02-22] EC2.182 exception taxonomy.** Implemented: explicit `ClientError` classification; unsupported-operation and access-denied emit `SOFT_RESOLVED` (`state_confidence=40`), while `ThrottlingException` and unknown errors are re-raised.
12. **[CLOSED 2026-02-22] S3.9 logging validation depth.** Implemented: S3.9 now requires non-empty `TargetBucket` and `TargetPrefix` key presence (empty string allowed), replacing presence-only `bool(LoggingEnabled)` compliance.
13. **[CLOSED 2026-02-22] S3.15 effective-rule logic.** Implemented: evaluate all default-encryption rules and resolve only when SSE-KMS (`aws:kms`) is present (case-insensitive), replacing first-rule-only evaluation.
14. **[GOOD] S3.1:** no logic fix required; optional identity normalization for consistency.
15. **[GOOD] EC2.7:** no logic fix required.
16. **[GOOD] IAM.4:** no logic fix required; optional identity normalization for consistency.

## Controls Not Yet Covered by Reconciliation
- None currently in the audited scope.
- `SecurityHub.1` coverage is implemented via `_collect_securityhub_account` and routed in `collect_inventory_snapshots`.

## GitHub-Issue-Style Entries
### ISSUE-01: [UNRELIABLE] Missing SecurityHub.1 reconciliation collector
- **Control ID:** `SecurityHub.1`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:26`, `backend/workers/services/inventory_reconcile.py:1039`
- **Problem:** `SecurityHub.1` is authoritative but no collector or service dispatch exists, so reconciliation cannot produce fresh evaluations.
- **Exact code change needed:** implement `_collect_securityhub_account(session_boto, account_id, region)` using Security Hub enablement APIs, add `"securityhub"` to `INVENTORY_SERVICES_DEFAULT`, and add `if svc == "securityhub": return _collect_securityhub_account(...)` in `collect_inventory_snapshots`.

### ISSUE-02: [UNRELIABLE] CloudTrail.1 silently ignores per-trail status failures
- **Control ID:** `CloudTrail.1`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:493`, `backend/workers/services/inventory_reconcile.py:507`
- **Problem:** `includeShadowTrails=False` plus broad `except Exception: continue` can miss compliant trails and silently produce `OPEN`.
- **Exact code change needed:** call `describe_trails(includeShadowTrails=True)`, catch `ClientError` explicitly in `get_trail_status`, and emit non-authoritative (`SOFT_RESOLVED`) status when trail status cannot be determined.

### ISSUE-03: [UNRELIABLE] S3.5 compliance check is condition-existence only
- **Control ID:** `S3.5`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:185`, `backend/workers/services/inventory_reconcile.py:445`
- **Problem:** `_policy_has_ssl_deny` returns compliant if any deny statement has `aws:SecureTransport=false`, without validating principal/action/resource scope.
- **Exact code change needed:** extend `_policy_has_ssl_deny` to require wildcard principal, full S3 object+bucket resource coverage, and deny coverage for relevant actions before returning `True`.

### ISSUE-04: [UNRELIABLE] S3.11 resolves on lifecycle rule count only
- **Control ID:** `S3.11`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:158`, `backend/workers/services/inventory_reconcile.py:430`
- **Problem:** `lifecycle_rule_count > 0` can pass when all rules are disabled.
- **Exact code change needed:** parse lifecycle rules and require at least one enabled rule with lifecycle action payload (`Expiration` or `Transitions`) before setting `RESOLVED`.

### ISSUE-05: [NEEDS IMPROVEMENT] GuardDuty.1 misses detector pagination and suppresses detail errors
- **Control ID:** `GuardDuty.1`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:958`, `backend/workers/services/inventory_reconcile.py:971`
- **Problem:** `list_detectors()` is not paginated and `get_detector` failures are silently skipped.
- **Exact code change needed:** switch to paginator for `list_detectors`, capture failed detector reads in evidence, and downgrade to `SOFT_RESOLVED` when detector status cannot be authoritatively determined.
> ✅ Status update (2026-02-22): Closed. `list_detectors` now paginates via `NextToken`; per-detector `get_detector` failures are explicitly classified; `AccessDenied`/`AccessDeniedException` now emits `SOFT_RESOLVED` with `state_confidence=40` and reason `inventory_access_denied_guardduty_get_detector`.

### ISSUE-06: [NEEDS IMPROVEMENT] S3.2 identity handling is bucket-only while findings can be mixed-shape
- **Control ID:** `S3.2`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:379`
- **Problem:** collector emits only `AwsS3Bucket` evaluations, but observed findings include both `AwsS3Bucket` and `AwsAccount` shapes.
- **Exact code change needed:** emit account-shaped companion evaluation for `S3.2` (or enforce bucket-shaped target selection upstream) so shadow joins do not depend on which shape was selected.
> ✅ Status update (2026-02-22): Closed. `_collect_s3_buckets` now emits dual-shape `S3.2` evaluations per bucket (`AwsS3Bucket` + `AwsAccount`) with identical `status`, `status_reason`, and `state_confidence`.

### ISSUE-07: [NEEDS IMPROVEMENT] S3.4 accepts any non-null encryption algorithm
- **Control ID:** `S3.4`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:369`, `backend/workers/services/inventory_reconcile.py:396`
- **Problem:** compliance is `algo is not None`, which is weaker than explicit approved algorithm checks.
- **Exact code change needed:** validate `algo in {"aes256", "aws:kms"}` and evaluate effective encryption rule across all returned rules.
> ✅ Status update (2026-02-22): Closed. `_collect_s3_buckets` now evaluates S3.4 compliance across all encryption rules and only resolves when at least one rule defines `ApplyServerSideEncryptionByDefault.SSEAlgorithm` in approved set `{aes256, aws:kms}` (case-insensitive).

### ISSUE-08: [NEEDS IMPROVEMENT] EC2.53 targeted SG ARN inputs are dropped
- **Control ID:** `EC2.53`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:218`
- **Problem:** targeted path keeps only `resource_ids` starting with `sg-`, so ARN-form SG IDs are skipped.
- **Exact code change needed:** normalize each `resource_id` through SG-ID extraction before filtering and querying `describe_security_groups`.
> ✅ Status update (2026-02-22): Closed. Targeted `EC2.53` path now normalizes identifiers with `_security_group_id_from_any`; raw `sg-*` values pass through, ARN-form identifiers extract `sg-*`, and invalid identifiers are warned and dropped cleanly.

### ISSUE-09: [NEEDS IMPROVEMENT] Config.1 compliance logic is minimal
- **Control ID:** `Config.1`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:553`
- **Problem:** check only requires recorder existence + one `recording=true` status; control intent can require stricter recorder configuration quality.
- **Exact code change needed:** enrich evaluation to inspect recorder config fields (for example recording scope and expected recorder mode) and include explicit evidence keys.
> ✅ Status update (2026-02-22): Closed. `_collect_config_account` now enforces recorder-quality semantics (`recording=true`, role ARN present, `allSupported` or explicit resource type coverage, delivery channel present and configured) with detailed evidence fields; access denial on recorder status is classified as `SOFT_RESOLVED` with `state_confidence=40`.

### ISSUE-10: [NEEDS IMPROVEMENT] SSM.7 uses broad exception fallback
- **Control ID:** `SSM.7`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:898`
- **Problem:** any exception is treated as unsupported API and `SOFT_RESOLVED`, which can mask transient failures.
- **Exact code change needed:** catch `ClientError`, classify access-denied/throttle/not-found separately, and only mark unsupported when the error code confirms unsupported operation.
> ✅ Status update (2026-02-22): Closed. `_collect_ssm_account` now uses explicit `ClientError` taxonomy: access-denied and unsupported-operation map to `SOFT_RESOLVED` with `state_confidence=40`, while `ThrottlingException` is re-raised and no longer swallowed.

### ISSUE-11: [NEEDS IMPROVEMENT] EC2.182 conflates unsupported API with all failures
- **Control ID:** `EC2.182`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:633`
- **Problem:** broad exception handling sets `snapshot_supported=False` for all errors.
- **Exact code change needed:** catch `ClientError`, map unsupported-operation codes to `SOFT_RESOLVED`, and treat other failures as retryable/explicit failures.
> ✅ Status update (2026-02-22): Closed. `_collect_ebs_account` now applies explicit `ClientError` taxonomy for `EC2.182`: unsupported-operation (`UnsupportedOperation`, `UnsupportedOperationException`, `InvalidRequest`, `OperationNotSupportedException`) and access-denied (`AccessDenied`, `AccessDeniedException`) map to `SOFT_RESOLVED` with `state_confidence=40`; `ThrottlingException` and unknown errors are re-raised.

### ISSUE-12: [NEEDS IMPROVEMENT] S3.9 checks logging presence only
- **Control ID:** `S3.9`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:371`, `backend/workers/services/inventory_reconcile.py:418`
- **Problem:** `bool(LoggingEnabled)` can pass with weak logging configuration quality.
- **Exact code change needed:** validate required logging destination fields and include configuration-quality checks before resolving.
> ✅ Status update (2026-02-22): Closed. `_s3_bucket_logging_enabled` now requires `LoggingEnabled` to be a non-empty object, `TargetBucket` to be present/non-empty string, and `TargetPrefix` key presence (empty string accepted) before `S3.9` is resolved.

### ISSUE-13: [NEEDS IMPROVEMENT] S3.15 uses first-rule-only KMS evaluation
- **Control ID:** `S3.15`
- **Exact file + line:** `backend/workers/services/inventory_reconcile.py:370`, `backend/workers/services/inventory_reconcile.py:408`
- **Problem:** first-rule-only algorithm check can misclassify multi-rule encryption configurations.
- **Exact code change needed:** evaluate all effective/default encryption rules and resolve only when effective default is SSE-KMS.
> ✅ Status update (2026-02-22): Closed. `_s3_bucket_default_encryption_summary` now scans all default-encryption rules and tracks SSE-KMS presence across the full rule set; `S3.15` resolves only when at least one rule has `SSEAlgorithm=aws:kms` (case-insensitive).
