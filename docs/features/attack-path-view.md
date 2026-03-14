# Attack Path View

Implemented in Phase 3.5.1.

This feature turns `GET /api/actions/{id}` into a bounded attack story that explains how an attacker gets in, what they can reach, why the action is urgent, and what the safest next step is without introducing a free-form graph explorer or a second scoring system.

Implemented source files:
- `backend/services/action_attack_path_view.py`
- `backend/routers/actions.py`
- `frontend/src/lib/api.ts`
- `frontend/src/components/ActionDetailModal.tsx`
- `frontend/src/components/ActionDetailAttackPathNodeCard.tsx`
- `frontend/src/components/actionDetailExplainers.ts`
- `frontend/src/components/actionDetailAttackPath.ts`
- `frontend/src/components/ui/AnimatedTooltip.tsx`
- `tests/test_phase3_p3_5_1_attack_path_view.py`
- `tests/test_wave5_action_detail_contract.py`
- `frontend/src/components/ActionDetailAttackPathNodeCard.test.tsx`
- `frontend/src/components/actionDetailAttackPath.test.ts`

## API contract

`GET /api/actions/{id}` now includes additive `attack_path_view`.

Payload shape:

- `status`
  - `available`
  - `partial`
  - `unavailable`
  - `context_incomplete`
- `summary`
- `path_nodes[]`
- `path_edges[]`
- `entry_points[]`
- `target_assets[]`
- `business_impact_summary`
- `risk_reasons[]`
- `recommendation_summary`
- `confidence`
- `truncated`
- `availability_reason`

Current `path_nodes[].kind` values:

- `entry_point`
- `identity`
- `target_asset`
- `business_impact`
- `next_step`

Current `path_nodes[].facts[]` shape:

- `label`
- `value`
- `tone`
  - `default`
  - `accent`
  - `code`

Current `availability_reason` values:

- `relationship_context_unavailable`
- `relationship_context_incomplete`
- `bounded_context_truncated`
- `entry_point_unresolved`
- `target_assets_unresolved`
- `partial_attack_story`

## Source-of-truth reuse

The view is additive and reuses existing contracts only:

- `graph_context`
- `business_impact`
- `recommendation`
- `score_factors`
- `score_components`
- `execution_guidance`
- `sla`
- owner metadata already present on the action

No new risk score, business-criticality model, or unbounded graph query path is introduced.

## State semantics

### `available`

- bounded graph context exists
- a concrete entry point and target asset can be shown
- no truncation was required
- this now includes self-resolved bounded paths when the backing `graph_context` is marked `self_resolved=true`

### `partial`

- the story can still be shown, but some context was intentionally capped or could not be resolved inside the bounded slice
- `truncated=true` when the bounded graph input hit its existing caps

### `unavailable`

- the graph-backed attack story cannot be rendered from the bounded detail inputs
- the field still returns a stable explicit fallback payload instead of disappearing

### `context_incomplete`

- the action already carries explicit fail-closed context markers from the existing prioritization pipeline
- the API avoids implying a concrete attack path and returns empty `path_nodes[]` / `path_edges[]`
- exception: when bounded graph context is already `available`, the attack path can still render as `available` or `partial`
- this applies both to provider-backed bounded graph context and to `self_resolved=true` fallback graph context
- for self-resolved paths, the confidence stays lowered because the anchor was reconstructed from the action's persisted fields

## Self-resolved fallback

When provider relationship metadata is missing or low-confidence, the view can now reuse the additive bounded graph context if that graph was self-resolved from persisted action metadata.

That behavior stays conservative:

- it does not invent a new graph source of truth
- it still relies on the existing bounded `graph_context` neighborhood
- it lowers attack-path confidence to `0.20`
- the summary explicitly states that Autopilot resolved the path independently because provider metadata was unavailable

## Bounded model

The path view is built from the already-bounded action-detail neighborhood exposed by [Graph-backed action context](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/graph-backed-action-context.md).

It does not traverse beyond the existing detail caps:

- `max_related_findings = 24`
- `max_related_actions = 24`
- `max_inventory_assets = 24`
- `max_connected_assets = 6`
- `max_identity_nodes = 6`
- `max_blast_radius_neighbors = 6`

## Render flow

```mermaid
flowchart TD
    A["GET /api/actions/{id}"] --> B["Load additive detail contracts"]
    B --> C["graph_context"]
    B --> D["business_impact"]
    B --> E["recommendation"]
    B --> F["score_factors + score_components"]
    B --> G["execution_guidance + sla"]
    C --> H["build_action_attack_path_view(...)"]
    D --> H
    E --> H
    F --> H
    G --> H
    H --> I["attack_path_view"]
    I --> J["ActionDetailModal Attack Path"]
    F --> K["Why this is prioritized"]
    D --> K
    E --> K
```

## UI behavior

`frontend/src/components/ActionDetailModal.tsx` now renders:

- a dashboard-aligned `Attack Path` section with a bounded horizontal path
- hover/focus help on the `Bounded decision view` label so operators know the panel is intentionally concise and not a free-form graph explorer
- help-marked hoverable labels/badges and auto-flipped tooltip placement so bounded-view explanations stay readable near the modal edge
- plain-language hover copy that explains what the bounded view means before it references graph/scoring terminology
- the shared tooltip renders in a top-level portal so these explanations are not cut off by the action-detail modal container
- inline-emphasized target resource, account scope, operator caution, and recommended next step directly in the summary copy instead of separate context cards
- de-duplicated summary support text so the target resource and next step are not repeated again below the main story when the summary already includes them
- explicit badges for:
  - `Actively exploited`
  - `Business critical` with hover/focus help that clarifies the badge is driven by business-impact evidence rather than technical score alone
  - `Context incomplete`
- a tooltip explanation on the `partial` status badge using concise `Take care:` wording and left-side placement so the bounded/incomplete reason is fully visible near the right edge of the panel
- same-size bounded path cards with clearer typography and node detail text under each node when available
- cards render backend-provided `path_nodes[].facts[]` directly in a compact `1 insight + up to 2 facts` format instead of inferring entry/target/scope rows from the summary on the frontend
- target/scope support context moved into the relevant path cards instead of sitting in a separate metadata row above the path
- the `next_step` card no longer repeats a redundant `Safest next step` footer badge because that recommendation is already expressed in the card title/body and summary copy
- a `Why this is prioritized` priority storyboard that surfaces:
  - a short risk-summary headline
  - a score waterfall with stronger per-factor contrast and factor labels/values outside the decorative bars for stable scanning
  - a dashboard-aligned impact panel with one primary business-dimension card and a bounded supporting-evidence rail so text never collapses into narrow columns
  - a full-width recommended-check command rail with a compact `Context missing` badge when tenant context is still unverified

Existing business-impact, score-explainability, threat-intel provenance, graph-context, and implementation-artifact sections remain in place.

## Limitations

- The path is intentionally single-story and bounded; it is not a tenant-wide graph explorer.
- `context_incomplete` remains fail-closed when bounded graph context is not available.
- The current confidence value is derived from the existing relationship-context confidence and bounded-state handling, with a fixed `0.20` fallback for self-resolved paths rather than a new scoring system.
- The view prefers the recommended execution-guidance entry when present; otherwise it falls back to the existing recommendation mode/rationale.
- Some nodes can legitimately render fewer than two fact rows when bounded source data is missing; the API does not invent filler metadata to satisfy the UI shape.

## Related docs

- [Graph-backed action context](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/graph-backed-action-context.md)
- [Security Graph foundation](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/security-graph-foundation.md)
- [Business impact matrix](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/business-impact-matrix.md)
- [Recommendation mode matrix](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/recommendation-mode-matrix.md)
- [Threat-intelligence weighting](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/threat-intelligence-weighting.md)
- [AWS Security Autopilot documentation index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md)
