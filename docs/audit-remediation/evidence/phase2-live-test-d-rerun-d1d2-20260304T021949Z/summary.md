# Phase 2 Live Test D Rerun (D1/D2) Results

- D1: PASS
- D2: PASS
- D1a fail-closed centralized-bucket check: PASS

## Verification Outputs
- D1 recorder/channel before+after: `raw/d1_before_recorders.json`, `raw/d1_after_recorders.json`, `raw/d1_before_delivery_channels.json`, `raw/d1_after_delivery_channels.json`
- D1 fail-closed run: `raw/d1a_terraform_apply.txt`, `raw/d1a_result.json`
- D2 recorder/channel/status before+after: `raw/d2_before_recorders.json`, `raw/d2_after_recorders.json`, `raw/d2_after_recorder_status.json`, `raw/d2_before_delivery_channels.json`, `raw/d2_after_delivery_channels.json`
- D2 cleanup: `raw/cleanup_d2_stop_recorder.json`, `raw/cleanup_d2_delete_channel.json`, `raw/cleanup_d2_delete_recorder.json`, `raw/cleanup_d2_head_bucket_after.exitcode`

## Fix Validation Notes
- Region fix validated: D1 and D2 ran with ambient `AWS_REGION/AWS_DEFAULT_REGION=us-west-2`; generated local-exec commands still applied successfully in target regions (`eu-central-1`, `ap-south-1`).
- Stale/unreachable centralized delivery fix validated: centralized path now exits with explicit fail-closed message when delivery bucket is unreachable.

## Recommendation
- Decision: **GO_FOR_TASK_SCOPE**
- Reason: Config.1 rerun scope (D1/D2 + fail-closed centralized-bucket check) passed after the two targeted robustness fixes.
