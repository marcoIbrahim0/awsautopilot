# P2.1 Weighting Summary

Status: `BLOCKED`

Observed live behavior:
- None of the six live action details exposes the requested threat-intel fields inside `score_components["exploit_signals"]`.
- The inspected actions only show the legacy heuristic exploit shape (`points`, `signals`, `normalized`) plus the existing explainability contribution text.
- No live action demonstrates `applied_threat_signals[]`, trusted-source labels, confidence values, or separate requested-vs-applied threat-intel math.

What this means:
- A positive P2.1 validation cannot be performed on the current production dataset.
- Current evidence is sufficient only to say that the tenant lacks threat-intel-bearing actions; it is not sufficient to distinguish between "no qualifying live data" and "undeployed P2 contract" for a positive case.

Supporting evidence:
- `../evidence/api/04-actions.body.json`
- `../evidence/api/action-442e46ac.body.json`
- `../evidence/api/action-3301b44c.body.json`
- `../evidence/api/action-0ca64b94.body.json`
- `blocker-no-threat-intel-candidates.md`
