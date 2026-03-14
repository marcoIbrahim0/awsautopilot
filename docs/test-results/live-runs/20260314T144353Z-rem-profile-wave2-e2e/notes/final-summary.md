# Remediation-Profile Wave 2 Focused E2E Summary

- Run ID: `20260314T144353Z-rem-profile-wave2-e2e`
- Date (UTC): `2026-03-14T15:05:45Z`
- Environment used: `local`
- Branch tested: `codex/rem-profile-w2-integrate`
- Frontend URL: `http://localhost:3000`
- Backend URL: `http://127.0.0.1:8000`

## Outcome Counts

- Pass: `10`
- Fail: `0`
- Partial: `2`
- Blocked: `0`
- Skip/NA: `0`

## Highest Severity Findings

| Test / Surface | Severity | Finding | Evidence |
|---|---|---|---|
| `RPW2-01`, `RPW2-02` UI surface | `🟠 HIGH` | Local `frontend` route `/actions/[id]` hit a React hydration mismatch inside `ActionDetailDrawer`. Browser-authenticated API requests for action detail and remediation-options returned `200`, but the drawer stayed on a skeleton/blank state and blocked visual validation of remediation-options and remediation-preview. | `evidence/ui/rpw2-ui-observations.md`, `evidence/screenshots/rpw2-action-detail-hydration.png` |

## Exact Contracts Proven

- `GET /api/actions/{id}/remediation-options` still returns legacy strategy fields and now includes additive Wave 2 profile metadata fields: `profiles[]`, `recommended_profile_id`, `missing_defaults`, `blocked_reasons`, and `decision_rationale`.
- Strategy-only preview compatibility still works and exposes additive `resolution` with `profile_id` defaulted to `strategy_id`.
- Explicit valid `profile_id` is preserved on preview and create.
- Invalid `profile_id` is rejected with `400` and explicit backend error text; no silent fallback was observed.
- `POST /api/remediation-runs` for `pr_only` persists canonical `artifacts.resolution` and still mirrors `selected_strategy` plus `strategy_inputs`.
- Duplicate guard still rejects immediate duplicate create requests with `409`, `Duplicate pending run`, and `reason=duplicate_active_run`.
- `GET /api/remediation-runs/{id}` exposes both raw canonical artifacts and normalized top-level `resolution`.
- Legacy run detail compatibility hydration still synthesizes conservative `resolution` from `selected_strategy` when canonical `artifacts.resolution` is absent.
- `direct_fix` preview/create behavior stayed legacy-compatible: preview works without `profile_id`, and create remained blocked by dependency checks instead of widening into profile-driven behavior.
- No-auth, wrong-tenant, and invalid-resource probes stayed denied across remediation-options, remediation-preview, remediation-run create, and remediation-run detail.
- Tenant remediation settings admin GET/PATCH worked, and Wave 2 read-path wiring consumed `s3_access_logs.default_target_bucket_name` in remediation-options and remediation-preview.

## Exact Blockers / Gaps

- Branch runtime was not verified on a dedicated deployed endpoint, so this run used a local branch environment only.
- The local action-detail UI route could not be visually validated end to end because of the hydration mismatch described above.
- No same-tenant non-admin user existed in the test tenant, so the remediation-settings check exercised the documented admin path and read-path influence rather than a full same-tenant role matrix.

## Runtime Notes

- The local backend accepted and enqueued the `pr_only` create requests; each create would have failed with `503` if SQS enqueue failed on the create path.
- Worker pickup and migration behavior were not used as release criteria in this run because Wave 2 scope explicitly excludes queue schema v2 and worker migration validation.
- Created Wave 2 runs remained `pending` during the observation window:
  - `RPW2-05`: `9ca75043-9533-4bd0-b76e-1c0a4d522461`
  - `RPW2-06`: `624170a6-6c76-43e5-8cee-3c501759cf2d`
  - `RPW2-07`: `c1aaa1ae-ed77-4066-bb40-f905f354c5be`

## Gate Decision

- Recommended gate decision: `stop for fixes`
- Rationale: the Wave 2 API contract passed across the targeted surfaces, but the only verified runtime for this branch is local and its `/actions/[id]` UI route is currently broken by a hydration mismatch. Wave 3 should wait for that UI regression to be fixed or for a dedicated deployed branch environment to prove the issue is local-only.
