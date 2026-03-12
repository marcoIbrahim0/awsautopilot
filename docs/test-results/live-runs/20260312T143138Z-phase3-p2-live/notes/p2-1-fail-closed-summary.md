# P2.1 Fail-Closed Summary

Status: `NOT TESTABLE`

Observed live behavior:
- No live action carries threat-intel payloads at all.
- Because there is no positive threat-intel candidate, there is also no direct live example of an untrusted, low-confidence, inactive, malformed, or no-headroom threat signal being rejected.

Conservative conclusion:
- The current live dataset is insufficient to validate P2.1 fail-closed cases.
- Existing config-only actions with heuristic `exploit_signals` are not enough to prove the P2-specific fail-closed branches.

Supporting evidence:
- `../evidence/api/04-actions.body.json`
- `../evidence/api/action-442e46ac.body.json`
- `../evidence/api/action-3301b44c.body.json`
- `../evidence/api/action-0ca64b94.body.json`
- `blocker-no-threat-intel-candidates.md`
