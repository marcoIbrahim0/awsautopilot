# All-Groups PR Bundle Live Run

This retained run captures a live end-to-end grouped PR-bundle exercise executed on March 22, 2026 UTC against tenant `Valens` account `696505809372` using local AWS mutation credentials (`AWS_PROFILE=test28-root`).

Primary artifacts:

- `summary.json` — consolidated per-group outcome summary
- `groups_index.json` — live action-group inventory captured before execution
- `auth_me.json` — authenticated operator context captured during the run
- `notes/final-summary.md` — human-readable outcome summary and notable failure modes

Per-group folders are numbered in sorted execution order and include:

- `group_detail.json` for the pre-run grouped-action snapshot
- `options.json` when remediation options were resolved
- `bundle_run_create.json` for grouped bundle-creation responses
- `remediation_run_poll_history.json` for bundle-generation polling when creation succeeded
- `pr-bundle.zip` and extracted `bundle/` contents when bundle generation succeeded
- `local_execution.json` when local bundle execution was attempted
- `group_run_poll_history.json` and `result.json` for grouped execution status evidence

This run intentionally distinguishes three states:

1. bundle generation (`remediation_runs`)
2. reported grouped execution (`action_group_runs`)
3. later action closure, which still depends on reconciliation and AWS confirmation
