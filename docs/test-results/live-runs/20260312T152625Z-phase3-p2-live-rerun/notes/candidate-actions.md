# Candidate Actions

The initial graph-bypassed recompute reported `7` created action IDs, but only `6` of them are the synthetic Phase 3 P2 validation candidates.

## Created Action IDs From Recompute

| Action ID | Title on live `/api/actions` | Synthetic P2 candidate | Notes |
| --- | --- | --- | --- |
| `e7764c6c-1c56-426b-8373-deacb9277c30` | `Synthetic IAM finding with capped trusted threat intel` | Yes | IAM headroom/cap positive case |
| `8d5a0c7d-92d8-4a35-bcbf-07a49fbe8f13` | `Synthetic IAM finding without trusted threat intel` | Yes | IAM no-signal comparator |
| `73097c11-174c-4597-85a2-9af793842e8d` | `Synthetic Config finding with trusted threat intel` | Yes | Config positive case |
| `18de803d-b7cd-4df8-ad30-1604dcb05cd5` | `Synthetic Config finding with aged trusted threat intel` | Yes | P2.2 decay/provenance case |
| `5acc7d0e-e361-474f-9efa-c200a0358f0d` | `Synthetic Config finding with low-confidence threat intel` | Yes | Fail-closed low-confidence case |
| `a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1` | `Synthetic Config finding without trusted threat intel` | Yes | Config no-signal comparator |
| `202e02c7-f2c1-4c24-b81a-11168acad054` | `AWS Config should be enabled and use the service-linked role for resource recording` | No | Unrelated real action created during the same recompute |

## Live List Scores Before Cleanup

| Action ID | Title | Live score |
| --- | --- | ---: |
| `e7764c6c-1c56-426b-8373-deacb9277c30` | Synthetic IAM finding with capped trusted threat intel | `48` |
| `8d5a0c7d-92d8-4a35-bcbf-07a49fbe8f13` | Synthetic IAM finding without trusted threat intel | `46` |
| `73097c11-174c-4597-85a2-9af793842e8d` | Synthetic Config finding with trusted threat intel | `26` |
| `18de803d-b7cd-4df8-ad30-1604dcb05cd5` | Synthetic Config finding with aged trusted threat intel | `16` |
| `5acc7d0e-e361-474f-9efa-c200a0358f0d` | Synthetic Config finding with low-confidence threat intel | `16` |
| `a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1` | Synthetic Config finding without trusted threat intel | `16` |

## Post-Cleanup Open-State Check

After the cleanup ingest plus graph-bypassed recompute, the open-actions list dropped from `13` to `11`, but `4` synthetic actions remained open:

- `e7764c6c-1c56-426b-8373-deacb9277c30` — Synthetic IAM finding with capped trusted threat intel
- `8d5a0c7d-92d8-4a35-bcbf-07a49fbe8f13` — Synthetic IAM finding without trusted threat intel
- `5acc7d0e-e361-474f-9efa-c200a0358f0d` — Synthetic Config finding with low-confidence threat intel
- `a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1` — Synthetic Config finding without trusted threat intel

Artifacts:

- Recompute result: [06c-recompute-actions-graph-bypassed.json](../evidence/api/06c-recompute-actions-graph-bypassed.json)
- Initial list: [07-actions-list.body.json](../evidence/api/07-actions-list.body.json)
- Post-cleanup open list: [12-actions-open-after-cleanup.body.json](../evidence/api/12-actions-open-after-cleanup.body.json)
