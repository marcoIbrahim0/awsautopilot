AWS Security Autopilot — Terraform bundle

Credentials and region
--------------------
- Use your normal AWS credentials: a named profile from ~/.aws/config (e.g. default) or environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY).
- Do NOT set AWS_PROFILE to your account ID. Use a profile name (e.g. default) or leave unset to use the default profile.
- Set the region: export AWS_REGION=eu-north-1 (or your action's region).

Commands
--------
terraform init
terraform plan
terraform apply

Terraform proof metadata (C2/C5)
-------------------------------
- terraform_plan_timestamp_utc: 2026-03-18T21:13:36+00:00
- preserved_configuration_statement: The generated IaC is scoped to this control and is expected to preserve unrelated existing configuration unless a generated diff explicitly changes it.


Config.1 preflight safeguards
-----------------------------
- This bundle inspects existing AWS Config recorder and delivery-channel state before mutating settings.
- The executable Terraform path snapshots exact pre-state under `.aws-config-rollback/` before mutation and ships a bundle-local restore command at `rollback/aws_config_restore.py`.
- Recorder safety default: `overwrite_recording_group = false` preserves an existing recorder's recording group (including selective mode).
- Set `overwrite_recording_group = true` only when you explicitly want to replace existing recorder scope with all-supported recording.
- Delivery safety: if an existing delivery channel points to a different bucket, apply emits a warning before redirecting to `delivery_bucket_name`.
- Delivery fail-closed: when `create_local_bucket = false`, apply exits early if `delivery_bucket_name` is unreachable so remediation does not fail later with an ambiguous `NoSuchBucket` error.
- Rollback safety: the restore script replays the exact pre-remediation recorder, recording mode, delivery-channel, and target-bucket policy state; it fails closed if drift or non-empty created buckets make exact restoration ambiguous.


Selected strategy
-----------------
- strategy_id: config_enable_centralized_delivery
