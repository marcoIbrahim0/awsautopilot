# P1.3 Repo-Aware PR Automation Summary

- Request:
  - Created live PR-only remediation run `9e193ab2-7e08-457a-9db4-b90969a33ec8` for action `0ca64b94-9dcb-4a97-91b0-27b0341865bc`.
  - Included additive `repo_target` metadata in the create request.
- Observed live behavior:
  - The API accepted the create request with `201`.
  - The run completed successfully as a normal PR bundle run.
  - Run detail did **not** expose `diff_summary`, `rollback_notes`, `control_mapping_context`, `repo_target`, or `pr_payload`.
  - Downloaded bundle zip contained only `README.txt`, `ebs_default_encryption.tf`, and `providers.tf`.
  - No `pr_automation/` directory or repo-aware files were present.
- Verdict:
  - Current live runtime accepts the additive request field without error but silently drops the Phase 3 P1.3 repo-aware contract and artifacts.

Supporting evidence:
- `../evidence/api/p1-3-run-create-0ca64b94.request.json`
- `../evidence/api/p1-3-run-create-0ca64b94.body.json`
- `../evidence/api/p1-3-run-detail-9e193ab2.body.json`
- `../evidence/api/p1-3-run-execution-9e193ab2.body.json`
- `../evidence/api/p1-3-pr-bundle-download-9e193ab2.notes.txt`
