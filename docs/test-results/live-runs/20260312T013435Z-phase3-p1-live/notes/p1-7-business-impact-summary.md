# P1.7 Business Impact Summary

- API observations:
  - `GET /api/actions` returned actions with no additive `business_impact`.
  - `GET /api/actions?group_by=batch` returned batch rows with no additive `business_impact`.
  - `GET /api/actions/{id}` for both representative actions returned `business_impact: null`.
- UI observations:
  - `Create PR Bundle` selection table does not show matrix labels or criticality columns.
  - `PR Bundle Summary` does not show the documented `By matrix cell` block or condensed matrix labels.
- Result:
  - Live production does not currently expose the documented Phase 3 P1.7 payload or UI surfaces.

Supporting evidence:
- `../evidence/api/04-actions.body.json`
- `../evidence/api/p1-7-actions-batch.body.json`
- `../evidence/api/p1-7-action-detail-known-442e46ac-f31c-4242-82ca-9e47081a3adb.body.json`
- `../evidence/api/p1-7-action-detail-unknown-3301b44c-8846-49c2-9f27-823e6a77e559.body.json`
- `../evidence/ui/p1-7-pr-bundle-create-matrix.png`
- `../evidence/ui/p1-7-pr-bundle-summary-matrix.png`
