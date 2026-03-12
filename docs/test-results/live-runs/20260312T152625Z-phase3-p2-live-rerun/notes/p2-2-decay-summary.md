# P2.2 Decay Summary

## Core Live Result

`P2.2` decay and zero-point provenance are live on production at the API layer.

## Aged Candidate

- Action ID: `18de803d-b7cd-4df8-ad30-1604dcb05cd5`
- Title: `Synthetic Config finding with aged trusted threat intel`
- Live score: `16`

## Observed Provenance Fields

The aged action detail exposes all required P2.2 provenance fields on live:

- `score_components["exploit_signals"]["signals"] = ["threat_intel:cisa_kev:CVE-2026-9002"]`
- `score_components["exploit_signals"]["threat_intel_points_requested"] = 0`
- `score_components["exploit_signals"]["threat_intel_points_applied"] = 0`
- `score_components["exploit_signals"]["applied_threat_signals"][0]`
  - `source = "cisa_kev"`
  - `timestamp = "2026-02-25T00:00:00+00:00"`
  - `decay_applied = 0.0268`
  - `requested_points = 0`
  - `applied_points = 0`
  - `final_contribution = 0`
- `score_factors[]` for `factor_name="exploit_signals"`
  - `provenance[0].source = "cisa_kev"`
  - `provenance[0].observed_at = "2026-02-25T00:00:00+00:00"`
  - `provenance[0].decay_applied = 0.0268`
  - `provenance[0].base_contribution = 10`
  - `provenance[0].final_contribution = 0`

## Zero-Point Visibility

The aged signal has fully decayed to zero current points, but provenance remains visible in both places:

- `applied_threat_signals[]` still records the aged trusted signal with zero applied points.
- `score_factors[].provenance[]` still records the source, observed time, decay factor, and zero final contribution.

This is the required zero-point transparency behavior.

Status:

- P2.2 decay/provenance API contract: PASS
- UI provenance rendering: NOT SURFACED

## UI Check

The trusted-config action drawer and DOM text search did not surface:

- `CVE-2026-9001`
- `CISA`
- `provenance`
- `decay`

The UI shows the action title and live priority, but not the API provenance contract.

Artifacts:

- Aged action detail: [08-action-18de803d-b7cd-4df8-ad30-1604dcb05cd5.body.json](../evidence/api/08-action-18de803d-b7cd-4df8-ad30-1604dcb05cd5.body.json)
- Trusted-config action drawer screenshot: [02-action-detail-trusted-config.png](../evidence/ui/02-action-detail-trusted-config.png)
- Drawer DOM search: [03-action-detail-dom-search.json](../evidence/ui/03-action-detail-dom-search.json)
