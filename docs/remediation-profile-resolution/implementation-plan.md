# Remediation Profile Resolution Implementation Plan

> Scope date: 2026-03-14
>
> ⚠️ Status: Partially implemented on `master` — later steps and live product-claim updates remain planned
>
> Source spec: [Remediation Profile Resolution](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/README.md)

## Summary

This implementation plan converts the remediation profile resolution spec into `10 ordered steps`, each broken into numbered substeps so an implementer can focus on one slice at a time. The plan preserves the current public `strategy_id` contract, keeps grouped runs on the single-row persistence model, and keeps IAM.4 execution authority exclusively under `/api/root-key-remediation-runs`.

Guardrails for every step:

- `direct_fix` remains out of scope.
- No public strategy ID semantics change for existing clients.
- No grouped route may bypass shared resolver-backed safety.
- No root-key lifecycle behavior may become profile-driven in this phase.
- No product claim changes land before live validation.

Use this plan serially:

- complete substeps in order within each step
- satisfy the step definition of done before starting the next step unless a later step is explicitly unblocked
- treat this as a planning and execution-sequencing doc, not a progress checklist

## Step Index

1. Baseline contract lock and legacy compatibility guardrails
2. Resolver types, decision schema, and profile catalog
3. Resolution-aware options and preview
4. Single-run remediation creation
5. Shared grouped-run service for both grouped entry points
6. Queue payload v2, resend, duplicate detection, and worker migration
7. Mixed-tier grouped bundle layout, manifest, executor, and reporting
8. Tenant remediation settings persistence and API exposure
9. Incremental control-family migration
10. Final docs and product-claim update after validation

## Planned Interface Coverage

This plan still explicitly covers the planned additive interfaces and payload concepts from the source spec:

- `POST /api/remediation-runs`
- `POST /api/remediation-runs/group-pr-bundle`
- `POST /api/action-groups/{group_id}/bundle-run`
- `GET/PATCH /api/users/me/remediation-settings`
- `profile_id`
- `profiles[]`
- grouped `action_overrides[]`
- `repo_target`
- `artifacts.resolution`
- `artifacts.group_bundle.action_resolutions`
- queue payload schema versioning

## Step 1: Baseline Contract Lock and Legacy Compatibility Guardrails

Dependencies: None. This step establishes the migration floor.

Current baseline artifact:

- [Wave 0 contract lock](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-profile-resolution/wave-0-contract-lock.md)

### 1.1 Capture the current API contract surface

Document the current behavior and request/response shape for:

- `GET /api/actions/{id}/remediation-options`
- `GET /api/actions/{id}/remediation-preview`
- `POST /api/remediation-runs`
- `POST /api/remediation-runs/group-pr-bundle`
- `POST /api/action-groups/{group_id}/bundle-run`
- `/api/root-key-remediation-runs`

The goal is to make later changes measurable against a known compatibility baseline.

### 1.2 Record legacy artifact mirror fields and their consumers

List the current artifact keys that existing code paths still depend on during duplicate detection, resend, worker execution, and run-detail hydration:

- `selected_strategy`
- `strategy_inputs`
- `pr_bundle_variant`

This step should also identify where each mirror field is still read so later cleanup is deliberate instead of accidental.

### 1.3 Record current duplicate-detection and resend behavior

Define the current request-signature behavior for single-run and grouped-run requests, including which top-level fields currently participate and which resend flows reconstruct those fields.

This becomes the baseline for later `profile_id`, override, and `repo_target` signature changes.

### 1.4 Define the fail-closed worker schema-version guard

Specify that the worker dispatcher must reject unknown future schema versions explicitly before any version 2 payloads are emitted.

This requirement is part of the migration baseline, not a later nice-to-have.

### 1.5 Lock rollback and validation expectations for the migration

Define what must remain true if a later step is partially rolled out or reverted:

- schema v1 payloads must keep running
- current grouped bundle flows must remain usable
- current root-key lifecycle semantics must not change
- run-detail hydration must not break for existing runs

### Step 1 Definition of Done

- The baseline contract is explicit enough that later steps cannot silently break current clients, workers, or root-key flows.
- Legacy artifact mirrors and their consumers are enumerated.
- The worker schema-version fail-closed requirement is locked before schema v2 is introduced.

## Step 2: Resolver Types, Decision Schema, and Profile Catalog

Dependencies: Step 1 guardrails and baseline contract inventory.

### 2.1 Define the resolver core boundary

Define `RemediationProfileResolver` as the single decision authority for generic remediation selection.

The boundary should make these rules explicit:

- the core is pure or sync-compatible
- API entry points may wrap it asynchronously
- worker code can call it without requiring an async-only boundary
- generators do not make hidden business-safety decisions once resolver output exists

### 2.2 Define resolver inputs

Specify the complete input set:

- action
- linked findings
- selected strategy family
- optional `profile_id`
- explicit request inputs
- tenant remediation settings
- runtime signals
- current-resource evidence
- computed risk snapshot

Also define input precedence:

1. explicit request values
2. tenant remediation settings
3. runtime-safe defaults already declared in schema
4. static profile defaults

### 2.3 Define the canonical decision schema

Specify the persisted decision object and keep it stable enough for rollout:

- `strategy_id`
- `profile_id`
- `support_tier`
- `resolved_inputs`
- `missing_inputs`
- `missing_defaults`
- `blocked_reasons`
- `rejected_profiles`
- `finding_coverage`
- `preservation_summary`
- `decision_rationale`
- `decision_version`

Set `decision_version` to start at `resolver/v1` and reserve version changes for material schema or selection-semantics changes.

### 2.4 Define support tiers and downgrade semantics

Specify the three planned tiers:

- `deterministic_bundle`
- `review_required_bundle`
- `manual_guidance_only`

Also define that generators may only downgrade for renderer or bundle invariants once the resolver has already made the business-safety decision.

### 2.5 Define the profile catalog under public strategy families

Create a resolver-owned profile catalog that stays separate from `STRATEGY_REGISTRY` and is keyed by existing public strategy compatibility families.

Each profile definition must identify:

- profile ID
- default support tier
- eligibility rules
- default inputs
- missing-default requirements
- downgrade rules
- rationale templates

### 2.6 Define the phase-1 compatibility rule for single-profile families

Lock the phase-1 rule that when a strategy currently maps to one concrete remediation path:

- `profile_id == strategy_id`

Also preserve the compatibility rule that future internal branching must not break strategy-only clients.

### Step 2 Definition of Done

- The resolver boundary, inputs, outputs, versioning, and support tiers are fully specified.
- The profile catalog can be implemented without changing public strategy semantics.
- The phase-1 `profile_id == strategy_id` compatibility rule is explicit.

## Step 3: Resolution-Aware Options and Preview

Dependencies: Step 2 resolver and profile catalog.

### 3.1 Define additive `profiles[]` metadata under `strategies[]`

Keep `GET /api/actions/{id}/remediation-options` on the existing `strategies[]` contract while adding:

- `profiles[]`
- `recommended_profile_id`
- `missing_defaults`
- `blocked_reasons`
- `decision_rationale`

Older clients must still be able to ignore the additive fields and behave correctly.

### 3.2 Define recommended-profile selection in options mode

Specify that `recommended_profile_id` is computed dynamically from the current action context, linked findings, runtime signals, tenant defaults, and current-resource evidence, with no explicit user override.

The recommendation must come from the same resolver logic that later powers create-time behavior.

### 3.3 Define preview support for optional `profile_id`

Specify that `GET /api/actions/{id}/remediation-preview` accepts optional `profile_id` and returns a `resolution` object tied to the backend-selected profile.

Preview should simulate the resolved decision, not a flat strategy-only approximation.

### 3.4 Define ambiguous-selection validation behavior

When multiple eligible profiles exist and neither `profile_id` nor legacy-disambiguating `strategy_inputs` uniquely identify one profile, specify a validation response that returns:

- eligible profiles
- blocked reasons
- missing defaults

The backend must not silently guess.

### 3.5 Define backward-compatible behavior for strategy-only clients

Specify that legacy `strategy_inputs` continue to participate in profile auto-selection where they historically encoded branch selection.

Strategy-only clients must continue to get deterministic legacy-equivalent behavior whenever one eligible profile can be selected safely.

### Step 3 Definition of Done

- Options and preview are defined in terms of the same resolution logic that create paths will use.
- Strategy-only clients remain backward compatible.
- Ambiguous profile selection is explicitly validated rather than guessed.

## Step 4: Single-Run Remediation Creation

Dependencies:

- Step 2 decision schema.
- Step 3 options and preview behavior.

### 4.1 Define single-run request handling for optional `profile_id`

Keep `POST /api/remediation-runs` on the current required `strategy_id` behavior where that is required today, and add optional `profile_id` support as additive metadata and selection input.

### 4.2 Define resolver-backed validation flow

Specify the validation path for:

- selected strategy family
- selected profile
- explicit inputs
- missing defaults
- blocked reasons
- risk context

Single-run creation must use the same resolved-decision logic as preview.

### 4.3 Define canonical persistence in `artifacts.resolution`

Specify that the canonical persisted decision for single-run remediation is stored in:

- `artifacts.resolution`

This is the authoritative record for later run-detail hydration and compatibility-aware resend.

### 4.4 Define which legacy mirrors remain written during rollout

Specify exactly which top-level artifact mirrors stay written during the migration window and why they remain necessary.

This should preserve compatibility for:

- duplicate detection
- resend and requeue flows
- worker execution paths still reading legacy keys
- legacy run-detail consumers

### 4.5 Define run-detail hydration from canonical and legacy data

Specify that run detail reads from the canonical resolution payload first but remains able to hydrate required fields from legacy mirrors during rollout.

The additive run-detail surface should include:

- `selected_profile`
- `support_tier`
- `rejected_profiles`
- `finding_coverage`
- `preservation_summary`
- `decision_rationale`

### 4.6 Re-state the direct-fix boundary

Keep `direct_fix` explicitly outside this migration:

- no preview behavior changes
- no approval behavior changes
- no validation behavior changes
- no queue payload changes
- no worker runtime changes

### Step 4 Definition of Done

- Single-run create, preview, and run-detail behavior are resolution-consistent.
- Canonical persistence and legacy mirror writes are both specified.
- The direct-fix out-of-scope boundary remains explicit.

## Step 5: Shared Grouped-Run Service for Both Grouped Entry Points

Dependencies: Step 4 single-run resolution persistence.

### 5.1 Define the shared grouped-run creation service boundary

Define one grouped-run service that both grouped entry points must use:

- `POST /api/remediation-runs/group-pr-bundle`
- `POST /api/action-groups/{group_id}/bundle-run`

The action-groups route must not remain a raw enqueue bypass.

### 5.2 Define grouped request normalization across both routes

Specify how grouped requests normalize shared inputs:

- top-level `strategy_id`
- top-level `strategy_inputs`
- optional grouped `action_overrides[]`
- `repo_target`
- group scope and representative action anchoring

### 5.3 Define grouped `action_overrides[]` validation rules

Specify grouped override validation:

- override action must belong to the grouped action set
- duplicate overrides are rejected
- override strategy must be valid for the grouped action type
- override profile must belong to the override strategy family
- override inputs apply only to the overridden action

### 5.4 Define grouped per-action resolution with one grouped run row

Specify that grouped resolution is per action while grouped persistence remains:

- one `RemediationRun` row per group
- one representative action anchor as today
- per-action decisions stored under grouped artifacts

This step removes representative-action-only risk evaluation without changing the one-row grouped persistence model.

### 5.5 Define `ActionGroupRun` lifecycle preservation

Preserve the existing action-groups route lifecycle behavior:

- `ActionGroupRun` tracking
- reporting-token issuance
- reporting callback configuration
- grouped-run linkage to the single grouped `RemediationRun`

### 5.6 Define `repo_target` parity for `/api/action-groups/{group_id}/bundle-run`

Specify that the action-groups grouped route gains `repo_target` parity with the grouped remediation-runs route and persists it through grouped artifact and queue construction.

### Step 5 Definition of Done

- Both grouped entry points are specified to use one resolver-backed grouped service.
- Grouped overrides, grouped per-action resolution, and grouped lifecycle tracking are all explicit.
- No grouped route is left with a resolver bypass.

## Step 6: Queue Payload v2, Resend, Duplicate Detection, and Worker Migration

Dependencies: Step 5 shared grouped-run service.

### 6.1 Define schema v2 queue payload shape and versioning rules

Specify the version 2 payload for resolution-aware runs, including:

- explicit schema version
- single-run resolution payload support
- grouped per-action decision support
- grouped metadata needed by worker generation and reporting

Schema version 1 must remain runnable throughout the rollout window.

### 6.2 Define worker branching rules for schema v1 and schema v2

Specify how worker dispatch distinguishes:

- legacy top-level strategy payloads
- resolution-aware single-run payloads
- grouped per-action decision payloads

Unknown future schema versions must fail closed.

### 6.3 Define request-signature updates for `profile_id`, overrides, and `repo_target`

Specify the request-signature changes needed so that:

- different `profile_id` values are not treated as identical
- different grouped override maps are not treated as identical
- `repo_target` continues participating where it already affects grouped output identity

### 6.4 Define resend and requeue reconstruction rules

Specify how resend and requeue rebuild resolution-aware payloads while preserving:

- legacy mirrors
- grouped override state
- `repo_target`
- grouped single-row persistence semantics

### 6.5 Define grouped worker generation changes

Specify that grouped worker generation must consume per-action decisions when resolution-aware grouped data is present.

The worker must stop assuming one shared grouped strategy in that path.

### 6.6 Define `_generate_group_pr_bundle` replacement or wrapper expectations

Specify whether `_generate_group_pr_bundle` is refactored directly or wrapped by a new resolution-aware grouped generation layer, but make the requirement explicit:

- each grouped action must be generated from its own resolved decision

### Step 6 Definition of Done

- Schema v2 payload behavior is fully specified.
- Schema v1 compatibility remains explicit.
- Duplicate detection, resend, and worker generation all account for profile-aware grouped decisions.

## Step 7: Mixed-Tier Grouped Bundle Layout, Manifest, Executor, and Reporting

Dependencies: Step 6 worker migration and grouped per-action decisions.

### 7.1 Define the grouped bundle folder layout

Specify the new grouped bundle layout:

- `executable/actions/...`
- `review_required/actions/...`
- `manual_guidance/actions/...`

New grouped bundles should not keep executable work rooted at legacy `actions/`.

### 7.2 Define manifest fields

Specify that `bundle_manifest.json` declares at least:

- `layout_version`
- `execution_root`
- grouped action list
- per-action outcome or tier information

The manifest becomes the primary runtime signal for bundle layout interpretation.

### 7.3 Define `run_all.sh` behavior for executable-only actions

Specify that `run_all.sh` for new grouped bundles scans and executes only:

- `executable/actions`

It must not attempt to execute review-required or manual-guidance folders.

### 7.4 Define executor detection order for new and legacy bundles

Specify executor detection order:

1. if manifest declares `layout_version` and `execution_root`, use them
2. else if `executable/actions` exists, treat as mixed-tier grouped bundle
3. else if `actions` exists, treat as legacy grouped bundle
4. else treat as single-run workspace-root bundle

### 7.5 Define grouped artifact outputs across all tiers

Specify that grouped artifacts enumerate all actions, not just executable ones, in:

- `bundle_manifest.json`
- `decision_log.md`
- `finding_coverage.json`

### 7.6 Define additive reporting callback changes

Specify additive grouped reporting callback support for:

- `non_executable_results[]`

Each item should capture:

- `action_id`
- `support_tier`
- `profile_id`
- `strategy_id`
- `reason`
- `blocked_reasons`

### 7.7 Define grouped success and failure semantics

Specify that grouped runs may succeed with mixed outcomes when some actions are executable and others are explicitly review/manual or blocked.

Hard failure remains reserved for broken shared invariants, invalid requests, broken grouped execution invariants, or zero-artifact outcomes.

### Step 7 Definition of Done

- Mixed-tier grouped bundle behavior, manifest semantics, executor detection, and additive reporting are fully specified.
- Legacy grouped bundles remain executable.
- Partial executable coverage is explicitly supported.

## Step 8: Tenant Remediation Settings Persistence and API Exposure

Dependencies:

- Step 2 resolver precedence rules.
- Step 5 grouped shared service if grouped flows will consume tenant defaults immediately.

### 8.1 Define the `Tenant.remediation_settings` persistence addition

Specify the planned persistence addition:

- `Tenant.remediation_settings` JSONB column
- additive migration only
- tenant-scoped data ownership

### 8.2 Define GET and PATCH schema expectations

Specify the nested response and PATCH schema for remediation settings, including which fields are readable and which are writable.

### 8.3 Define PATCH merge, replace, and clear semantics

Specify PATCH behavior exactly:

- omitted fields remain unchanged
- provided scalar fields replace existing scalar values
- provided object branches deep-merge into the existing JSONB document
- explicit `null` clears the addressed scalar field or object branch
- unknown keys are rejected with HTTP 400

### 8.4 Define admin-only and tenant-scoped write rules

Specify that the route remains tenant-scoped and PATCH remains admin-only, consistent with current `/users/me/*-settings` behavior.

### 8.5 Define settings fields used by resolver default precedence

Specify the settings families and fields that can feed resolver defaults in phase 1, including:

- SG access-path preferences and related approved values
- CloudTrail defaults
- Config defaults
- S3 access-log defaults
- S3 encryption defaults

### 8.6 Define secret-exposure guardrails for the settings contract

Specify that the remediation-settings route must not expose secret values or unintended sensitive material beyond the intended contract surface.

### Step 8 Definition of Done

- Remediation settings persistence, PATCH semantics, auth boundaries, and resolver-consumed fields are specific enough to implement directly.
- The settings contract has explicit rules for what is and is not exposed.

## Step 9: Incremental Control-Family Migration

Dependencies: Steps 2 through 8.

### 9.1 Define the migration order for control families

Specify the order each family moves onto resolver-backed profile selection so rollout stays bounded and compatible.

The migration order should favor families where current behavior and downgrade paths are already well understood.

### 9.2 Define EC2.53 profile branching and executable-only branches

Specify EC2.53 migration inside `sg_restrict_public_ports` while preserving `sg_restrict_public_ports_guided` as the public compatibility strategy.

Executable phase-1 branches remain only:

- `close_public`
- `close_and_revoke`
- `restrict_to_ip`
- `restrict_to_cidr`

Keep `ssm_only` and `bastion_sg_reference` as review/manual until runtime support exists.

### 9.3 Define IAM.4 additive profile metadata and dedicated execution authority

Specify that IAM.4 keeps `iam_root_key_disable` and `iam_root_key_delete`, with additive profile metadata only.

Execution authority must remain exclusively under `/api/root-key-remediation-runs`.

### 9.4 Define S3.2 family migration and manual-only fallback paths

Specify that S3.2 keeps its current strategy families and may add manual-only profile paths such as `website_manual` without breaking current strategy compatibility.

### 9.5 Define S3.5 and S3.11 preservation-evidence gating

Specify that executable S3.5 and S3.11 output requires resolver-side preservation evidence:

- policy-document capture and merge-safety for S3.5
- lifecycle-document capture and additive-merge safety for S3.11

Without that evidence, the path downgrades explicitly.

Current landed scope on `master`:

- 9.2 is implemented for EC2.53.
- 9.3 is implemented for IAM.4 guidance metadata while `/api/root-key-remediation-runs` remains the only execution authority.
- 9.4 is implemented for S3.2 with explicit manual-only fallback profiles.
- 9.5 is implemented for S3.5 and S3.11 with resolver-side preservation summaries, explicit downgrade reasons, and single-run worker gating that keeps non-deterministic branches metadata-only.
- 9.6 is implemented for S3.9 and S3.15 with explicit family branches, runtime-proof downgrade rules, and worker-side metadata-only bundle gating for non-deterministic paths.

### 9.6 Define S3.9 and S3.15 branching and downgrade conditions

Implemented scope on `master`:

- S3.9 access-logging destination safety
  - executable compatibility branch: `s3_enable_access_logging_guided`
  - explicit downgrade branch: `s3_enable_access_logging_review_destination_safety`
  - executable output now requires source bucket scope plus destination safety proof from runtime signals
  - ambiguous source/destination relationships and unproven destination safety downgrade explicitly
- S3.15 AWS-managed versus customer-managed KMS paths
  - executable compatibility branch remains `s3_enable_sse_kms_guided` for AWS-managed `aws/s3`
  - explicit customer-managed branch is `s3_enable_sse_kms_customer_managed`
  - customer-managed paths downgrade when `kms_key_arn` is missing, the key is invalid, or key-policy/grant proof is incomplete

External dependencies that cannot be proven safe in phase 1 must downgrade explicitly.

### 9.7 Define CloudTrail.1 and Config.1 migration boundaries

Specify that CloudTrail.1 and Config.1 keep their existing public strategy families while unresolved or unsupported branches are represented as review/manual instead of executable.

Implemented on `master` on 2026-03-15 for the Prompt 5 local contract scope:

- CloudTrail.1 keeps public strategy `cloudtrail_enable_guided`.
  - Resolver-backed defaults now read `cloudtrail.default_bucket_name` and `cloudtrail.default_kms_key_arn`.
  - Executable output remains limited to the compatibility branch with a resolved, runtime-proven log bucket and default-safe `create_bucket_policy=true` plus `multi_region=true`.
  - `create_bucket_policy=false`, `multi_region=false`, unresolved bucket defaults, unreachable bucket proof, and KMS delivery all downgrade explicitly.
- Config.1 keeps public strategies `config_enable_account_local_delivery`, `config_enable_centralized_delivery`, and `config_keep_exception`.
  - Resolver-backed defaults now read `config.delivery_mode`, `config.default_bucket_name`, and `config.default_kms_key_arn`.
  - Generator-safe local create-new delivery remains executable where runtime proof is not required.
  - Centralized or existing-bucket paths downgrade explicitly when delivery-bucket reachability, centralized policy compatibility, or KMS validity cannot be proven.

### 9.8 Re-state the explicit downgrade rule

Lock the rule that unsupported or under-proven branches must downgrade to:

- `review_required_bundle`
- `manual_guidance_only`

They must never appear executable by default.

### Step 9 Definition of Done

- Each migrated control family has an explicit rule set for compatibility rows, branch eligibility, and downgrade behavior.
- No control-family migration step leaves execution eligibility ambiguous.

## Step 10: Final Docs and Product-Claim Update After Validation

Dependencies: Steps 1 through 9 complete for the relevant control families.

### 10.1 Define the live-validation coverage required before claiming shipped behavior

Specify that each migrated control family needs one of these live-validation proof shapes before product or operator docs describe the behavior as shipped:

- Standard proof shape:
  - one deterministic executable validation case
  - one truthful blocked or review/manual validation case
- Provider-drift exception shape:
  - one deterministic executable validation case
  - explicit evidence that current live provider semantics do not materialize a truthful failing case for that family

Lock the provider-drift exception behind these guardrails:

- it is documentation and gate-policy only, not a runtime downgrade relaxation
- it must cite a dated evidence package plus exact action, run, resource, and control identifiers
- the family must be described as `executable-only under current live semantics`
- it must be re-evaluated on the next targeted live rerun or if the live provider control inventory changes

### 10.2 Define which runtime docs can change only after validation

Specify that only validated runtime behavior should update shipped operator or product docs. Planned docs may describe intended behavior earlier, but shipped docs must lag implementation until validation is complete.

### 10.3 Define operator-guidance updates for grouped mixed-tier bundles and remediation settings

Specify the operator-facing documentation updates required after validation for:

- mixed-tier grouped bundle handling
- new remediation-settings behavior
- profile-aware resolution and downgrade interpretation

### 10.4 Define the legacy-mirror retirement follow-up boundary

Specify that retiring legacy artifact mirrors is follow-on work and must not be implied complete merely because canonical resolution payloads exist.

This boundary prevents accidental cleanup before all compatibility consumers are migrated.

### Step 10 Definition of Done

- Shipped docs and product claims describe only validated runtime behavior, including any explicitly documented provider-drift exception.
- The legacy-mirror retirement boundary is clearly tracked as follow-on work rather than implied complete.

## Acceptance Summary

The implementation is complete only when all of the following remain true:

- `strategy_id` is still the public compatibility contract.
- `direct_fix` is unchanged and still out of scope.
- Both grouped bundle routes share one resolver-backed safety path.
- Grouped runs still use one `RemediationRun` row per group in phase 1.
- `/api/root-key-remediation-runs` remains the only IAM.4 execution authority.
- Tenant remediation settings remain tenant-scoped and admin-write.
- Mixed-tier grouped bundles work without breaking legacy grouped bundle execution.
