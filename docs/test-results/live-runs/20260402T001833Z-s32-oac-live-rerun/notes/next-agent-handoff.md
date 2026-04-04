# Next-Agent Handoff: Complete the live S3.2 rerun to success

## Objective

Continue from the retained `S3.2` live rerun package and drive the real grouped customer path all the way to a truthful terminal success, if possible.

The old April 1 blocker is already disproven:

- `OriginAccessControlAlreadyExists` no longer reproduced on the post-fix live rerun.

The remaining work is to close the new blockers and then re-run:

1. live recompute if needed
2. live grouped bundle generation
3. bundle download
4. local `run_all.sh`
5. callback/final group-run state

## Current retained package

- Root evidence folder:
  - `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun`
- Current summaries:
  - [final-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/notes/final-summary.md)
  - [bundle-inspection.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/notes/bundle-inspection.md)
  - [deploy-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/notes/deploy-summary.md)

## Live scope

- Account: `696505809372`
- Region: `eu-north-1`
- Action group id: `9200b6d5-b209-443f-9d78-28a4e60f6fb1`
- Strategy: `s3_migrate_cloudfront_oac_private`
- Affected action id: `1dc66e7e-efe9-4fd6-9335-3197211b289f`
- Affected bucket: `security-autopilot-dev-serverless-src-696505809372-eu-north-1`

## Important live IDs already created

### First attempt, now historical

- Group run: `b880d21e-eabc-4e93-aa2e-ffec9a84b9fc`
- Remediation run: `07e907d7-2cf0-4fbc-9c5b-31bcc888296a`
- Meaning:
  - this bundle proved the new runtime was active
  - it also exposed the now-fixed Terraform syntax regression

### Post-fix attempt

- Group run: `a42ffced-c41c-449e-9b0e-66621947b3f1`
- Remediation run: `fff01518-2143-4a26-a6f7-830a3630709f`
- Current API state:
  - still `started`
  - no callback was posted because the local run was interrupted after hanging/timeouts
- Relevant API snapshot:
  - `api/group-run-status-during-hang.json`

Do not try to turn this stuck run into the final acceptance proof. Create a fresh rerun after fixing the next blocker.

## Deploy state

- Supported deploy path already succeeded:
  - `/Users/marcomaher/AWS Security Autopilot/scripts/deploy_saas_serverless.sh`
- Current live image tag:
  - `20260402T002927Z`
- Evidence:
  - [deploy-summary.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/notes/deploy-summary.md)

## What is already fixed in code

### S3.2 bundle behavior

- `backend/services/pr_bundle.py`
  - S3.2 Terraform now ships `hashicorp/external`
  - bundles `scripts/cloudfront_oac_discovery.py`
  - uses `data "external" "cloudfront_reuse"`
  - conditionally reuses exact-match OAC/distribution only when safe
  - strips prior `AllowCloudFrontReadOnly` before re-emitting managed policy
  - keeps April 1 stale-target/create-if-missing handling intact

- `backend/services/aws_cloudfront_bundle_support.py`
  - contains the bundled CloudFront reuse discovery script content

### Runner behavior

- `backend/workers/jobs/run_all_template.sh`
- `infrastructure/templates/run_all.sh`
  - no longer treat `OriginAccessControlAlreadyExists` as duplicate-only success
  - still tolerate the intended S3.9 owned-bucket duplicate case

## Focused test status

These already passed after the syntax fix:

```bash
DATABASE_URL='postgresql+asyncpg://user:pass@localhost/db' \
DATABASE_URL_SYNC='postgresql://user:pass@localhost/db' \
DATABASE_URL_FALLBACK='postgresql+asyncpg://user:pass@localhost/db' \
DATABASE_URL_SYNC_FALLBACK='postgresql://user:pass@localhost/db' \
PYTHONPATH=. venv/bin/python -m pytest tests/test_step7_components.py -q -k 'cloudfront_oac_private or s3_2'
```

- Result: `11 passed, 161 deselected`

```bash
DATABASE_URL='postgresql+asyncpg://user:pass@localhost/db' \
DATABASE_URL_SYNC='postgresql://user:pass@localhost/db' \
DATABASE_URL_FALLBACK='postgresql+asyncpg://user:pass@localhost/db' \
DATABASE_URL_SYNC_FALLBACK='postgresql://user:pass@localhost/db' \
PYTHONPATH=. venv/bin/python -m pytest tests/test_remediation_run_worker.py -q -k 'duplicate_tolerance or run_all'
```

- Result: `1 passed, 50 deselected`

## Exact live blocker split

### Blocker A: the real affected customer action still downgrades before executable S3.2

The affected action is no longer failing on duplicate OAC creation. It now downgrades earlier because the family resolver cannot verify bucket existence from the current account context:

- retained decision file:
  - `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/bundle/retry/extracted/manual_guidance/actions/05-arn-aws-s3-security-autopilot-dev-serverless-src-1dc66e7e/decision.json`
- exact blocker text:
  - `Target bucket 'security-autopilot-dev-serverless-src-696505809372-eu-north-1' existence could not be verified from this account context (403). Do not keep the existing-bucket remediation path executable until bucket existence is proven.`

This is the real affected customer path.

### Blocker B: other executable S3.2 folders now hit a different live runtime problem

The post-fix bundle emitted executable S3.2 actions for other buckets, and those no longer hit `OriginAccessControlAlreadyExists`. Instead, local bundle execution hit:

- `Error: timeout while waiting for plugin to start`
- `ERROR: command timed out after 300s: terraform plan -input=false`
- `ERROR: command timed out after 300s: terraform apply -auto-approve`

Retained log tail:

- `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/apply/retry/run_all.tail.final.log`

## What was disproven already

### The helper script itself is not hanging

Direct live probing under `AWS_PROFILE=test28-root` worked immediately:

```bash
AWS_PROFILE=test28-root AWS_REGION=eu-north-1 python3 \
  docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/bundle/retry/extracted/executable/actions/13-arn-aws-s3-sa-wi5-site-696505809372-20260328t164-51f0f65a/scripts/cloudfront_oac_discovery.py
```

With the retained JSON stdin query from the run, it returned:

```json
{"mode": "create"}
```

Raw AWS CLI probes also returned quickly:

```bash
AWS_PROFILE=test28-root aws cloudfront list-origin-access-controls --no-cli-pager --output json
AWS_PROFILE=test28-root aws cloudfront list-distributions --no-cli-pager --output json
```

So the next executable-bundle timeout is not simply “AWS CLI hangs in the helper”.

## Best next debugging targets

### 1. Fix the real affected customer downgrade if possible

This is the highest-value path because acceptance is about the real customer action.

Investigate why the resolver/runtime sees bucket verification as `403` for:

- `security-autopilot-dev-serverless-src-696505809372-eu-north-1`

Likely code touchpoints:

- `/Users/marcomaher/AWS Security Autopilot/backend/services/remediation_runtime_checks.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/services/s3_family_resolution_adapter.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/services/remediation_profile_selection.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/services/remediation_profile_catalog.py`

You need to determine:

- whether the `403` is expected because current live role assumptions for grouped generation use a context that cannot prove bucket existence
- whether the current resolver is too conservative for this path
- whether the bucket-existence proof should use a different source already available in the live product context

### 2. If executable S3.2 still matters, debug the new provider timeout

The remaining live executable blocker appears around Terraform plus `hashicorp/external`.

High-probability areas:

- runner timeout/parallelism interaction in:
  - `/Users/marcomaher/AWS Security Autopilot/infrastructure/templates/run_all.sh`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/jobs/run_all_template.sh`
- external provider behavior under multiple parallel workspaces
- plugin cache / lockfile refresh interaction with a newly introduced provider

Useful retained evidence:

- full stdout:
  - `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/apply/retry/run_all.stdout.log`
- final tail:
  - `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/apply/retry/run_all.tail.final.log`

Strong candidate debug steps:

- rerun one executable S3.2 folder serially with:
  - `PARALLEL_BUNDLES=1`
  - or run Terraform directly inside a copied workspace
- test whether the provider timeout disappears when:
  - only one S3.2 folder runs at a time
  - the `external` data source is evaluated once in isolation
- inspect whether Terraform child processes are leaving orphaned `terraform-provider-external` processes

## Live auth / operator shortcuts

### Important auth discovery

The live API Lambda `JWT_SECRET` did not match the value from Secrets Manager during this run. Working operator tokens had to be signed with the actual Lambda environment secret.

Working local files during this run:

- live JWT secret:
  - `/tmp/ocypheris_live_jwt_secret.txt`
- minted bearer token path:
  - `/tmp/ocypheris_same_operator_token.txt`

Working operator identity:

- user id: `7c43e0b3-6e98-43af-826f-f4eeaa5af674`
- tenant id: `9f7616d8-af04-43ca-99cd-713625357b70`
- token version: `5`

If the temp files are gone, recreate the token like this:

```python
import time, jwt
from pathlib import Path

secret = Path('/tmp/ocypheris_live_jwt_secret.txt').read_text().strip()
payload = {
    'sub': '7c43e0b3-6e98-43af-826f-f4eeaa5af674',
    'tenant_id': '9f7616d8-af04-43ca-99cd-713625357b70',
    'email': 'ops@ocypheris.com',
    'token_version': 5,
    'iat': int(time.time()),
    'exp': int(time.time()) + 3600,
}
token = jwt.encode(payload, secret, algorithm='HS256')
Path('/tmp/ocypheris_same_operator_token.txt').write_text(token)
```

## Useful API artifacts already retained

- current group detail:
  - `api/group-detail.json`
- remediation options:
  - `api/remediation-options.json`
- first run create:
  - `api/create-group-run-request.json`
  - `api/create-group-run-response.json`
- retry run create:
  - `api/create-group-run-request-retry.json`
  - `api/create-group-run-response-retry.json`
- polls:
  - `api/group-run-poll.json`
  - `api/group-run-final.json`
  - `api/group-run-poll-retry.json`
  - `api/group-run-final-retry.json`
  - `api/group-run-status-during-hang.json`

## Fresh rerun recipe

After fixing the next blocker, do not reuse the stuck post-fix group run. Mint a fresh grouped run with a unique branch name and retain the new response.

### Create a fresh grouped run

Use:

- group id: `9200b6d5-b209-443f-9d78-28a4e60f6fb1`
- strategy: `s3_migrate_cloudfront_oac_private`
- `risk_acknowledged=true`
- `bucket_creation_acknowledged=true`

Pattern used successfully:

```json
{
  "strategy_id": "s3_migrate_cloudfront_oac_private",
  "risk_acknowledged": true,
  "bucket_creation_acknowledged": true,
  "repo_target": {
    "provider": "github",
    "repository": "example/security-autopilot-remediations",
    "base_branch": "main",
    "head_branch": "<UNIQUE_BRANCH_NAME>"
  }
}
```

### Poll bundle generation

Poll both:

- `get_action_group_run(group_id, group_run_id)`
- `get_remediation_run(remediation_run_id)`

Wait for bundle generation `success` / `ready`.

### Download and inspect the ZIP

Save into a new subfolder under:

- `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260402T001833Z-s32-oac-live-rerun/`

Verify:

- affected action still manual or becomes executable
- executable S3.2 folders still include:
  - `scripts/cloudfront_oac_discovery.py`
  - `data "external" "cloudfront_reuse"`
  - wrapped locals:
    - `effective_oac_id = (`
    - `effective_distribution_id = (`

### Execute locally

From the extracted bundle root:

```bash
AWS_PROFILE=test28-root AWS_REGION=eu-north-1 bash ./run_all.sh
```

Capture:

- stdout
- stderr
- final control-plane group-run state

## Acceptance condition to aim for

You need a truthful retained proof of one of:

- `PASS`
  - the affected S3.2 customer-run path succeeds end to end for the real target
- `FAIL`
  - the run still fails, but not because of `OriginAccessControlAlreadyExists`
  - and the remaining blocker is narrowly identified with retained evidence

## Most likely shortest path to closure

1. fix the bucket-verification `403` downgrade for the real affected action if that can be done safely
2. rerun fresh grouped bundle generation
3. if the affected action becomes executable, rerun locally and see whether the provider timeout is still present on that exact folder
4. only then decide whether a separate runner/external-provider hardening patch is still needed
