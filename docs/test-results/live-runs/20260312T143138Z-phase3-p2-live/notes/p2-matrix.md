# Phase 3 P2 Live Matrix

| Slice | Status | Exact evidence | Verdict |
| --- | --- | --- | --- |
| `P2.1` | `BLOCKED` | `../evidence/api/03-findings.body.json`, `../evidence/api/04-actions.body.json`, `../evidence/api/action-442e46ac.body.json`, `../evidence/api/action-3301b44c.body.json`, `../evidence/api/action-0ca64b94.body.json`, `p2-1-weighting-summary.md`, `p2-1-fail-closed-summary.md`, `blocker-no-threat-intel-candidates.md` | Current live data contains only configuration-style findings/actions, so no trusted threat-intel weighting path can be positively exercised. |
| `P2.2` | `BLOCKED` | `../evidence/api/04-actions.body.json`, `../evidence/api/action-442e46ac.body.json`, `../evidence/api/action-e6b1eac2.body.json`, `../evidence/api/action-caf5dc54.body.json`, `../evidence/api/action-3301b44c.body.json`, `../evidence/api/action-0ca64b94.body.json`, `../evidence/api/action-0b8c765a.body.json`, `p2-2-decay-summary.md`, `blocker-no-threat-intel-candidates.md` | No live action exposes threat-intel provenance or decay fields, so decay transparency cannot be verified on production right now. |
