# Final Summary

## Outcome

Overall run result: `PARTIAL`

This rerun proves the core `P2.1` and `P2.2` API contracts are live on production, but the full end-to-end outcome remains partial because production still shows explainability and cleanup defects.

## What Live Production Proved

- `P2.1` trusted threat-intelligence weighting is live.
  - Config trusted signal: `26` vs `16` against the config no-signal comparator.
  - IAM headroom/cap path: `48` vs `46`, with `requested=10`, `applied=2`, `capped=true`.
- `P2.1` fail-closed behavior is live.
  - Low-confidence config signal stayed at `16` with zero threat-intel contribution and no fake provenance.
- `P2.2` decay/provenance transparency is live at the API layer.
  - The aged trusted signal kept visible provenance even after decaying to `0` current points.
- The live UI list shows all six synthetic actions.
- The live UI action drawer opens on the trusted-config action and shows the correct live priority (`26`).

## Live Defects and Gaps

- Standard recompute still fails on production:
  - `ValueError: security graph node missing for key=action:0ca64b94-9dcb-4a97-91b0-27b0341865bc`
- The trusted-config action’s human-readable `exploit_signals` explanation is incorrect on live:
  - it claims `10 heuristic points` even though `heuristic_points=0`
- The UI does not surface the new threat-intel provenance contract:
  - no visible `CVE`
  - no visible source label (`CISA`)
  - no visible decay/provenance metadata
- Source cleanup only partially propagated into app state:
  - Security Hub accepted archival for all six synthetic findings
  - post-cleanup open-actions list still retained four synthetic actions

## Cleanup Result

- Source-side cleanup:
  - assumed-role import succeeded with `SuccessCount=6`
  - post-import Security Hub state shows all six synthetic findings as `RecordState=ARCHIVED`
- App-side cleanup:
  - cleanup ingest completed with `updated_findings_count=2`
  - standard recompute failed again on the security graph defect
  - graph-bypass recompute succeeded but resolved only the two trusted-config synthetic actions

> ❓ Needs verification: why `BatchImportFindings` accepted the cleanup payload for all six findings but post-import `get-findings` still reports `Workflow=NEW` while `RecordState=ARCHIVED`.

> ❓ Needs verification: why the app-side ingest plus graph-bypassed recompute removed only the two trusted-config synthetic actions from the open set while the four archived no-signal / low-confidence / IAM synthetic actions remained open.

## Related Notes

- [tenant-context.md](tenant-context.md)
- [candidate-actions.md](candidate-actions.md)
- [selected-actions.md](selected-actions.md)
- [p2-1-weighting-summary.md](p2-1-weighting-summary.md)
- [p2-1-fail-closed-summary.md](p2-1-fail-closed-summary.md)
- [p2-2-decay-summary.md](p2-2-decay-summary.md)
- [p2-matrix.md](p2-matrix.md)
