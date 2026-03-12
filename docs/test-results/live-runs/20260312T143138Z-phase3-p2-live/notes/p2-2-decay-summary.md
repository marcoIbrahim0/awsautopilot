# P2.2 Decay Summary

Status: `BLOCKED`

Observed live behavior:
- None of the six inspected action details exposes `score_factors[].provenance[]`.
- No live action detail exposes `source`, `observed_at`, `decay_applied`, `base_contribution`, or `final_contribution`.
- No live action provides an older trusted signal, a decayed non-zero signal, or an aged-out zero-point provenance entry.

What this means:
- P2.2 decay and provenance transparency cannot be validated on the current live dataset.
- The current production tenant first needs at least one threat-intel-bearing vulnerability action, ideally with both fresh and older timestamps, before decay math can be evaluated.

Supporting evidence:
- `../evidence/api/action-442e46ac.body.json`
- `../evidence/api/action-e6b1eac2.body.json`
- `../evidence/api/action-caf5dc54.body.json`
- `../evidence/api/action-3301b44c.body.json`
- `../evidence/api/action-0ca64b94.body.json`
- `../evidence/api/action-0b8c765a.body.json`
- `blocker-no-threat-intel-candidates.md`
