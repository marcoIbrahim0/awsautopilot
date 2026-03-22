# Attack Path Account-Scope Live Rerun Summary

- Run ID: `20260321T185416Z-attack-path-account-scope-live-rerun`
- Date (UTC): `2026-03-21T18:54:16Z`
- Frontend: `https://ocypheris.com`
- Backend: `https://api.ocypheris.com`
- Result: `PASS`

## Scope

Close the live account-scoped attack-path issue after deploying the backend runtime that contains the fallback fix, then revalidate representative `SSM.7`, `IAM.4`, and `Config.1` actions on production.

Target account: `696505809372`

## Runtime change

Deployed the live serverless runtime with image tag:

- `20260321T185016Z`

Confirmed the live API Lambda changed from:

- previous image `20260321T182248Z`

to:

- current image `20260321T185016Z`

## Live API result after deploy

Representative live account-scoped actions now return bounded attack-path stories instead of the fail-closed relationship-context fallback:

- `SSM.7` action `e8be6f05-0e5e-4bdc-818e-f551cd62ccb5`
  - `attack_path_view.status="partial"`
  - `attack_path_view.availability_reason="bounded_context_truncated"`
- `IAM.4` action `84a23bb8-d6f7-4c1b-87ff-87f9cc7c469c`
  - `attack_path_view.status="partial"`
  - `attack_path_view.availability_reason="bounded_context_truncated"`
- `Config.1` action `7d51a23a-9af2-4a82-ae75-67561c01cf8e`
  - `attack_path_view.status="partial"`
  - `attack_path_view.availability_reason="bounded_context_truncated"`

Notable live detail:

- `score_components.relationship_context` remains `null` on these action rows
- `score_components.toxic_combinations.context_incomplete` remains `true`
- despite that, the new live attack-path builder correctly falls back to linked finding relationship context and no longer treats the toxic-combination scorer marker as an attack-path fail-closed gate

## Live UI result after deploy

Reloaded the dedicated live action-detail page for `IAM.4` action `84a23bb8-d6f7-4c1b-87ff-87f9cc7c469c`.

The rendered `Attack Path` section now shows:

- status `partial`
- bounded story text beginning:
  - `Exploitable path can reach AWS::::Account:696505809372 in the current bounded view, but some path context is truncated or unresolved.`

The old fail-closed message is no longer present on the loaded action-detail page.

## Recompute decision

No scoped recompute or relationship-context backfill was needed after deploy.

Reason:

- the live API corrected immediately once the new runtime was serving traffic
- that proves the issue was runtime logic, not stale live action rows

## Evidence

- Post-deploy browser screenshot: `/Users/marcomaher/AWS Security Autopilot/output/playwright/live-attack-path-e2e/.playwright-cli/page-2026-03-21T18-54-16-676Z.png`
- Post-deploy browser snapshot: `/Users/marcomaher/AWS Security Autopilot/output/playwright/live-attack-path-e2e/.playwright-cli/page-2026-03-21T18-54-14-319Z.yml`
- Earlier failing run summary: `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260321T184710Z-attack-path-account-scope-live-e2e/notes/final-summary.md`

## Conclusion

The live issue is closed.

Production now renders bounded `partial` attack-path stories for the affected account-scoped controls after the backend deploy, and no follow-up recompute was required.
