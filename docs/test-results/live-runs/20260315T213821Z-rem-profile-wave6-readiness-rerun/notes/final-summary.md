# Remediation-profile Wave 6 blocker-closure rerun summary

- Run ID: `20260315T213821Z-rem-profile-wave6-readiness-rerun`
- Date (UTC): `2026-03-15T21:38:21Z`
- Environment used: `local master against resumed isolated runtime`
- Branch tested: `master`
- Exact HEAD tested: `1039467ef3ae84ea1f99fbca7ee6dc25be813f0b`
- AWS accounts and regions:
  - SaaS queue/runtime account `029037611564` in `eu-north-1`
  - Isolated AWS test account `696505809372` in `eu-north-1` and `us-east-1`
- Fresh/live data note: `Continuation of the March 15 environment-readiness runtime with fresh post-seeding recompute evidence captured in the same package.`
- Supported execution model exercised: `customer-run PR bundles only; public SaaS-managed PR-bundle plan/apply remained archived`
- Wave 6 complete: `no`
- Final Wave 6 E2E gate executed: `no`

Related notes:

- [Family readiness matrix](./family-readiness-matrix.md)
- [AWS cleanup summary](./aws-cleanup-summary.md)
- Prior baseline package: [`../20260315T201821Z-rem-profile-wave6-environment-readiness/notes/final-summary.md`](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260315T201821Z-rem-profile-wave6-environment-readiness/notes/final-summary.md)

## Readiness outcome

- Families now fully ready for executable and downgrade/manual proof:
  - `EC2.53`
  - `IAM.4`
  - `S3.2`
  - `S3.5`
  - `S3.9`
  - `CloudTrail.1`
  - `Config.1`
- Families now executable-ready only:
  - `S3.11`
- Families still blocked:
  - `S3.15`
- All nine Wave 6 families finally ready for the full live gate: `no`
  - Exact reason: `S3.11` still has no truthful downgrade-ready failing live case under current AWS lifecycle semantics, and `S3.15` still has no compatible live Security Hub control/finding mapping to the product's SSE-KMS family.

## Root cause and closure status per remaining family

| Family | Root cause | Fresh rerun evidence | Outcome |
| --- | --- | --- | --- |
| `S3.2` | The live bucket-scoped failing control currently surfaces as `S3.8`, not `S3.2`. The product already canonicalizes `S3.8` to the `S3.2` family, but the saved post-seeding action snapshot was stale and had not captured the two new bucket-scoped groups. | Post-recompute action inventory now contains bucket-scoped canonical `S3.2` actions `1166ca21-3d37-4bfc-96d8-4362bacf6f47` and `540f1cd9-1087-46f8-ae79-dcf746acf206`. Preview kept the exec bucket `deterministic_bundle`, downgraded the website bucket to `manual_guidance_only`, and run `726e95b9-c33c-4bf6-8f27-ccfe0e84b882` persisted `deterministic_bundle`. | `Closed` |
| `S3.5` | Preview already classified the seeded bucket-scoped case as executable, but create/run detail re-escalated it to `review_required_bundle` because create-time support-tier preservation did not whitelist the S3.5 strategy IDs. | Existing executable run `0c7045dd-3745-4bce-b452-e796ce4b67a8` for action `9c67856d-10d4-4359-aef2-059fb3be9edc` now persists `resolution.support_tier = deterministic_bundle`. A separate live review probe on account-scoped action `230d6326-f361-4a57-b38a-7be3a16ca99b` downgrades truthfully when bucket identity and merge-safe preservation evidence are absent. | `Closed` |
| `S3.11` | Current live lifecycle findings materialize on enabled control `S3.13`, not the older direct `S3.11` control semantics. Product materialization needed an alias back to canonical family `S3.11`. | Existing executable run `c2aab0c4-ed7d-4320-a7d7-34e6c059f2b1` for action `3b03726e-a29f-473c-a7ae-ecac0f1ee1c5` persists `deterministic_bundle`. Review bucket `security-autopilot-w6-envready-s311-review-696505809372` has lifecycle configured and currently returns `S3.13 PASSED`, so no failing downgrade-ready action exists to materialize. | `Partially closed` |
| `S3.15` | The isolated account still has no current enabled Security Hub control/finding that truthfully maps to the product's `s3_bucket_encryption_kms` family semantics. | Fresh control inventory still shows only `S3.13`, `S3.2`, and `S3.8` enabled. Fresh `S3.15` findings remain empty, and post-seeding actions still contain no `s3_bucket_encryption_kms` action. | `Still blocked by live AWS/product drift` |

## Highest-signal evidence

| Area | Fresh rerun evidence | Impact |
| --- | --- | --- |
| `S3.2` executable | Action `1166ca21-3d37-4bfc-96d8-4362bacf6f47` on `arn:aws:s3:::security-autopilot-w6-envready-s315-exec-696505809372` previews and persists as `deterministic_bundle`; run `726e95b9-c33c-4bf6-8f27-ccfe0e84b882` completed successfully. | `S3.2` now has a real bucket-scoped executable-ready proof path backed by live AWS findings and runtime probes. |
| `S3.2` downgrade | Action `540f1cd9-1087-46f8-ae79-dcf746acf206` on `arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372` downgrades to `manual_guidance_only` because website hosting is enabled. | The family still fails closed for unsafe public-access hardening cases. |
| `S3.5` executable | Run `0c7045dd-3745-4bce-b452-e796ce4b67a8` for action `9c67856d-10d4-4359-aef2-059fb3be9edc` now records `resolution.support_tier = deterministic_bundle` all the way through run detail. | The preview/create/run-detail mismatch is closed. |
| `S3.5` downgrade | Account-scoped action `230d6326-f361-4a57-b38a-7be3a16ca99b` downgrades to `review_required_bundle` because no bucket identifier or merge-safe bucket-policy preservation evidence can be derived. | The family still fails closed when evidence is under-proven. |
| `S3.11` executable-only truth | Action `3b03726e-a29f-473c-a7ae-ecac0f1ee1c5` and run `c2aab0c4-ed7d-4320-a7d7-34e6c059f2b1` prove live `S3.13` lifecycle findings now materialize as canonical `S3.11` executable actions. | Product executable path is restored without changing the public family/control contract. |
| `S3.11` downgrade impossibility | Review bucket lifecycle exists and Security Hub reports `S3.13 PASSED`; no post-seeding lifecycle action exists for `arn:aws:s3:::security-autopilot-w6-envready-s311-review-696505809372`. | There is still no truthful downgrade-ready failing case for `S3.11` under current live AWS semantics. |
| `S3.15` mismatch | Fresh control inventory still lacks a live SSE-KMS family control, `S3.15` findings remain empty, and no `s3_bucket_encryption_kms` action exists post-seeding. | `S3.15` must remain blocked rather than being marked ready from non-Security-Hub shadow data. |

## Credential-path note

- Product/runtime read-path proof remains role-based and is evidenced by the rerun worker logs already captured in this package:
  - `Assuming role arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
  - `Successfully assumed role arn:aws:iam::696505809372:role/CodexP2SecurityHubImportRole`
- Direct customer-side AWS CLI truth checks in this rerun used local profile `test28-root`.
  - Direct `AssumeRole` from that root profile to the import role is not allowed by the role trust policy, so the role-based product read path and the customer-side AWS truth path are evidenced separately.

## Net conclusion

- The remaining code blockers from the March 15 environment-readiness pass are closed for `S3.2` and `S3.5`.
- `S3.11` is now executable-ready, but not downgrade-ready, because current live AWS lifecycle semantics only fail buckets that lack lifecycle configuration.
- `S3.15` remains blocked by a live AWS/product control-family mismatch.
- Final live-gate readiness after this rerun is `7/9` fully ready families, `1/9` executable-only family, and `1/9` still blocked family.
