# All-Groups PR Bundle Live Run

This retained run captures a live end-to-end PR-bundle exercise executed on March 22, 2026 UTC against tenant `Valens` account `696505809372` using local AWS mutation credentials (`AWS_PROFILE=test28-root`).

Primary artifacts:

- `summary.json` — consolidated per-group outcome summary
- `api_transcript.json` — API request/response transcript for bundle-generation and follow-up calls
- `groups_index.json` — live action-group inventory captured before execution
- `notes/final-summary.md` — human-readable outcome summary and notable failure modes

Per-group folders are numbered in sorted execution order and include:

- `options.json` when remediation options were resolved
- `remediation_run_poll_history.json` for bundle-generation polling
- `pr-bundle.zip` and extracted `bundle/` contents when bundle generation succeeded
- `local_execution.json` when local bundle execution was attempted
- `group_run_poll_history.json` and `result.json` when grouped execution status was observed

This run intentionally distinguishes three states:

1. bundle generation (`remediation_runs`)
2. reported grouped execution (`action_group_runs`)
3. later action closure, which still depends on reconciliation and AWS confirmation
