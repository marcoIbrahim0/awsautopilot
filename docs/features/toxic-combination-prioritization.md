# Toxic-Combination Prioritization

This feature adds a conservative attack-path-lite boost on top of the existing P0.1 action score.

Implemented source files:
- `backend/services/toxic_combinations.py`
- `backend/services/action_engine.py`
- `backend/services/action_scoring.py`
- `backend/routers/actions.py`

## Status

Implemented in Phase 3 P0.3.

## What it does

- Detects explicit toxic combinations across related actions that came from open findings.
- Applies an additive score boost only when every required signal in a rule is present and the related relationship context is both complete and above the minimum confidence threshold.
- Persists the boosted score back onto:
  - `actions.score`
  - `actions.priority`
  - `actions.score_components["toxic_combinations"]`
- Persists `actions.score_components["context_incomplete"]` so the API can show when toxic-combination promotion was withheld because relationship context was missing or low-confidence.
- Reuses the existing `/api/actions` ordering and batch-group logic, so boosted priorities are visible without a separate API path.

## Safe default rule

The default rule is intentionally narrow:

| Rule ID | Required signals | Boost |
| --- | --- | ---: |
| `public_exposure_privilege_sensitive_data` | `internet_exposure` + `privilege_weakness` + `sensitive_data` | `15` |

Only resource-scoped actions can act as the anchor for this rule. Account-scoped actions such as root-account hygiene findings can contribute supporting context, but they do not become boosted anchors themselves.

## Relationship model

The current implementation is fail-closed and only evaluates the following neighborhood after explicit relationship context is available:

- same tenant
- same AWS account
- same region, or region plus global/account-scoped context
- same `resource_id` for resource-scoped related actions
- optional account-scoped supporting actions

Relationship context is considered complete only when one of these payloads is present and marks the context complete with confidence `>= 0.75`:

- `finding.raw_json.relationship_context`
- `finding.raw_json.RelationshipContext`
- `finding.raw_json.graph_context`
- `finding.raw_json.GraphContext`
- `finding.raw_json.ProductFields["aws/autopilot/relationship_context"]`
- `finding.raw_json.ProductFields["aws/autopilot/graph_context"]`

If the anchor action is account-scoped, the relationship payload is missing, or the confidence is below threshold, the engine records `context_incomplete` and applies no boost.

```mermaid
flowchart TD
    A["Resource-scoped action"] --> B["Collect same-resource related actions"]
    A --> C["Collect account-scoped supporting actions"]
    B --> D["Required rule signals all present?"]
    C --> D
    D -->|Yes| E["Boost actions.score and actions.priority"]
    D -->|No| F["No boost"]
    A --> G["Anchor is account-scoped?"]
    G -->|Yes| H["Context incomplete: no boost"]
```

## API behavior

`GET /api/actions` and `GET /api/actions/{id}` expose the result through the existing score contract:

- `score` and `priority` include the toxic-combination boost when a rule matches.
- `GET /api/actions/{id}` now includes additive `context_incomplete` so action detail can explicitly show when relationship context was not good enough to apply a boost.
- `score_components["toxic_combinations"]` includes:
  - `points`
  - `context_incomplete`
  - `matched_rule_ids`
  - `context_incomplete_rule_ids`
  - `missing_signals`
  - `signals`
  - `explanation`
- `score_factors` includes a `toxic_combinations` factor so the boost, or the fail-closed non-boost reason, is explainable.

Batch-mode action lists also inherit the boosted value because they already use the highest member action score in the group.

## Configuration

Environment variables:

- `ACTIONS_TOXIC_COMBINATIONS_ENABLED=true`
- `ACTIONS_TOXIC_COMBINATION_MAX_BOOST=15`
- `ACTIONS_TOXIC_COMBINATION_RULES_JSON=''`

`ACTIONS_TOXIC_COMBINATION_RULES_JSON` accepts an optional JSON array of explicit rule objects. Each rule supports:

- `rule_id`
- `label`
- `required_signals`
- `boost_points`
- `anchor_signals`
- `require_resource_anchor`
- `allow_account_scope_support`

If the JSON is invalid or empty, the implementation falls back to the default built-in rule.

## Limitations

- The neighborhood is computed from the current recompute scope, so out-of-scope actions are intentionally not inferred into the path.
- The current release supports explicit rule-based combinations only; it is not a full security graph.
- Boosts are capped by `ACTIONS_TOXIC_COMBINATION_MAX_BOOST`.
- Missing or low-confidence relationship data is conservative by design: no boost is applied, even if the existing same-resource/account heuristics would otherwise have matched.

## Related docs

- [Action score explainability](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/action-score-explainability.md)
- [Ownership-based risk queues](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/ownership-risk-queues.md)
- [AWS Security Autopilot documentation index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md)
