# Final Summary

## Outcome

Overall result: `PASS`

This run closed the last live blocker that remained after the earlier March 12 production rerun. Combined with the already-captured recompute, cleanup, and explanation fixes from the same production session, Phase 3 `P2` is now live-PASS on production.

## What This Run Proved

- The grouped findings API now maps the exact trusted synthetic Config finding to the correct action:
  - `remediation_action_id=73097c11-174c-4597-85a2-9af793842e8d`
  - `remediation_action_status=resolved`
- The trusted Config action detail still exposes the corrected explanation text and provenance at the API layer:
  - `0 heuristic points plus 10 decayed threat-intel points`
  - `CVE-2026-9001`
  - `cisa_kev`
  - `decay_applied=0.9957`
- A fresh standard recompute on production succeeds without the earlier security-graph node error.
- Post-recompute open actions contain zero synthetic `ocypheris-p2` actions.
- The live production grouped Findings page now renders the filtered grouped result and opens the trusted action drawer without the earlier stale grouped-card behavior.
- The live drawer visibly renders:
  - `Threat-intel provenance`
  - `CVE-2026-9001`
  - `CISA KEV`
  - `Confidence 1.00`
  - `Requested 10 pts`
  - `Applied 10 pts`
  - `Decay 0.9957`

## Combined Closure Against the March 12 Partial Run

- Standard production recompute failure: closed
- Cleanup mismatch after source archival: closed
- Trusted-config explanation inaccuracy: closed
- UI provenance visibility gap: closed
- Grouped finding opening the wrong action: closed
- Grouped Findings stale-card rendering after filter changes / refresh: closed

## Evidence

- Grouped API remaps filtered trusted Config group to the correct action:
  - [01-findings-grouped-trusted-config.json](../evidence/api/01-findings-grouped-trusted-config.json)
- Trusted action detail shows corrected explanation plus provenance:
  - [02-action-73097c11-174c-4597-85a2-9af793842e8d.json](../evidence/api/02-action-73097c11-174c-4597-85a2-9af793842e8d.json)
- Standard recompute succeeds on production:
  - [03-recompute-actions-standard.stdout.json](../evidence/api/03-recompute-actions-standard.stdout.json)
  - [03-recompute-actions-standard.stderr.txt](../evidence/api/03-recompute-actions-standard.stderr.txt)
- No synthetic actions remain open after recompute:
  - [04-open-actions-after-recompute.summary.json](../evidence/api/04-open-actions-after-recompute.summary.json)
- Live drawer visibly renders provenance:
  - [01-action-detail-trusted-config-provenance.png](../evidence/ui/01-action-detail-trusted-config-provenance.png)
  - [02-action-detail-trusted-config-provenance.snapshot.md](../evidence/ui/02-action-detail-trusted-config-provenance.snapshot.md)

## Related Runs

- [20260312T163257Z-phase3-p2-fix-validation](../../20260312T163257Z-phase3-p2-fix-validation/notes/)
- [20260312T152625Z-phase3-p2-live-rerun](../../20260312T152625Z-phase3-p2-live-rerun/notes/final-summary.md)
