# Selected Actions

These are the six live synthetic actions used for the P2.1/P2.2 assertions.

| Purpose | Action ID | Title | Key live artifact |
| --- | --- | --- | --- |
| Config positive weighting case | `73097c11-174c-4597-85a2-9af793842e8d` | Synthetic Config finding with trusted threat intel | [08-action-73097c11-174c-4597-85a2-9af793842e8d.body.json](../evidence/api/08-action-73097c11-174c-4597-85a2-9af793842e8d.body.json) |
| Config no-signal comparator | `a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1` | Synthetic Config finding without trusted threat intel | [08-action-a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1.body.json](../evidence/api/08-action-a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1.body.json) |
| Config fail-closed comparator | `5acc7d0e-e361-474f-9efa-c200a0358f0d` | Synthetic Config finding with low-confidence threat intel | [08-action-5acc7d0e-e361-474f-9efa-c200a0358f0d.body.json](../evidence/api/08-action-5acc7d0e-e361-474f-9efa-c200a0358f0d.body.json) |
| Aged decay/provenance case | `18de803d-b7cd-4df8-ad30-1604dcb05cd5` | Synthetic Config finding with aged trusted threat intel | [08-action-18de803d-b7cd-4df8-ad30-1604dcb05cd5.body.json](../evidence/api/08-action-18de803d-b7cd-4df8-ad30-1604dcb05cd5.body.json) |
| IAM headroom/cap case | `e7764c6c-1c56-426b-8373-deacb9277c30` | Synthetic IAM finding with capped trusted threat intel | [08-action-e7764c6c-1c56-426b-8373-deacb9277c30.body.json](../evidence/api/08-action-e7764c6c-1c56-426b-8373-deacb9277c30.body.json) |
| IAM no-signal comparator | `8d5a0c7d-92d8-4a35-bcbf-07a49fbe8f13` | Synthetic IAM finding without trusted threat intel | [08-action-8d5a0c7d-92d8-4a35-bcbf-07a49fbe8f13.body.json](../evidence/api/08-action-8d5a0c7d-92d8-4a35-bcbf-07a49fbe8f13.body.json) |

## UI Surfaces Checked

- Actions list surface: [01-actions-list.png](../evidence/ui/01-actions-list.png)
- Trusted-config action drawer: [02-action-detail-trusted-config.png](../evidence/ui/02-action-detail-trusted-config.png)

The UI list shows all six synthetic actions. The trusted-config action drawer shows the live title and `Priority 26`, but it does not surface the API provenance fields (`CVE`, source label, decay, or `score_factors[].provenance[]`).
