# Candidate Actions

The current live tenant does not contain any valid P2 threat-intel candidates.

Observed live action set:
- `442e46ac-f31c-4242-82ca-9e47081a3adb` — `ebs_snapshot_block_public_access`
- `e6b1eac2-041c-4fb3-9a47-2525a3afa908` — `ssm_block_public_sharing`
- `caf5dc54-aef7-4df2-9480-1fdbfcfc507a` — `s3_block_public_access`
- `3301b44c-8846-49c2-9f27-823e6a77e559` — `cloudtrail_enabled`
- `0ca64b94-9dcb-4a97-91b0-27b0341865bc` — `ebs_default_encryption`
- `0b8c765a-62b0-4f80-8271-2bb1bbd4b353` — `enable_guardduty`

Why these are not suitable for P2:
- All seven live findings are Security Hub configuration/control findings; none indicates Inspector-style vulnerability context, CVE metadata, or threat-intel payloads.
- No inspected action detail exposes `threat_intel_points_requested`, `threat_intel_points_applied`, `threat_intel_max_points`, `factor_max_points`, or `applied_threat_signals[]`.
- No inspected action detail exposes `score_factors[].provenance[]` entries with `source`, `observed_at`, `decay_applied`, `base_contribution`, or `final_contribution`.

Nearest inspected actions used only to confirm absence of the P2 contract:
- `442e46ac-f31c-4242-82ca-9e47081a3adb` — highest-scored current action; `exploit_signals` remains the legacy heuristic shape only
- `3301b44c-8846-49c2-9f27-823e6a77e559` — zero exploit contribution; no threat-intel metadata
- `0ca64b94-9dcb-4a97-91b0-27b0341865bc` — comparable medium-risk config action; no threat-intel metadata

Supporting evidence:
- `../evidence/api/03-findings.body.json`
- `../evidence/api/04-actions.body.json`
- `../evidence/api/action-442e46ac.body.json`
- `../evidence/api/action-3301b44c.body.json`
- `../evidence/api/action-0ca64b94.body.json`
