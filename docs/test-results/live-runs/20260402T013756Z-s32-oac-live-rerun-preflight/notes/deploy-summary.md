# Deploy summary

## Runtime deployment used for this rerun

- Production was already on image tag `20260402T002927Z` when the task started.
- This task deployed the preflight refactor with the supported script only:
  - `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_saas_serverless.sh`
- Successful deployment evidence:
  - image tag: `20260402T013336Z`
  - CodeBuild build id: `security-autopilot-dev-serverless-image-builder:7763bca9-556d-431d-b869-4e8a7b304f15`

## What changed in the deployed bundle path

- `S3.2` CloudFront/OAC bundles no longer invoke `hashicorp/external` through Terraform `data.external`.
- The bundled Python discovery helper now runs in runner preflight before `terraform init/plan/apply`.
- The preflight writes Terraform-ready reuse inputs into `security_autopilot.auto.tfvars.json`.
- The bundle still fails closed if safe CloudFront/OAC reuse cannot be proven.

## Post-deploy checks retained in this package

- [api/health.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/api/health.json) confirms live `/health` returned `200`.
- [api/auth-me.json](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T013756Z-s32-oac-live-rerun-preflight/api/auth-me.json) confirms authenticated `/api/auth/me` returned `200` at bundle-creation time.

## Focused validation before deploy

- `tests/test_step7_components.py -k 'cloudfront_oac_private or s3_2'` passed: `11 passed`
- `tests/test_remediation_run_worker.py -k 'timeout_guards or run_all_templates_keep_s3_9_owned_bucket_tolerance_but_fail_closed_for_oac_duplicates or group_pr_bundle_mixed_tier_layout_for_executable_and_review_required_actions or infra_run_all_template_merges_cloudfront_oac_preflight_tfvars or infra_run_all_template_fails_closed_when_cloudfront_oac_preflight_fails'` passed: `5 passed`
- Shell syntax checks passed for:
  - `/Users/marcomaher/AWS Security Autopilot/infrastructure/templates/run_all.sh`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/jobs/run_all_template.sh`
