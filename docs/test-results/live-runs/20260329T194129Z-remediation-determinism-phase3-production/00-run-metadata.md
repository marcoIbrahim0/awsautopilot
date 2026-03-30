# Run Metadata

- Run ID: `20260329T194129Z-remediation-determinism-phase3-production`
- Date (UTC): `2026-03-29`
- Surface: `https://api.ocypheris.com`
- Tenant: `Marco`
- Tenant ID: `e4e07aa8-b8ea-4c1d-9fd7-4362a2fc1195`
- Canary account: `696505809372`
- Region: `eu-north-1`
- Historical predecessor: `20260329T003200Z-remediation-determinism-phase3-production`

## Scope

- `WI-4` S3.5 apply-time policy merge status carry-forward
- `WI-5` S3.2 website-to-CloudFront private-origin production proof
- `WI-9` S3.2 OAC production proof
- `WI-10` S3.2 public-policy scrub full production proof
- `WI-11` S3.11 lifecycle status carry-forward
- Gate 3D grouped mixed-tier production proof

## Environment Notes

- Production health and readiness passed during this rerun.
- Control-plane freshness for account `696505809372` in `eu-north-1` was stale at the start of the run and was refreshed through the production synthetic-event intake path before any live scenario execution.
- The canary mutation profile for this retained run was `AWS_PROFILE=test28-root`.
- Terraform provider installation used `TF_CLI_CONFIG_FILE=/tmp/phase3-gate3-20260329T194129Z.tfrc`, pointing at the provider mirror under `~/.terraform.d/plugin-cache`.
- The canary read-role baseline remains intentionally advanced to `SecurityAutopilotReadRolePolicy` default version `v10` with `s3:GetBucketWebsite` included.
- The user temporarily disabled all four account-level S3 Public Access Block settings on account `696505809372` so `WI-10` could be seeded truthfully, and the original all-true account-level baseline was restored at the end of the run.
- The March 30 WI-5 closure follow-up used the real delegated hostname `wi5-gate3-696505809372.ocypheris.com`, Route53 hosted zone `Z081885955B6GUR4IL7E`, and Amazon-issued ACM certificate `arn:aws:acm:us-east-1:696505809372:certificate/509785ff-eef1-4071-bddc-d275f1dfa6ed`.
- The WI-5 Terraform proof used retained provider-mirror config [`scenarios/wi5/aws/terraformrc-real.tfrc`](./scenarios/wi5/aws/terraformrc-real.tfrc) and the same canary mutation profile `AWS_PROFILE=test28-root`.

## Retained Outputs

- `local-gate/` retains the exact Gate 3B pytest transcripts.
- `evidence/preflight/` retains health, readiness, auth, account, tooling, control-plane readiness, and family/group sweeps.
- `scenarios/wi5/` retains both the original March 29 certificate-blocked attempt and the March 30 successful real-certificate follow-up, including create/apply/recompute/rollback evidence and manual restoration of the website, policy, and bucket-level PAB baseline.
- `scenarios/wi9/` retains the full production OAC create/apply/rollback proof.
- `scenarios/wi10/` retains the full production public-policy-scrub proof, including:
  - the approved temporary account-level S3 Public Access Block change
  - truthful public-policy seeding
  - two surfaced current-head WI-10 bundle regressions
  - the deployed fixes and final corrected rerun
  - final AWS post-state, recompute transcript, bucket rollback, and account-level S3 Public Access Block restoration
- `scenarios/grouped/` retains:
  - the failed truthful grouped `S3.11` attempt caused by stale deleted members
  - the successful grouped `S3.2` fallback run
  - callback finalization
  - AWS post-state
  - cleanup verification
  - recompute output
