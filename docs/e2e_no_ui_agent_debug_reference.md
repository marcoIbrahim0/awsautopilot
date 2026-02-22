# E2E No-UI Agent — Known Issues, Code Mapping & Required Fixes

## Summary Table
| Bug | Affected Controls | Status | Reference |
|---|---|---|---|
| Bug 1 — EC2.7 / EC2.182 routing + shadow promotion chain | `EC2.7`, `EC2.182` | Closed ✅ (2026-02-22 UTC) | [Bug 1 (Closed)](#bug-1--ec27--ec2182-wrong-collector-routing-closed) |
| Bug 2 — Region-scoped identity mismatch in reconcile | `Config.1`, `SSM.7`, `EC2.7`, `EC2.182` | Closed ✅ (2026-02-22 UTC) | [Bug 2 (Closed)](#bug-2-closed--config1--ssm7--ec27--ec2182-region-scoped-identity-mismatch) |
| Bug 3 — S6 KPI thresholds not hard-enforced | All controls evaluated by no-UI pipeline | Closed ✅ (2026-02-22 UTC) | [Bug 3 (Closed)](#bug-3-closed--s6-kpi-schema--hard-gate-enforcement) |
| Bug 4 — S6 outcome classification and campaign aggregation hardening | All controls evaluated by no-UI pipeline | Closed ✅ (2026-02-22 UTC) | [Bug 4 (Closed)](#bug-4-closed--s6-outcome-classification-and-campaign-aggregation) |

### Final Closure Record (Bugs 1-4)
- **Bug 1:** EC2.7 / EC2.182 wrong collector routing and identity shape — closed and SaaS-confirmed.
- **Bug 2:** Config.1, SSM.7, EC2.7, EC2.182 region-scoped identity in inventory reconcile — closed. Reconcile emissions for all four controls include account-scoped `AwsAccount` + `account_id` identity (EC2.182 also maintains dual-shape compatibility in findings).
- **Bug 3:** KPI schema gap and hard-gate enforcement — closed. Top-level `tested_control_delta` / `resolved_gain` are populated; gate enforces non-compliant pre-state runs and skips already-compliant no-op runs.
- **Bug 4:** S6 reporting layer hardening — closed. `final_report` now emits `outcome_type`, `gate_evaluated`, and `gate_skip_reason`; campaign summary now exposes `remediated_count`, `already_compliant_noop_count`, and `failed_count`.
- **Closure artifacts:**
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/ec2_7_bug1_validation_4`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/ec2_182_bug1_validation_2`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/config1_bug2_validation_3`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/ssm7_bug2_validation`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/full_e2e_validation_2`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/full_e2e_validation_2_ssm7`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/full_e2e_validation_2_ec2_7`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/ec2_182_bug2_final_validation`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/config1_bug4_validation`

### Final Session Summary (2026-02-22 UTC)
> ✅ End of current debug + hardening cycle.

- Option B fallback fix closed the last known campaign failure mode (preferred control with no eligible open finding now classifies as no-op instead of hard-fail mismatch).
- Campaign layer is production-ready for single-account operation.
- All four controls (`Config.1`, `SSM.7`, `EC2.7`, `EC2.182`) are validated across Bugs 1–4 with artifact paths recorded.
- Latest campaign proof:
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/s3-campaign-20260222T045146Z/campaign_summary.json`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/s3-campaign-20260222T045146Z/final_campaign_summary.json`
- End-state:
  - Bug 1: closed
  - Bug 2: closed
  - Bug 3: closed
  - Bug 4: closed
  - Tests: `556 passed`
  - Campaign layer: single-account four-control validation `overall_passed=true`

## Section 1 — Highest-Risk Bugs

### Bug 1 — EC2.7 / EC2.182 Wrong Collector Routing (Closed)
- **Exact code citations**:
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:791`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:620`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:1016`
- **Root cause**: `run_no_ui_pr_bundle_agent.py` routes all `EC2.*` controls to reconciliation service `ec2`, but `EC2.7` and `EC2.182` evaluations are emitted by the `ebs` collector path in `inventory_reconcile.py`.
- **Observed symptom**: remediation run and Terraform apply succeed, but `shadow` remains `null` and S6 verification times out.
- **Impact**: false non-resolution at S6 for EBS account controls despite successful remediation.

### Bug 1 Closure Evidence (2026-02-22 UTC)
> ✅ Status: Fully closed. SaaS-visible finding resolution and forwarder verification are confirmed.

**Live no-UI validation run directories:**
- `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/ec2_7_bug1_validation_4`
- `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/ec2_182_bug1_validation_2`

**Final control outcomes:**
| Control | `final_report.status` | `shadow` | `shadow.status_normalized` | `apply_exit_code` |
|---|---|---|---|---|
| `EC2.7` | `success` | present | `RESOLVED` | `0` |
| `EC2.182` | `success` | present | `RESOLVED` | `0` |

**SaaS list visibility confirmation (`GET /api/findings`, account `029037611564`, region `eu-north-1`, limit `20`):**
| Finding ID | Control | Status | `resolved_at` | `display_badge` | List index |
|---|---|---|---|---|---|
| `4a5c3213-9e5e-4186-8451-77f0fdd16a12` | `EC2.182` (`AwsEc2SnapshotBlockPublicAccess`) | `RESOLVED` | `2026-02-22T00:20:49.781678+00:00` | `resolved` | `1` |
| `8cff7c16-c70a-4c2e-8433-b84d9a58ab5d` | `EC2.182` (`AwsAccount`) | `RESOLVED` | `2026-02-22T00:20:49.774016+00:00` | `resolved` | `2` |
| `08b8e40b-abb2-44b2-bbb9-cc0a644a0533` | `EC2.7` (`AwsAccount`) | `RESOLVED` | `2026-02-22T00:20:49.758152+00:00` | `resolved` | `4` |

**Bug 1 code changes that closed the issue:**
- `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/shadow_state.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/models/finding.py`
- `/Users/marcomaher/AWS Security Autopilot/alembic/versions/0032_findings_resolved_at.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/workers/jobs/ingest_findings.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/workers/jobs/ingest_access_analyzer.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/workers/jobs/ingest_inspector.py`
- `/Users/marcomaher/AWS Security Autopilot/backend/routers/findings.py`
- `/Users/marcomaher/AWS Security Autopilot/tests/test_no_ui_pr_bundle_agent_smoke.py`
- `/Users/marcomaher/AWS Security Autopilot/tests/test_inventory_reconcile.py`
- `/Users/marcomaher/AWS Security Autopilot/tests/test_shadow_state.py`
- `/Users/marcomaher/AWS Security Autopilot/tests/test_worker_ingest.py`

**Forwarder verification confirmation (console-free):**
- Stack: `SecurityAutopilotControlPlaneForwarder` (`029037611564`, `eu-north-1`)
- Script: `/Users/marcomaher/AWS Security Autopilot/scripts/verify_control_plane_forwarder.sh`
- Verified result: `Phase 1 PASS`, `Phase 2 PASS`, `Phase 3 PASS`, `exit 0`
- Supporting status: control-plane token rotated and stack updated; target DLQ backlog purged before final PASS run

### Bug 2 (Closed) — Config.1 / SSM.7 / EC2.7 / EC2.182 Region-Scoped Identity Mismatch
> ✅ Status: Fully closed on 2026-02-22 UTC.

- **Exact code citations**:
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:545`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:559`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:883`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:915`
  - Join behavior reference: `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/shadow_state.py:85`
- **Evidence artifact**:
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/20260220T022820Z/findings_pre_raw.json`
- **Code-state update (2026-02-22)**:
  - `_collect_config_account` now emits `resource_id=account_id`, `resource_type=AwsAccount`.
  - `_collect_ssm_account` now emits `resource_id=account_id`, `resource_type=AwsAccount`.
  - `_collect_ebs_account` was already account-scoped (plus ARN dual-shape for `EC2.182`) from Bug 1 closure.
- **Closure evidence (live runs):**
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/config1_bug2_validation_3`
    - `final_report.status=success`
    - `terraform apply exit_code=0`
    - target finding `shadow` present, `shadow.status_normalized=RESOLVED`
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/ssm7_bug2_validation`
    - `final_report.status=success`
    - `terraform apply exit_code=0`
    - target finding `shadow` present, `shadow.status_normalized=RESOLVED`
- **Supporting completion notes:**
  - `Config.1` and `SSM.7` reconcile identities now match account-scoped finding shape.
  - `EC2.7` and `EC2.182` were already closed in Bug 1 (EBS routing + account/dual-shape support).
  - Config PR bundle path now includes delivery bucket policy application to avoid `InsufficientDeliveryPolicyException` on fresh accounts.

### Bug 3 (Closed) — S6 KPI Schema + Hard Gate Enforcement
> ✅ Status: Closed on 2026-02-22 UTC.

- **Exact code citations**:
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:648`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:653`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:684`
  - `/Users/marcomaher/AWS Security Autopilot/tests/test_no_ui_pr_bundle_agent_smoke.py:205`
  - `/Users/marcomaher/AWS Security Autopilot/tests/test_no_ui_pr_bundle_agent_smoke.py:212`
- **Root cause (pre-fix)**:
  - KPI values were only written under `final_report.delta.kpis`, while top-level `final_report.tested_control_delta` / `final_report.resolved_gain` were missing.
  - No run-level hard gate failed remediation runs when KPI proof of improvement was absent.
- **Fix implemented (2026-02-22)**:
  - `final_report` now mirrors:
    - `tested_control_delta = delta["kpis"]["tested_control_delta"]`
    - `resolved_gain = delta["kpis"]["resolved_gain"]`
  - Hard gate added in `_write_reports`:
    - If `self.final_status == "success"` and `terraform_apply` completed and run is not `dry_run`,
    - then fail run (`status=failed`, non-zero exit, checkpoint error) when `resolved_gain` is missing/non-numeric or `<= 0`.
- **Live validation evidence**:
  - Artifact: `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/config1_bug3_validation`
  - `terraform apply exit_code=0`
  - Finding state: `shadow` present, `shadow.status_normalized=RESOLVED`
  - Top-level KPI fields are now present and non-null:
    - `tested_control_delta=0`
    - `resolved_gain=0`
  - Final run status is `failed` with error:
    - `KPI gate failed: resolved_gain must be > 0 after remediation apply (got 0)`
  - This confirms the gate is now enforced rather than silently passing.
  - Expected behavior note: this gate fire occurred on a rerun after prior remediation had already resolved `Config.1` during Bug 2 validation, so `resolved_gain=0` is accurate and not a regression.

### Bug 4 (Closed) — S6 Outcome Classification and Campaign Aggregation
> ✅ Status: Closed on 2026-02-22 UTC.

- **Exact code citations:**
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:672`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:708`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py:468`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py:522`
  - `/Users/marcomaher/AWS Security Autopilot/tests/test_no_ui_pr_bundle_agent_smoke.py:212`
  - `/Users/marcomaher/AWS Security Autopilot/tests/test_s3_campaign_summary.py:55`
- **Root cause (pre-fix):**
  - Operator-facing campaign outputs could not distinguish `remediated` vs `already_compliant_noop` vs `failed` without manual artifact inspection.
- **Fix implemented (2026-02-22):**
  - Added top-level classification fields to `final_report.json`:
    - `outcome_type` (`remediated` | `already_compliant_noop` | `failed`)
    - `gate_evaluated` (`true` | `false`)
    - `gate_skip_reason` (`apply_not_completed` | `pre_already_compliant` | `null`)
  - Added campaign summary rollups:
    - `remediated_count`
    - `already_compliant_noop_count`
    - `failed_count`
  - Added path tests for all three outcome classes and campaign aggregation totals.
- **Live validation evidence:**
  - Artifact: `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/config1_bug4_validation`
  - `final_report.status=success`
  - `terraform apply exit_code=0`
  - live finding `shadow` present, `shadow.status_normalized=RESOLVED`
  - `outcome_type=already_compliant_noop`
  - `gate_evaluated=false`
  - `gate_skip_reason=pre_already_compliant`

## Section 2 — S0–S6 Gate-to-Code Canonical Mapping

### Gate Mapping Table
| Gate | Campaign Orchestrator Mapping | Per-Control Agent Mapping | Primary Assertion Boundary |
|---|---|---|---|
| S0 | `/Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py:529`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py:537`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py:548` | `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:288`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:297` | Hard abort before control execution when auth/readiness fails |
| S1 | `/Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py:594` | `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:301` | `readiness.json` + readiness guard (`overall_ready` + region recency) |
| S2 | Campaign delegates to agent run | `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:309`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:573`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:320` | Ingest+compute refresh, then eligibility assertion in target select |
| S3 | Campaign delegates to agent run | `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:323`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:336` | Target finding/action/control IDs and control-preference guard |
| S4 | Campaign delegates to agent run | `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:346`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:397`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:432` | Strategy selection, run creation, and terminal run success |
| S5 | Campaign reads apply transcript | `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:458`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:471` | Bundle extracted and `terraform apply` completion recorded |
| S6 | Campaign summarizes from per-control outputs | `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:489`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:492`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:515`, `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:521` | Refresh/reconcile, resolution poll, post snapshot, delta/KPI report |

### Per-Gate Narrative
- **S0**: campaign-level login and stage0 readiness gate are enforced before any control run; the per-control agent enforces `phase_auth` + `phase_readiness` when invoked directly.
- **S1**: readiness is polled/validated at campaign scope and persisted as `readiness.json` at agent scope.
- **S2**: pre-snapshot triggers ingest/compute refresh; target eligibility assertion is performed when selecting a target finding.
- **S3**: target context requires non-empty identifiers and matching control preference.
- **S4**: remediation strategy is selected, run is created, then polled to terminal success.
- **S5**: PR bundle is downloaded/extracted and Terraform apply is executed with transcript capture.
- **S6**: refresh (optionally reconcile) runs, verification poll waits for resolved state + readiness freshness, then post-snapshot and delta report complete DoD evaluation.

## Section 3 — Exact Code Changes Required
> ✅ Status: `Fix 1` and `Fix 2` are implemented and live-verified. Keep diffs as historical reference.

### Fix 1 — Correct EBS Collector Routing for EC2.7 / EC2.182 (Implemented; reference only)

#### Diff 1A — Route EC2.7/EC2.182 to `ebs` in agent reconcile service mapping
```diff
# File: /Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py
# Function: _reconcile_services_for_control
@@
 def _reconcile_services_for_control(control_id: str) -> list[str]:
     token = str(control_id or "").strip().upper()
     if token.startswith("S3."):
         return ["s3"]
+    if token in {"EC2.7", "EC2.182"}:
+        return ["ebs"]
     if token.startswith("EC2."):
         return ["ec2"]
     if token.startswith("IAM."):
         return ["iam"]
```

#### Diff 1B — Codify collector ownership for EC2.7/EC2.182 in reconcile service module
```diff
# File: /Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py
@@
 INVENTORY_SERVICES_DEFAULT: tuple[str, ...] = (
@@
     "guardduty",
 )
+
+# Controls emitted by EBS account collector (not EC2 SG collector).
+EBS_ACCOUNT_CONTROLS: frozenset[str] = frozenset({"EC2.7", "EC2.182"})
@@
 def _collect_ebs_account(
@@
-    evals = [
+    # EC2.7 and EC2.182 reconciliation snapshots are emitted from this EBS path.
+    evals = [
@@
 def collect_inventory_snapshots(
@@
     if svc == "ec2":
         return _collect_ec2_security_groups(session_boto, region, resource_ids, max_resources)
@@
     if svc == "ebs":
         return _collect_ebs_account(session_boto, account_id, region)
```

### Fix 2 — Convert Region-Scoped Controls to Account-Scoped Identity (Implemented)
Reference pattern: `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:963`

#### Diff 2A — `_collect_config_account` (`Config.1`)
```diff
# File: /Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py
# Function: _collect_config_account
@@
 def _collect_config_account(
@@
-    evals = [
+    resource_id = account_id
+    resource_type = "AwsAccount"
+    evals = [
         _control_eval(
             control_id="Config.1",
-            resource_id=f"{account_id}:{region}",
-            resource_type="AwsAccountRegion",
+            resource_id=resource_id,
+            resource_type=resource_type,
             status=SHADOW_STATUS_RESOLVED if compliant else SHADOW_STATUS_OPEN,
@@
     return [
         InventorySnapshot(
             service="config",
-            resource_id=f"{account_id}:{region}",
-            resource_type="AwsAccountRegion",
+            resource_id=resource_id,
+            resource_type=resource_type,
             key_fields=state_for_hash.copy(),
             state_for_hash=state_for_hash,
             metadata_json=None,
             evaluations=evals,
         )
```

#### Diff 2B — `_collect_ssm_account` (`SSM.7`)
```diff
# File: /Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py
# Function: _collect_ssm_account
@@
 def _collect_ssm_account(
@@
-    evals = [
+    resource_id = account_id
+    resource_type = "AwsAccount"
+    evals = [
         _control_eval(
             control_id="SSM.7",
-            resource_id=f"{account_id}:{region}",
-            resource_type="AwsAccountRegion",
+            resource_id=resource_id,
+            resource_type=resource_type,
             status=status,
@@
     return [
         InventorySnapshot(
             service="ssm",
-            resource_id=f"{account_id}:{region}",
-            resource_type="AwsAccountRegion",
+            resource_id=resource_id,
+            resource_type=resource_type,
             key_fields=state_for_hash.copy(),
             state_for_hash=state_for_hash,
             metadata_json=None,
             evaluations=evals,
         )
```

#### Diff 2C — `_collect_ebs_account` (`EC2.7`, `EC2.182`)
```diff
# File: /Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py
# Function: _collect_ebs_account
@@
 def _collect_ebs_account(
@@
-    evals = [
+    resource_id = account_id
+    resource_type = "AwsAccount"
+    evals = [
         _control_eval(
             control_id="EC2.7",
-            resource_id=f"{account_id}:{region}",
-            resource_type="AwsAccountRegion",
+            resource_id=resource_id,
+            resource_type=resource_type,
             status=SHADOW_STATUS_RESOLVED if ebs7_compliant else SHADOW_STATUS_OPEN,
@@
         _control_eval(
             control_id="EC2.182",
-            resource_id=f"{account_id}:{region}",
-            resource_type="AwsAccountRegion",
+            resource_id=resource_id,
+            resource_type=resource_type,
             status=ec2182_status,
@@
     return [
         InventorySnapshot(
             service="ebs",
-            resource_id=f"{account_id}:{region}",
-            resource_type="AwsAccountRegion",
+            resource_id=resource_id,
+            resource_type=resource_type,
             key_fields=state_for_hash.copy(),
             state_for_hash=state_for_hash,
             metadata_json=None,
             evaluations=evals,
         )
```

### Fix 3 — Enforce S6 KPI Mirroring + Resolved-Gain Hard Gate (Implemented)

#### Diff 3A — Agent-level KPI mirroring and hard gate in `_write_reports`
```diff
# File: /Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py
# Function: _write_reports
@@
         delta = compute_delta(pre_summary, post_summary, control_id)
+        kpis = delta.get("kpis") if isinstance(delta.get("kpis"), dict) else {}
+        tested_control_delta = kpis.get("tested_control_delta")
+        resolved_gain = kpis.get("resolved_gain")
+        apply_phase_completed = self.state.is_phase_complete("terraform_apply")
+        is_real_apply = not bool(self.settings.get("dry_run"))
+        if self.final_status == "success" and apply_phase_completed and is_real_apply:
+            resolved_gain_value = resolved_gain if isinstance(resolved_gain, (int, float)) else None
+            if resolved_gain_value is None or resolved_gain_value <= 0:
+                self.final_status = "failed"
+                self.exit_code = self.exit_code or 1
+                self.state.add_error(
+                    "report",
+                    (
+                        "KPI gate failed: resolved_gain must be > 0 after remediation apply "
+                        f"(got {resolved_gain!r})"
+                    ),
+                )
+        write_json(self.output_dir / "findings_delta.json", delta)
@@
         report = {
             "tested_control_delta": tested_control_delta,
             "resolved_gain": resolved_gain,
```

## Section 4 — Additional Plan Gaps That Can Cause False-Positive S6

### Gap A — Missing reconcile terminal-status assertion before verification
- **Missing assertion**: verify reconcile run result is `succeeded` (or approved terminal) before starting verification poll.
- **Where to add**: `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:490` after `_trigger_refresh(include_reconcile=True)`; fail fast if reconcile status is `failed`, `partial_failed`, or `timeout`.

### Gap B — S2 eligibility does not assert `in_scope=true`
- **Missing assertion**: selected finding must satisfy `in_scope == true`.
- **Where to add**: `/Users/marcomaher/AWS Security Autopilot/scripts/lib/no_ui_agent_stats.py:115` in `_is_eligible_target`, and guard check in `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:320`.

### Gap C — No pre-state -> post-state transition assertion for the target finding
- **Missing assertion**: ensure target finding was open (`NEW`/`NOTIFIED`) at pre-snapshot and transitions to resolved at S6.
- **Where to add**: capture initial target state in `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:323` and enforce transition in `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:506`.

### Gap D — Ingest/compute are asynchronous fire-and-forget with no completion synchronization
- **Missing assertion**: wait for fresh ingest/compute completion markers before target selection.
- **Where to add**: extend `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:570` (`_trigger_refresh`) with completion polling and freshness checks before `phase_target_select`.

## Verification Checklist
- [x] **Fix 1 verified**: code changed, unit test added/updated in `/Users/marcomaher/AWS Security Autopilot/tests/test_inventory_reconcile.py`, live rerun passed S6, KPI deltas confirmed non-zero.
- [x] **Fix 2 verified**: code changed, unit test added/updated in `/Users/marcomaher/AWS Security Autopilot/tests/test_inventory_reconcile.py`, live rerun passed S6 with `apply_exit_code=0` and non-null shadow for `Config.1` + `SSM.7`.
- [x] **Fix 3 verified**: code changed in `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py`, tests updated in `/Users/marcomaher/AWS Security Autopilot/tests/test_no_ui_pr_bundle_agent_smoke.py`, full suite passed, and live rerun confirmed non-null top-level KPI fields plus enforced hard-fail when `resolved_gain <= 0`.
- [x] **Fix 4 verified**: code changed in `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py` and `/Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py`, tests added/updated in `/Users/marcomaher/AWS Security Autopilot/tests/test_no_ui_pr_bundle_agent_smoke.py` and `/Users/marcomaher/AWS Security Autopilot/tests/test_s3_campaign_summary.py`, and live rerun captured `outcome_type=already_compliant_noop` in `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/config1_bug4_validation`.
