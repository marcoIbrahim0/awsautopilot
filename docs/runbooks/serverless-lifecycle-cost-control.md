# Serverless Lifecycle Cost-Control Runbook

This runbook covers the reversible serverless cost-control workflow implemented by [`scripts/serverless_lifecycle.sh`](/Users/marcomaher/AWS%20Security%20Autopilot/scripts/serverless_lifecycle.sh).

## Scope

The script targets the current serverless deployment defaults:

- Region: `eu-north-1`
- Build stack: `security-autopilot-saas-serverless-build`
- Runtime stack: `security-autopilot-saas-serverless-runtime`
- SQS stack: `security-autopilot-sqs-queues`
- Name prefix: `security-autopilot-dev`
- RDS instance: `security-autopilot-db-main`
- Env file: `config/.env.ops`
- Backup root: `backups/runtime-control/`

It manages:

- Lambda runtime and worker mappings
- API Gateway/runtime stack
- build stack and ECR images
- SQS queues
- RDS instance restore/delete from manual snapshots
- CloudTrail logging
- AWS Config recorder state
- GuardDuty detector state
- Security Hub plus previously enabled standards
- known EventBridge rules:
  - `SecurityAutopilotControlPlaneApiCallsRule-eu-north-1`
  - `SecurityAutopilotReconcileGlobalAllTenants-eu-north-1`
  - `creating-events-in-cloudwatch`

It does **not** restore:

- S3 object payloads from export/support buckets
- SQS message bodies
- Route 53, Cloudflare, or domain-registration resources
- Inspector or IAM Access Analyzer state

## Prerequisites

- AWS CLI configured for the target account/region
- Docker installed for exact image export/import during `delete` and `redeploy`
- A valid `config/.env.ops` with:
  - `DATABASE_URL`
  - `JWT_SECRET`
  - `CONTROL_PLANE_EVENTS_SECRET`

The script always sets `AWS_PAGER=""` internally to avoid interactive CLI hangs.

## Commands

### Inspect current state

```bash
./scripts/serverless_lifecycle.sh status
```

### Pause the environment

This captures a new local bundle, disables worker processing, throttles the API Lambda to `0`, stops the RDS instance, and suspends account-level security services tracked by the runbook.

```bash
./scripts/serverless_lifecycle.sh pause
```

### Delete runtime resources

This captures a fresh bundle, exports exact API/worker images to local tar files, creates a manual RDS snapshot, empties configured export/support buckets, and deletes the runtime, SQS, build, and RDS resources.

```bash
./scripts/serverless_lifecycle.sh delete --force
```

### Redeploy from a saved bundle

If `--bundle` is omitted, the newest bundle under `backups/runtime-control/` is used.

```bash
./scripts/serverless_lifecycle.sh redeploy --bundle 20260310T120000Z
```

Redeploy restores:

- build stack and ECR repositories
- exact API/worker image tags from local tar archives
- SQS stack
- RDS instance from the saved manual snapshot
- runtime stack with worker disabled first

### Re-enable runtime and account services

```bash
./scripts/serverless_lifecycle.sh enable --bundle 20260310T120000Z
```

Enable starts a stopped DB if needed, reapplies the saved runtime worker settings, re-enables the tracked account services, and validates `/health` plus `/ready`.

## Local bundle contents

Each bundle directory contains:

- `manifest.env` and `manifest.json`
- `runtime-parameters.json`
- `runtime-outputs.json`
- `build-outputs.json`
- `db-instance.json`
- `cloudtrail.tsv`
- `config-recorders.tsv`
- `guardduty.tsv`
- `eventbridge.tsv`
- `securityhub-hub.json`
- `securityhub-standards.json`
- `images/api-image.tar`
- `images/worker-image.tar`

The bundle is local-only and is ignored by git via the root [`.gitignore`](/Users/marcomaher/AWS%20Security%20Autopilot/.gitignore).

## Restore model

This workflow is reversible from the operator side because it preserves:

- the exact Lambda images as local Docker tar archives
- the RDS database as a manual DB snapshot
- the runtime stack parameters needed to redeploy the same release profile

Residual AWS costs after `delete` can still include:

- manual RDS snapshot storage
- any external/shared buckets left in place
- DNS or third-party edge services outside the script’s scope

## Related docs

- [Owner deployment guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/deployment/README.md)
- [Serverless deployment guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/deployment/infrastructure-serverless.md)
- [Runbooks index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/runbooks/README.md)
