# Phase 3 Remediation Determinism Production Rerun

- Run ID: `20260329T194129Z-remediation-determinism-phase3-production`
- Date (UTC): `2026-03-29`
- Scope: Gate 3 Phase 3 production-only rerun (`WI-4`, `WI-5`, `WI-9`, `WI-10`, `WI-11`, grouped proof)
- Required live surface: `https://api.ocypheris.com`
- Tenant: `Marco` (`e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`)
- Canary account: `696505809372`
- Region: `eu-north-1`
- Outcome: `PASS`
- Historical predecessor: [`20260329T003200Z-remediation-determinism-phase3-production`](../20260329T003200Z-remediation-determinism-phase3-production/README.md)

## Summary

This retained package continues the March 29 Phase 3 production gate on the real production surface and, with the March 30 WI-5 follow-up retained under the same package, now closes Gate 3 in full.

What this rerun proved on production:

- Gate 3A preflight passed after refreshing control-plane freshness through the production synthetic-event path.
- Gate 3B local regression passed in full after the current-head fixes required by this rerun:
  - `backend/services/database_failover.py`
  - `backend/services/pr_bundle.py`
  - `tests/test_database_failover.py`
  - `tests/test_step7_components.py`
- `WI-9` now has full truthful production create/apply/rollback proof:
  - create response, final run detail, bundle download, Terraform `init` / `validate` / `plan` / `apply`, AWS post-state, recompute, and rollback are retained
  - rollback restored the exact pre-apply bucket policy and bucket-level public-access-block state
- `WI-10` now has full truthful production create/apply/rollback proof:
  - the user approved the temporary account-level S3 Public Access Block change by disabling all four account-level flags on account `696505809372`
  - a truthful public non-website candidate was seeded on bucket `sa-wi13-14-nopolicy-696505809372-20260328201935`
  - production options and preview resolved to the review-required public-policy-scrub branch as expected
  - the first production bundle surfaced a current-head Terraform type-shape regression for single-statement public policies, and the second surfaced an empty-policy apply bug after the scrub removed the only public statement
  - both WI-10 regressions were fixed minimally in `backend/services/pr_bundle.py`, covered in `tests/test_step7_components.py`, deployed to production, and then the final rerun completed with truthful production create, bundle download, Terraform `init` / `validate` / `plan` / `apply`, AWS post-state, recompute, and rollback
  - rollback restored the exact bucket-level public-access-block baseline, removed the seeded public policy, and restored the original account-level S3 Public Access Block settings
- Gate 3D grouped proof now has a truthful retained production pass through the allowed fallback path:
  - preferred grouped `S3.11` was attempted first and failed truthfully because the live action group still contained five deleted buckets
  - fallback grouped `S3.2` succeeded with a mixed-tier bundle containing `2` executable members and `8` metadata-only members
  - the grouped callback finalized successfully on production and both executable members were rolled back to baseline
- `WI-5` now has full truthful production create/apply/recompute/rollback proof:
  - the March 30 follow-up completed public parent-zone delegation for `wi5-gate3-696505809372.ocypheris.com`, confirmed ACM certificate `arn:aws:acm:us-east-1:696505809372:certificate/509785ff-eef1-4071-bddc-d275f1dfa6ed` reached `ISSUED`, and re-ran production preview/create with the real Route53 + ACM inputs
  - production run `ff6dea42-dbdc-42f1-996f-da437ad48e4c` generated a valid bundle and local Terraform `init` / `validate` / `plan` / `apply` all succeeded with the retained provider-mirror workaround
  - apply created CloudFront distribution `E3VUPASYW2QL80`, OAC `EDLL3VYQR916E`, Route53 `A` / `AAAA` aliases to `dxxm59bao95gt.cloudfront.net`, removed S3 website hosting, set all four bucket-level Public Access Block flags to `true`, and preserved the prior bucket policy statements while adding `AllowCloudFrontReadOnly`
  - recompute artifacts are retained for the same tenant/account scope
  - rollback destroyed the generated CloudFront, OAC, and alias records, then manually restored the captured website configuration, the original two-statement bucket policy, and the baseline bucket-level Public Access Block configuration with all four flags `false`

## Gate Decision

- Gate 3A preflight and deploy parity: `PASS`
- Gate 3B non-live regression: `PASS`
- Gate 3C required production scenarios: `PASS`
  - `WI-4`: `PASS` (authoritative prior retained proof)
  - `WI-5`: `PASS`
  - `WI-9`: `PASS`
  - `WI-10`: `PASS`
  - `WI-11`: `PASS` (authoritative prior retained proof)
- Gate 3D grouped production proof: `PASS`
- Gate 3E retained evidence: `PASS`
- Final decision: `PASS`

## Key Artifacts

- [Structured summary](./summary.json)
- [Run metadata](./00-run-metadata.md)
- [Final summary](./notes/final-summary.md)
- [Gate 3B transcripts](./local-gate/)
- [Preflight evidence](./evidence/preflight/)
- [WI-5 evidence](./scenarios/wi5/)
- [WI-5 parent-delegation handoff](./scenarios/wi5/aws/parent-delegation-handoff.md) (historical setup note retained alongside the successful follow-up)
- [WI-9 evidence](./scenarios/wi9/)
- [WI-10 evidence](./scenarios/wi10/)
- [Grouped proof evidence](./scenarios/grouped/)
