# P2.1 Weighting Summary

## Core Live Result

`P2.1` weighting is live on production at the API layer.

## Observed Comparisons

| Assertion | Observed live behavior | Status |
| --- | --- | --- |
| Trusted config signal raises score | Trusted config action `73097c11-174c-4597-85a2-9af793842e8d` scored `26`; config no-signal action `a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1` scored `16`. | PASS |
| Trusted signal is persisted inside `score_components["exploit_signals"]` | Trusted config action reports `threat_intel_points_requested=10`, `threat_intel_points_applied=10`, and one `applied_threat_signals[]` entry with `source=cisa_kev`, `identifier=CVE-2026-9001`, `confidence=1.0`, `timestamp=2026-03-12T15:20:00+00:00`, `applied_points=10`, `capped=false`. | PASS |
| No-signal comparator does not get fake threat-intel credit | Config no-signal action reports `threat_intel_points_requested=0`, `threat_intel_points_applied=0`, and `applied_threat_signals=[]`. | PASS |
| IAM headroom/cap behavior is enforced | IAM capped action `e7764c6c-1c56-426b-8373-deacb9277c30` scored `48` vs IAM no-signal `8d5a0c7d-92d8-4a35-bcbf-07a49fbe8f13` at `46`. The capped action reports `heuristic_points=13`, `threat_intel_points_requested=10`, `threat_intel_points_applied=2`, `points=15`, and `capped=true`, proving the `15`-point exploit-factor cap/headroom path is live. | PASS |

## Observed Explainability Defect

The fresh trusted-config action still contains a misleading human-readable explanation string on production:

- `score_components["exploit_signals"]["heuristic_points"] = 0`
- `score_factors[]` for `factor_name="exploit_signals"` says:
  - `Exploit signals contributed 10 points: 10 heuristic points plus 10 decayed threat-intel points ...`

The numeric fields and provenance are correct, but the explanation text overstates heuristic contribution on this live action.

Status:

- Weighting math and provenance fields: PASS
- Human-readable explanation accuracy: PARTIAL

Artifacts:

- Trusted config detail: [08-action-73097c11-174c-4597-85a2-9af793842e8d.body.json](../evidence/api/08-action-73097c11-174c-4597-85a2-9af793842e8d.body.json)
- Config no-signal detail: [08-action-a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1.body.json](../evidence/api/08-action-a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1.body.json)
- IAM capped detail: [08-action-e7764c6c-1c56-426b-8373-deacb9277c30.body.json](../evidence/api/08-action-e7764c6c-1c56-426b-8373-deacb9277c30.body.json)
- IAM no-signal detail: [08-action-8d5a0c7d-92d8-4a35-bcbf-07a49fbe8f13.body.json](../evidence/api/08-action-8d5a0c7d-92d8-4a35-bcbf-07a49fbe8f13.body.json)
