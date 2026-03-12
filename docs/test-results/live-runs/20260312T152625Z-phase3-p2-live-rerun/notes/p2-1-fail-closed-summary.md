# P2.1 Fail-Closed Summary

## Core Live Result

The low-confidence synthetic case fails closed on production.

## Observed Comparison

| Action | Score | `threat_intel_points_requested` | `threat_intel_points_applied` | `applied_threat_signals` | `score_factors[].provenance` |
| --- | ---: | ---: | ---: | --- | --- |
| `5acc7d0e-e361-474f-9efa-c200a0358f0d` — Synthetic Config finding with low-confidence threat intel | `16` | `0` | `0` | `[]` | `[]` |
| `a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1` — Synthetic Config finding without trusted threat intel | `16` | `0` | `0` | `[]` | `[]` |

Observed live outcome:

- The low-confidence candidate did not gain any threat-intel contribution.
- Its live score exactly matched the clean no-signal config comparator (`16` vs `16`).
- No fake signal provenance was added to the action detail payload.

Status:

- Low-confidence fail-closed behavior: PASS

Artifacts:

- Low-confidence detail: [08-action-5acc7d0e-e361-474f-9efa-c200a0358f0d.body.json](../evidence/api/08-action-5acc7d0e-e361-474f-9efa-c200a0358f0d.body.json)
- Config no-signal detail: [08-action-a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1.body.json](../evidence/api/08-action-a3d1ad9b-8cb7-47cc-b271-cb15f26dffd1.body.json)
