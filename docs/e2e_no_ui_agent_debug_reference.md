# E2E No-UI Agent — Known Issues, Code Mapping & Required Fixes

## Summary Table
| Bug | Affected Controls | Severity | Fix Section |
|---|---|---|---|
| EC2.7 / EC2.182 wrong collector routing | `EC2.7`, `EC2.182` | Critical | [Fix 1](#fix-1--correct-ebs-collector-routing-for-ec27--ec2182) |
| Region-scoped identity mismatch in reconcile | `Config.1`, `SSM.7`, `EC2.7`, `EC2.182` | Critical | [Fix 2](#fix-2--convert-region-scoped-controls-to-account-scoped-identity-guardduty-pattern) |
| S6 KPI thresholds not hard-enforced | All controls evaluated by no-UI pipeline | High | [Fix 3](#fix-3--enforce-dod-kpi-thresholds-as-hard-gates-at-s6) |

## Section 1 — Highest-Risk Bugs

### Bug 1 — EC2.7 / EC2.182 Wrong Collector Routing
- **Exact code citations**:
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:791`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:620`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:1016`
- **Root cause**: `run_no_ui_pr_bundle_agent.py` routes all `EC2.*` controls to reconciliation service `ec2`, but `EC2.7` and `EC2.182` evaluations are emitted by the `ebs` collector path in `inventory_reconcile.py`.
- **Observed symptom**: remediation run and Terraform apply succeed, but `shadow` remains `null` and S6 verification times out.
- **Impact**: false non-resolution at S6 for EBS account controls despite successful remediation.

### Bug 2 — Config.1 / SSM.7 / EC2.7 / EC2.182 Region-Scoped Identity Mismatch
- **Exact code citations**:
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:558`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:883`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:650`
  - `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/inventory_reconcile.py:660`
  - Join behavior reference: `/Users/marcomaher/AWS Security Autopilot/backend/workers/services/shadow_state.py:63`
- **Evidence artifact**:
  - `/Users/marcomaher/AWS Security Autopilot/artifacts/no-ui-agent/20260220T022820Z/findings_pre_raw.json`
- **Root cause**: reconciliation emits `AwsAccountRegion` identity (`<account_id>:<region>`), while ingested findings for these controls are predominantly `AwsAccount` identity (`account_id` only).
- **Observed symptom**: shadow overlay join key mismatch (`resource_key` mismatch) causes `shadow=null` after reconcile.
- **Impact**: S6 fails to resolve even after successful apply and refresh.

### Bug 3 — S6 False-Positive Pass on DoD KPI Thresholds
- **Exact code citations**:
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py:528`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py:657`
  - `/Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py:710`
- **Root cause**: KPI deltas are computed and reported, but no hard assertion enforces `tested_control_delta < 0` and `resolved_gain > 0` before success status is accepted.
- **Observed symptom**: control/campaign can report success despite no measurable improvement.
- **Impact**: false-positive S6 pass and misleading campaign completion.

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

### Fix 1 — Correct EBS Collector Routing for EC2.7 / EC2.182

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

### Fix 2 — Convert Region-Scoped Controls to Account-Scoped Identity (GuardDuty Pattern)
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

### Fix 3 — Enforce DoD KPI Thresholds as Hard Gates at S6

#### Diff 3A — Agent-level hard KPI gate after delta computation
```diff
# File: /Users/marcomaher/AWS Security Autopilot/scripts/run_no_ui_pr_bundle_agent.py
# Function: _write_reports
@@
         delta = compute_delta(pre_summary, post_summary, control_id)
         write_json(self.output_dir / "findings_delta.json", delta)
+
+        kpis = delta.get("kpis") if isinstance(delta.get("kpis"), dict) else {}
+        tested_control_delta = kpis.get("tested_control_delta")
+        resolved_gain = kpis.get("resolved_gain")
+        if not isinstance(tested_control_delta, (int, float)) or tested_control_delta >= 0:
+            raise AgentValidationError(
+                f"S6 DoD failure: tested_control_delta must be < 0 (got: {tested_control_delta})"
+            )
+        if not isinstance(resolved_gain, (int, float)) or resolved_gain <= 0:
+            raise AgentValidationError(
+                f"S6 DoD failure: resolved_gain must be > 0 (got: {resolved_gain})"
+            )
@@
         report = {
```

#### Diff 3B — Campaign-level pass/fail must include KPI gate
```diff
# File: /Users/marcomaher/AWS Security Autopilot/scripts/run_s3_controls_campaign.py
@@
 def _build_final_campaign_summary(
@@
     return {"controls": control_summaries, "overall_passed": overall_passed}
+
+
+def _kpi_gate_passed(result: dict[str, Any]) -> bool:
+    tested = result.get("tested_control_delta")
+    resolved = result.get("resolved_gain")
+    return isinstance(tested, (int, float)) and tested < 0 and isinstance(resolved, (int, float)) and resolved > 0
@@
-        result["passed"] = result["exit_code"] == 0 and result["status"] == "success"
+        result["passed"] = result["exit_code"] == 0 and result["status"] == "success" and _kpi_gate_passed(result)
@@
-    return 0 if all_passed else 1
+    return 0 if all_passed else 1
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
- [ ] **Fix 1 verified**: code changed, unit test added/updated in `/Users/marcomaher/AWS Security Autopilot/tests/test_inventory_reconcile.py`, live rerun passed S6, KPI deltas confirmed non-zero.
- [ ] **Fix 2 verified**: code changed, unit test added/updated in `/Users/marcomaher/AWS Security Autopilot/tests/test_inventory_reconcile.py`, live rerun passed S6, KPI deltas confirmed non-zero.
- [ ] **Fix 3 verified**: code changed, unit test added/updated in `/Users/marcomaher/AWS Security Autopilot/tests/test_inventory_reconcile.py`, live rerun passed S6, KPI deltas confirmed non-zero.
