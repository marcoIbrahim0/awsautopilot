# Selected Actions

- Graph-ready anchor candidate:
  - Action `442e46ac-f31c-4242-82ca-9e47081a3adb`
  - Type `ebs_snapshot_block_public_access`
  - Why selected: live action detail still shows `context_incomplete=false`, making it the best candidate for graph-backed context if P1.2 were deployed.
- Graph fallback candidate:
  - Action `3301b44c-8846-49c2-9f27-823e6a77e559`
  - Type `cloudtrail_enabled`
  - Why selected: live action detail shows `context_incomplete=true`, making it the best fallback candidate.
- PR-capable candidate:
  - Action `0ca64b94-9dcb-4a97-91b0-27b0341865bc`
  - Type `ebs_default_encryption`
  - Why selected: safe PR-only path already validated previously on live and still exposes PR strategies in remediation options.
- Recommendation / matrix candidate:
  - Reused `0ca64b94-9dcb-4a97-91b0-27b0341865bc`
  - Reason: low-risk PR-capable action with stable remediation-options output.
- Similar-risk / different-criticality pair:
  - Not available on live because no `business_impact` payload is exposed in `/api/actions` or `/api/actions?group_by=batch`.
- Integration candidate:
  - Not available on live because `GET /api/integrations/settings` returns `404 Not Found`.

Supporting evidence:
- `../evidence/api/action-442e46ac.body.json`
- `../evidence/api/action-3301b44c.body.json`
- `../evidence/api/action-0ca64b94.body.json`
- `../evidence/api/p1-3-remediation-options-0ca64b94.body.json`
- `../evidence/api/p1-5-settings-list.body.json`
