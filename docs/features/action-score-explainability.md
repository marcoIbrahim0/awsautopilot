# Action Score Explainability

This feature makes prioritized action scores explainable in both human and machine terms.

Implemented source files:
- `backend/services/action_scoring.py`
- `backend/routers/actions.py`
- `frontend/src/lib/api.ts`

## What is returned

`GET /api/actions` and `GET /api/actions/{action_id}` now return:
- `score`: the persisted `0-100` action score.
- `score_components`: the existing normalized component payload from P0.1.
- `score_factors`: an auditor-readable factor list derived from `score_components`.
- `context_incomplete` on action detail responses when toxic-combination promotion was withheld because relationship context was missing or low-confidence.

When toxic-combination prioritization is present in `score_components`, `score_factors` also includes a `toxic_combinations` entry with either:
- a positive additive boost, or
- a zero-point fail-closed explanation such as `context incomplete`, low-confidence relationship context, or missing required related signals.

Each `score_factors` entry includes:
- `factor_name`
- `weight`
- `contribution`
- `evidence_source`
- `signals`
- `explanation`

The factor contributions always sum to the returned `score`. If an older action only has partial scoring metadata, the API falls back to a single legacy factor so the contract stays non-empty and internally consistent.

## Current factor weights

The current deterministic weights come directly from `backend/services/action_scoring.py`:

| Factor | Weight |
| --- | ---: |
| `severity` | `35` |
| `internet_exposure` | `20` |
| `privilege_level` | `15` |
| `data_sensitivity` | `15` |
| `exploit_signals` | `15` |
| `compensating_controls` | `15` |

`compensating_controls` contributes negative points when mitigating context is present.

`toxic_combinations` is additive and rule-based rather than normalized against the base weights above. Its contribution is capped separately by `ACTIONS_TOXIC_COMBINATION_MAX_BOOST`.

When `score_components["context_incomplete"]` is `true`, the returned score intentionally stays at `score_before_toxic_combinations` and the toxic-combination factor explains why no additive promotion was applied.

## Evidence model

Evidence is intentionally constrained to safe, explainable metadata:
- fixed evidence-source strings such as `finding.severity_label + finding.severity_normalized`
- bounded keyword/action signals already used by the scorer
- human-readable explanations generated from the stored score metadata

The API does not echo raw finding blobs, AWS credentials, tokens, or other secret-like values in `score_factors`.

## Batch list behavior

For `GET /api/actions?group_by=batch`, the batch item score still represents the highest member action score in that group. The returned `score_factors` come from that same highest-scoring representative action so the explanation matches the displayed score.

```mermaid
flowchart TD
    A["Finding + raw Security Hub metadata"] --> B["backend/services/action_scoring.py"]
    B --> C["Persisted actions.score"]
    B --> D["Persisted actions.score_components"]
    D --> E["backend/routers/actions.py"]
    C --> E
    E --> F["score_factors in /api/actions list"]
    E --> G["score_factors in /api/actions/{id} detail"]
```

## Related docs

- [AWS Security Autopilot documentation index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md)
- [Baseline report spec](/Users/marcomaher/AWS%20Security%20Autopilot/docs/baseline-report-spec.md)
- [Toxic-combination prioritization](/Users/marcomaher/AWS%20Security%20Autopilot/docs/features/toxic-combination-prioritization.md)
