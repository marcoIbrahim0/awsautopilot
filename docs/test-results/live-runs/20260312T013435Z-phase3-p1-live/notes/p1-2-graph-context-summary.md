# P1.2 Graph-Backed Action Context Summary

- Representative live action details:
  - Graph-ready anchor `442e46ac-f31c-4242-82ca-9e47081a3adb` returns `context_incomplete=false` but `graph_context: null`.
  - Fallback candidate `3301b44c-8846-49c2-9f27-823e6a77e559` returns `context_incomplete=true` and `graph_context: null`.
- Expected additive fallback shape (`status`, `availability_reason`, empty arrays, `limits`) is absent.
- UI attempts to load action detail routes did not surface the documented graph-backed context card.
- Result:
  - Live production does not expose the documented Phase 3 P1.2 graph-backed action-detail contract.

Supporting evidence:
- `../evidence/api/p1-2-action-detail-available-442e46ac-f31c-4242-82ca-9e47081a3adb.body.json`
- `../evidence/api/p1-2-action-detail-fallback-3301b44c-8846-49c2-9f27-823e6a77e559.body.json`
- `../evidence/ui/p1-2-graph-context-available-442e46ac-f31c-4242-82ca-9e47081a3adb.png`
- `../evidence/ui/p1-2-graph-context-fallback-3301b44c-8846-49c2-9f27-823e6a77e559.png`
