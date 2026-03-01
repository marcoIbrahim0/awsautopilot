# Test 26

- Wave: 07
- Focus: Adversarial complex S3 policy preservation checks
- Status: PASS
- Severity (if issue): N/A

## Preconditions

- Identity: Tenant A admin `maromaher54@gmail.com` authenticated via `POST /api/auth/login` (`200`) and `GET /api/auth/me` (`200`).
- Tenant: `Valens` (`tenant_id=19b8d7c6-0100-421a-a084-c8b06d466837`).
- AWS account: `029037611564`.
- Region(s): `eu-north-1`.
- Runtime under test:
  - Runtime stack: `security-autopilot-saas-serverless-runtime`
  - API image: `.../security-autopilot-dev-saas-api:20260301T205539Z`
  - Worker image: `.../security-autopilot-dev-saas-worker:20260301T205539Z`
  - Runtime flags: `ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED=true`, `CONTROL_PLANE_SHADOW_MODE=false`
- Forwarder under test:
  - Stack: `SecurityAutopilotControlPlaneForwarder`
  - Rule: `SecurityAutopilotControlPlaneApiCallsRule-eu-north-1`
  - Event pattern includes `PutBucketPublicAccessBlock` and `DeleteBucketPublicAccessBlock`.
- Target resources:
  - Bucket: `arch1-bucket-evidence-b1-029037611564-eu-north-1`
  - Target action ID: `26403d52-eff4-47ce-ab52-49bd237e72f5`
  - Target finding ID (primary): `280fd5e2-6075-490f-913d-0ef52315a518`
  - Test run ID: `d310df98-6749-4200-85c3-3f15eca95177`

## Steps Executed

1. Applied deterministic adversarial setup for B1 and asserted risk-state preconditions before any open-list query.
2. Triggered pre-run `ingest + compute + reconcile` refresh.
3. Polled `status=open` S3.2 actions within SLA and captured per-poll target finding detail (`status`, `canonical_status`, `effective_status`, `shadow.status_normalized`).
4. Created PR-mode remediation run (`s3_migrate_cloudfront_oac_private`) for the same target action ID.
5. Downloaded PR bundle and executed Terraform (`init/plan/show/apply`) against AWS account.
6. Triggered post-apply `ingest + compute + reconcile`; polled refresh to completion.
7. Polled final action/finding state and linked-finding shadow/effective consistency.
8. Compared pre/post policy using legacy strict and delta-aware preservation checks.
9. Captured CloudTrail + control-plane DB evidence for pre-run reopen events and verified forwarder rule pattern.

## API/AWS Evidence

| # | Check | Expected | Observed | Artifact Path |
|---|---|---|---|---|
| 1 | Deterministic adversarial precondition | B1 risk-state confirmed before open-check | Confirmed (`adversarial_state_confirmed=true`, `statement_count=4`, `has_putobject_statement=true`, `has_source_vpc_condition=true`, PAB all false) | `evidence/api/test-26-closure-20260301T210222Z-12-adversarial-state-summary.json` |
| 2 | Track 2 pre-run visibility SLA | Target appears in `status=open` list within SLA window | Passed (`target_visible_in_open=true`, `elapsed_seconds=17`, `sla_seconds=180`) | `...-99-summary.json` |
| 3 | Finding truth transition in pre-run window | Canonical + shadow + effective should move from resolved to open after reset | Poll-1: `RESOLVED/NEW/RESOLVED/shadow=RESOLVED`; Poll-2: `NEW/NEW/NEW/shadow=OPEN` with target visible in open list | `...-122-pre-run-visibility-timeline.json`, `...-36f-target-finding-detail-pre-poll-1.json`, `...-36f-target-finding-detail-pre-poll-2.json` |
| 4 | Action linkage continuity | Same action ID should reopen; no replacement ID | Single target action ID remained consistent (`26403d52-eff4-47ce-ab52-49bd237e72f5`) | `...-123-action-linkage-summary.json`, `...-37-target-action-id.txt` |
| 5 | CloudTrail reset event name | Bucket-level PAB reset event must be observable as bucket API action | Observed `PutBucketPublicAccessBlock` for target bucket in pre-run window | `...-119-cloudtrail-put-bucket-public-access-block-window.json` |
| 6 | Control-plane ingestion for reset event | Reset event should be ingested and evaluated | `control_plane_events` row recorded `event_name=PutBucketPublicAccessBlock` and `processing_status=success` at `21:02:46Z` | `...-120-db-control-plane-events-window.json` |
| 7 | Forwarder rule correctness | Rule must match bucket-level PAB event names | Event pattern now includes `PutBucketPublicAccessBlock` and `DeleteBucketPublicAccessBlock` | `...-121-forwarder-rule-pattern.json` |
| 8 | Remediation options + auth boundary | `pr_only` strategies available, no-auth denied | Auth `200`, no-auth `401`; selected strategy `s3_migrate_cloudfront_oac_private` | `...-42-remediation-options-target.json`, `...-43-remediation-options-target-noauth.*`, `...-44-target-strategy-id.txt` |
| 9 | Run lifecycle | Run reaches terminal success | `success` | `...-51-run-detail-final.json`, `...-52-run-execution-final.json`, `...-53-run-final-status.txt` |
| 10 | Bundle download auth boundary | Auth `200`, no-auth denied | Auth `200`; no-auth `401` | `...-54-pr-bundle-download-authorized.*`, `...-55-pr-bundle-download-noauth.*` |
| 11 | Terraform execution | `init/plan/show/apply` succeed | All succeeded (`0/0/0/0`) | `evidence/aws/test-26-closure-20260301T210222Z-70-terraform-*.status` |
| 12 | Final closure | Target action + finding resolve after apply/refresh | Action resolved (`status=resolved`), finding in resolved set (`target_finding_in_resolved_final=true`) | `...-99-summary.json`, `...-110-target-action-detail-final.json`, `...-114-findings-resolved-s3-2-final.json` |
| 13 | Linked findings consistency | Linked findings report consistent resolved truth | `linked_finding_count=7`, resolved counts all `7`, `canonical_new_count=0` | `...-117-linked-findings-shadow-summary.json` |
| 14 | Policy preservation (delta-aware) | Non-risk statements preserved | Passed (`removed_non_risk=0`, `added_non_risk=0`, CloudFront rotation only) | `evidence/aws/test-26-closure-20260301T210222Z-78-policy-preservation-delta-summary.json` |
| 15 | PAB hardening | Post-apply PAB all true | Passed (`pab_hardened_post_apply=true`) | `...-76-aws-b1-public-access-block-post-apply.json`, `...-78-policy-preservation-delta-summary.json` |

## UI Evidence

| Screen/Flow | Expected | Observed | Screenshot Path |
|---|---|---|---|
| `GET https://dev.valensjewelry.com/actions` (no auth) | No-auth user must not access actions UI data | `307` redirect | `evidence/ui/test-26-closure-20260301T210222Z-ui-01-actions-route-no-auth.*` |

## Assertions

- Track 1 (blocking): PASS.
  - Run success: PASS.
  - Terraform `init/plan/show/apply`: PASS (`0/0/0/0`).
  - Final closure (`action_resolved` + `finding_resolved`): PASS.
  - Delta-aware policy preservation: PASS (`non_risk_invariance_pass=true`).
- Track 2 (visibility): PASS.
  - `target_visible_in_open=true` within SLA (`elapsed_seconds=17`, `sla_seconds=180`).
  - Reset-latency diagnostics: finding effective-open at `21s` from reset; action visible-open at `21s` from reset.
- Auth/API negative checks: PASS (`401` on no-auth run-create and bundle-download).
- UI auth boundary: PASS (`307` redirect for no-auth actions route).

## Tracker Updates

- Primary tracker section/row: Section 5 Test 26.
- Related tracker updates required: Sections 3/4/6 + Section 9 changelog.
- Section 8 checkbox impact: None.

## Notes

- Canonical evidence prefix: `test-26-closure-20260301T210222Z-*`.
- Root-cause closure verified by evidence:
  - CloudTrail emits bucket-level event names (`PutBucketPublicAccessBlock`),
  - Forwarder rule now matches those names,
  - pre-run reset event is ingested,
  - target finding/action reopens in OPEN list within SLA.
