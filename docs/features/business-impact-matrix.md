# Business Impact Matrix

Implemented in Phase 3 P1.7.

This feature adds an explicit `risk x criticality` matrix for actions so the platform can rank technically similar issues differently when the business context is materially different.

Implemented source files:
- `backend/services/action_business_impact.py`
- `backend/services/action_engine.py`
- `backend/services/toxic_combinations.py`
- `backend/routers/actions.py`
- `frontend/src/lib/api.ts`
- `frontend/src/components/ActionDetailModal.tsx`
- `frontend/src/components/ActionDetailPriorityStoryboard.tsx`
- `frontend/src/components/actionDetailExplainers.ts`
- `frontend/src/components/actionDetailBusinessImpact.ts`
- `frontend/src/components/ui/AnimatedTooltip.tsx`
- `frontend/src/components/actionDetailBusinessImpact.test.ts`
- `frontend/src/app/pr-bundles/create/page.tsx`
- `frontend/src/app/pr-bundles/create/summary/page.tsx`

## API contract

`GET /api/actions` and `GET /api/actions/{action_id}` now return additive `business_impact` payloads:

- `technical_risk_score`
- `technical_risk_tier`
- `criticality`
- `matrix_position`
- `summary`

`criticality` includes:

- `status`
- `score`
- `tier`
- `weight`
- `dimensions[]`
- `explanation`

`matrix_position` includes:

- `row`
- `column`
- `cell`
- `risk_weight`
- `criticality_weight`
- `rank`
- `explanation`

Each criticality dimension entry includes:

- `dimension`
- `label`
- `weight`
- `matched`
- `contribution`
- `signals`
- `explanation`

## Criticality model

The current deterministic criticality model uses bounded heuristics only.

| Dimension | Weight | Evidence model |
| --- | ---: | --- |
| `customer_facing` | `25` | bounded keywords such as `customer portal`, `external api`, `website` |
| `revenue_path` | `25` | bounded keywords such as `billing`, `checkout`, `payment`, `subscription` |
| `regulated_data` | `25` | bounded keywords and action hints such as `pci`, `phi`, `pii`, `s3_bucket_encryption_kms` |
| `identity_boundary` | `15` | bounded identity/resource hints such as `AwsAccount`, `AwsIamRole`, `root user`, `assume role` |
| `production_environment` | `10` | bounded production tokens such as `production`, `prod-`, `-prod`, `live` |

Single-signal matches contribute `60%` of the dimension weight. Multiple signals contribute the full dimension weight.

Criticality tiers:

| Score | Tier |
| ---: | --- |
| `70+` | `critical` |
| `40-69` | `high` |
| `1-39` | `medium` |
| `0` | `unknown` |

## Matrix placement

Technical risk still comes from the existing P0 scoring model described in [Action score explainability](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/action-score-explainability.md).

Risk tiers:

| Score | Tier |
| ---: | --- |
| `85+` | `critical` |
| `65-84` | `high` |
| `40-64` | `medium` |
| `0-39` | `low` |

Matrix rank is deterministic and ordered by:

1. matrix row weight (`critical` > `high` > `medium` > `low`)
2. matrix column weight (`critical` > `high` > `medium` > `unknown`)
3. technical risk score
4. existing stable tie-breakers (`updated_at`, `id`)

This means business criticality can rerank actions with the same technical score without hiding the raw score itself.

```mermaid
flowchart TD
    A["Representative finding"] --> B["Technical risk score (P0 scorer)"]
    A --> C["Criticality dimensions"]
    C --> D["criticality.status / tier / score"]
    B --> E["technical_risk_tier"]
    D --> F["matrix_position"]
    E --> F
    F --> G["/api/actions ordering"]
    F --> H["Action detail + summary UI"]
```

## Missing criticality handling

Missing criticality is explicit, not silently defaulted.

When no criticality signals are found:

- `criticality.status = "unknown"`
- `criticality.tier = "unknown"`
- `matrix_position.column = "unknown"`
- `summary` explicitly says the action has unknown criticality

The action still receives a deterministic matrix cell and rank because technical risk remains known.

## UI surfaces

The matrix payload is currently surfaced in:

- action detail modal
- PR bundle action selection list
- PR bundle summary view

The action detail modal shows:

- a matrix/criticality badge in the main action header with hover/focus help that explains how technical risk and business criticality combine for matrix placement
- hoverable labels and badges now use explicit help markers so explainable UI elements are visually distinct from static metadata
- the current hover copy is written in non-technical language first, so operators can understand the badge meaning without knowing the underlying model terms
- technical risk score in the main action header
- a `Why this is prioritized` priority storyboard that combines:
  - a short business-effect headline translated from the strongest matched dimensions
  - a score waterfall for the top explainable score drivers with factor labels rendered outside the bars, stronger per-factor contrast, and hover/focus explanations on `Score waterfall`, `Visible lift`, and each factor label
  - a dashboard-style impact panel centered on the primary matched business dimension with a bounded rail for supporting evidence cards plus hover/focus explanations on `Impact constellation` and `Focus dimension`
  - a recommended-check command rail that keeps the operator's next verification step visible
  - a compact `Context missing` badge when criticality is still unknown, with hover/focus help that explains why criticality stayed unknown and what tenant metadata would enrich it

The PR bundle selection and summary tables show condensed matrix labels so operators can see business context before selecting or batching work.

## Validation

- [P1.7 tests](/Users/marcomaher/AWS%20Security%20Autopilot/tests/test_phase3_p1_7_business_impact_matrix.py)
- `pytest tests/test_phase3_p1_7_business_impact_matrix.py -q`
- `pytest -q`

## Related docs

- [Action score explainability](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/action-score-explainability.md)
- [Recommendation mode matrix](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/recommendation-mode-matrix.md)
- [AWS Security Autopilot documentation index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md)
