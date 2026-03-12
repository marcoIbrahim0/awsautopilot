# P1.4 Approval Gate Summary

- Safe invalid escalation exercised:
  - Attempted to create a `direct_fix` remediation run for action `442e46ac-f31c-4242-82ca-9e47081a3adb`.
  - Reused strategy `snapshot_block_all_sharing`, which live remediation options declare as `pr_only`.
- Observed live behavior:
  - API rejected the request with `400`.
  - Error detail: strategy requires `pr_only` but received `direct_fix`.
  - Valid PR path still worked during this run:
    - repo-targeted PR-only run creation returned `201`
    - resulting run reached `success`
- Limitation:
  - No live evidence of the P1.4-specific March 12 worker approval artifact or `remediation_mutation_blocked` audit event was observed.
  - Current API/worker runtime images are still `20260311T224136Z`, which predates the March 12 P1 implementation entries.

Supporting evidence:
- `../evidence/api/remediation-options-442e46ac.body.json`
- `../evidence/api/p1-4-blocked-direct-fix-attempt-442e46ac.body.json`
- `../evidence/api/p1-3-run-create-0ca64b94.body.json`
- `../evidence/api/p1-3-run-detail-9e193ab2.body.json`
- `../evidence/api/runtime-api-function.json`
- `../evidence/api/runtime-worker-function.json`
