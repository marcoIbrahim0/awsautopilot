# Interactive Remediation Experience — Complete Plan

**Date:** 2026-03-04
**Status:** Planning
**Scope:** All 16 in-scope controls — guided choice-driven remediation UX

---

## Goal

Transform the remediation experience from "pick a strategy and type raw values" to a **guided, choice-driven flow** where every control presents clear, human-friendly options (dropdowns, toggles, checkboxes, validated inputs) so the user knows exactly what will happen before applying.

---

## Current State

| Layer | What exists | What's missing |
|---|---|---|
| **Backend** | `strategy_inputs` dict accepted by every generator; `input_schema.fields` with `key`, `type`, `required`, `description`, `enum` | Only `string` and `string_array` types; no `boolean`/`select`/`cidr`/`number` types; no conditional visibility; no "what will happen" summary |
| **Frontend** | `RemediationModal.tsx` renders radio buttons for strategies, text/textarea for inputs, dependency checks, risk ack, preview | No dropdowns, toggles, CIDR validators, contextual help, or impact preview text per choice |
| **API** | `GET /api/actions/{id}/remediation-options` returns strategies with `input_schema`; `GET /api/actions/{id}/remediation-preview` returns compliance preview | Preview is a single `message` string; not choice-aware with per-field impact descriptions |

---

## Part A — Guided Choice Inputs

### A1. Backend — Extend Input Schema Types

**File:** `backend/services/remediation_strategy.py`

Extend `StrategyInputSchemaField` to support richer types:

```python
# New field types (backward-compatible additions)
type: "string" | "string_array" | "select" | "boolean" | "cidr" | "number"

# New optional properties per field:
placeholder: str           # e.g. "10.0.0.0/24"
help_text: str             # e.g. "Your office IP range — find it at whatismyip.com"
default_value: Any         # Pre-filled value
options: list[dict]        # For "select" type: [{"value": "...", "label": "...", "description": "..."}]
visible_when: dict | None  # Conditional: {"field": "access_mode", "equals": "restrict_to_cidr"}
impact_text: str           # "This will block all public SSH access to this security group"
group: str                 # Visual grouping label: "Access Control", "Encryption Settings"
```

### A2. Backend — Per-Control Choice Definitions

**File:** `backend/services/remediation_strategy.py`

---

#### EC2.53 — Open SSH/RDP Connection

**Question:** *"How would you like to secure remote access to this instance?"*

| Choice | Type | What happens |
|---|---|---|
| **Close all public access** (default) | `select` option | Adds restricted SG rules only; public `0.0.0.0/0` left for manual removal |
| **Close public + auto-remove old rules** | `select` option | Sets `remove_existing_public_rules = true`; revokes `0.0.0.0/0` on 22/3389 first |
| **Restrict to my IP** | `select` option + `cidr` input | Shows CIDR input; only that range gets SSH/RDP |
| **Restrict to custom CIDR** | `select` option + `cidr` input | Same but labeled for VPN/office range |

Conditional fields:
- `allowed_cidr` (type: `cidr`) — visible when access_mode is `restrict_to_ip` or `restrict_to_cidr`
- `allowed_cidr_ipv6` (type: `cidr`) — visible when access_mode includes IPv6

Impact text per option:
- "Close all public": *"Public SSH/RDP access on ports 22 and 3389 will remain until you manually remove the 0.0.0.0/0 rules. New restricted rules will be added."*
- "Close + auto-remove": *"All existing 0.0.0.0/0 rules on ports 22 and 3389 will be automatically removed. Make sure you have alternative access (SSM, VPN) before applying."*
- "Restrict to my IP": *"Only traffic from {user_ip}/32 will be allowed on ports 22 and 3389. All other sources will be denied."*

---

#### IAM.4 — Root Access Key Active

**Question:** *"How would you like to handle the active root access key?"*

| Choice | Type | What happens |
|---|---|---|
| **Disable key** (recommended) | `select` option | Sets key to `Inactive`; reversible |
| **Delete key permanently** | `select` option | Deletes key; irreversible; requires MFA gate |

Impact text:
- Disable: *"The root access key will be set to Inactive. You can re-enable it later if needed. This is the safest first step."*
- Delete: *"The root access key will be permanently deleted. This cannot be undone. Root MFA must be active."*

---

#### Config.1 — AWS Config Not Enabled

**Question:** *"How should AWS Config be set up?"*

| Field | Type | Default | Description |
|---|---|---|---|
| Recording scope | `select` | "All resources" | Options: "All resources", "Keep existing scope" (if recorder exists) |
| Delivery bucket | `select` | "Create new" | Options: "Create a new dedicated bucket", "Use existing bucket" |
| Existing bucket name | `string` | — | Visible when "Use existing bucket" selected |
| Encrypt with KMS | `boolean` | `false` | Toggle: "Encrypt Config delivery with a KMS key" |
| KMS key ARN | `string` | — | Visible when encrypt = true |

---

#### CloudTrail.1 — CloudTrail Not Enabled

**Question:** *"Configure your CloudTrail logging"*

| Field | Type | Default | Description |
|---|---|---|---|
| Trail name | `string` | "security-autopilot-trail" | Name for the CloudTrail trail |
| Create bucket policy | `boolean` | `true` | "Automatically add the required S3 bucket policy for CloudTrail delivery" |
| Multi-region | `boolean` | `true` | "Enable multi-region logging" |

---

#### S3.5 — SSL Not Enforced

Impact text: *"After applying, all HTTP (non-HTTPS) requests to this bucket will receive a 403 Forbidden response."*

| Field | Type | Default | Description |
|---|---|---|---|
| Preserve existing policy | `boolean` | `true` (auto) | "Merge with existing bucket policy statements instead of replacing" |

---

#### S3.9 — Access Logging Not Enabled

| Field | Type | Default | Description |
|---|---|---|---|
| Log bucket name | `string` (required) | — | "Name of the S3 bucket to receive access logs (must be different from the source bucket)" |

---

#### S3.11 — No Lifecycle Configuration

| Field | Type | Default | Description |
|---|---|---|---|
| Abort incomplete uploads after | `number` | `7` | "Days after which incomplete multipart uploads are automatically cleaned up" |

---

#### S3.1 / S3.2 — Public Access Not Blocked

No inputs. Impact text only:
- **S3.1**: *"All four account-level public access block settings will be enabled."*
- **S3.2**: *"All four bucket-level public access block settings will be enabled for this specific bucket."*

---

#### S3.4 / S3.15 — Encryption

- **S3.4** (AES): No inputs. AES-256 automatic.
- **S3.15** (KMS): `select` — "AWS managed key (aws/s3)" or "Custom KMS key" (shows ARN input conditionally).

---

#### SecurityHub.1, GuardDuty.1, SSM.7, EC2.182, EC2.7

No input fields. Impact text only:

| Control | Impact text |
|---|---|
| SecurityHub.1 | "AWS Security Hub will be enabled in this region." |
| GuardDuty.1 | "Amazon GuardDuty will be enabled in this region." |
| SSM.7 | "Public sharing of SSM documents will be blocked." |
| EC2.182 | "Public access to EBS snapshots will be blocked at the account level." |
| EC2.7 | "All new EBS volumes in this region will be encrypted by default." |

---

### A3. Frontend — Enhanced Input Rendering

**File:** `frontend/src/components/RemediationModal.tsx`

| Field type | UI component |
|---|---|
| `string` | Text input (existing) |
| `string_array` | Textarea (existing) |
| `select` | Dropdown with label + description per option |
| `boolean` | Toggle switch |
| `cidr` | Text input with CIDR validation + "Detect my IP" button |
| `number` | Number input with min/max |

Additional frontend features:
- **Conditional visibility**: fields with `visible_when` only render when condition met
- **Impact preview**: shows `impact_text` below field groups in a highlighted box
- **Grouped layout**: fields with same `group` share a heading
- **Help popovers**: fields with `help_text` show info icon + tooltip

**File:** `frontend/src/lib/api.ts` — extend `StrategyInputSchemaField` type with new fields.

### A4. Backend — Impact Text in Preview

**File:** `backend/services/remediation_strategy.py`

Add `get_impact_summary(strategy_id, strategy_inputs) -> str` that composes a human-readable summary based on selected choices.

---

## Part B — UX Enhancements

### B1. Before/After Resource State Simulator

Show a live visual diff of what will change on the AWS resource before applying.

**Backend:** Add to `RemediationPreview` response:
```python
before_state: dict           # Current resource state snapshot
after_state: dict            # Predicted state after applying
diff_lines: list[dict]       # [{type: "remove"|"add"|"unchanged", label: str, value: str}]
```

**Per-control diffs:**
| Control | Before | After |
|---|---|---|
| EC2.53 | Inbound: 0.0.0.0/0 → port 22 | Inbound: 10.0.5.1/32 → port 22 |
| S3.5 | No SSL policy | Policy with Deny on non-HTTPS |
| Config.1 | No recorder | Recorder active, scope: all |
| S3.9 | Logging: disabled | Logging: target = log-bucket |

**Frontend:** Two-column card (Before / After) with green additions, red removals in `RemediationModal.tsx`.

---

### B2. Smart Defaults from AWS Context

Pre-fill fields using data already available:

| Control | Field | Auto-fill source |
|---|---|---|
| EC2.53 | `allowed_cidr` | Detect user's IP via `api.ipify.org` client-side |
| Config.1 | Recording scope | Pre-select "Keep existing" if recorder detected |
| Config.1 | Delivery bucket | Pre-fill `security-autopilot-config-{account_id}` |
| S3.15 | KMS key | List existing keys via `kms:ListAliases` probe |
| CloudTrail.1 | Bucket name | Pre-fill `security-autopilot-cloudtrail-{account_id}` |

**Backend:** Add KMS key list probe to `remediation_runtime_checks.py`. Return as `context.kms_key_options`.
**Frontend:** IP-detect fetch on modal open for EC2.53 actions.

---

### B3. Rollback Recipe Shown Upfront

Every control shows one precise rollback command in a collapsed section before Apply.

**Backend:** Add `rollback_command: str` to `RemediationOption`.

| Control | Rollback command |
|---|---|
| EC2.53 | `aws ec2 authorize-security-group-ingress --group-id {sg_id} --ip-permissions ...` |
| S3.5 | `aws s3api delete-bucket-policy --bucket {bucket}` |
| S3.9 | `aws s3api put-bucket-logging --bucket {bucket} --bucket-logging-status {}` |
| Config.1 | `aws configservice stop-configuration-recorder --configuration-recorder-name ...` |
| CloudTrail.1 | `aws cloudtrail stop-logging --name ...` |
| GuardDuty.1 | `aws guardduty delete-detector --detector-id {id}` |
| SecurityHub.1 | `aws securityhub disable-security-hub` |
| SSM.7 | `aws ssm update-service-setting --setting-id /ssm/documents/console/public-sharing-permission --setting-value Enable` |
| EC2.182 | `aws ec2 disable-snapshot-block-public-access` |
| EC2.7 | `aws ec2 disable-ebs-encryption-by-default` |

**Frontend:** Collapsed "How to undo this" with copy button, monospace formatting.

---

### B4. Estimated Time to Security Hub PASSED

Show realistic resolution estimate and optional re-eval trigger.

**Backend:** Add `estimated_resolution_time: str` and `supports_immediate_reeval: bool` to strategy.

| Control family | Estimate | Re-eval? |
|---|---|---|
| EC2, S3, IAM | 12–24 hours | Yes (Config rules) |
| Config.1, CloudTrail.1 | 1–6 hours | Partial |
| GuardDuty.1, SecurityHub.1 | ~1 hour | No |

**Backend:** New endpoint `POST /api/actions/{id}/trigger-reeval`.
**Frontend:** Checkbox "Trigger re-evaluation after apply" + estimate text below Apply button.

---

### B5. Blast Radius Indicator

Badge on modal header communicating scope and risk.

**Backend:** Add `blast_radius: "account" | "resource" | "access_changing"` to strategy.

| Badge | Controls |
|---|---|
| 🟢 Account-wide · Additive | SecurityHub.1, GuardDuty.1, SSM.7, EC2.182, EC2.7, S3.1, Config.1 |
| 🟡 Resource-specific · Additive | S3.4, S3.5, S3.9, S3.11, S3.15, CloudTrail.1 |
| 🔴 Access-changing · Review first | EC2.53 (auto-revoke), IAM.4 (delete) |

**Frontend:** Colored pill in modal header with tooltip.

---

### B6. "I Don't Know" Escape Hatches

Safe default paths for fields that might confuse SMB users.

| Control | Field | Escape hatch |
|---|---|---|
| S3.15 | KMS key ARN | "Not sure? Use aws/s3 — safest default" |
| EC2.53 | allowed_cidr | "Not sure? Detected 203.0.113.5 — or choose Close All" |
| Config.1 | Delivery bucket | "We'll create a dedicated bucket automatically" |
| S3.9 | Log bucket | "Recommend: `{source-bucket}-access-logs`" |
| CloudTrail.1 | Trail bucket | "Leave blank to create automatically" |

**Frontend:** Inline link below field: *"Not sure? [Use safe default →]"* that fills the value.

---

### B7. Post-Apply "What Changed" Summary Card

After successful apply, persist a structured summary on the finding/action detail page.

**Backend:** Write `change_summary` artifact after apply:
```json
{
  "applied_at": "2026-03-04T05:14:00Z",
  "applied_by": "user@company.com",
  "changes": [
    {"field": "SSH access", "before": "0.0.0.0/0", "after": "10.0.5.1/32"},
    {"field": "RDP access", "before": "0.0.0.0/0", "after": "removed"}
  ],
  "run_id": "abc-123"
}
```

**Frontend:** Card on action detail page:
> ✅ **Fixed on 2026-03-04** by `user@company.com` — SSH: 0.0.0.0/0 → 10.0.5.1/32 · [View run →]

**Files:** `pr_bundle_executor_worker.py` (write artifact), `ActionDetailDrawer.tsx` (render card).

---

### B8. Exception as a First-Class Choice

Present exceptions inline in the strategy list rather than as a fallback.

**Frontend:** Add explicit "I need an exception" at the bottom of strategy radio list:
> *"I can't apply this fix right now — create a time-limited exception"*
> ↳ Duration picker (7 / 14 / 30 / 90 days) + reason field inline

**Backend:** Exception duration and reason become `strategy_inputs` on the exception strategy. Uses existing `onChooseException` path but pre-populated.

---

## Verification Plan

### Automated Tests

**Command:** `PYTHONPATH=. ./venv/bin/pytest -q tests/test_step7_components.py -k "input_schema"`

Test cases:
1. Each control with interactive fields → assert expected field types/defaults in `input_schema.fields`
2. EC2.53 `select` field → 4 access mode options
3. `visible_when` rules on conditional fields
4. `impact_text` non-empty for every strategy option
5. S3.9 `log_bucket_name` → `required: true`
6. `rollback_command` present for every strategy
7. `blast_radius` set for every strategy
8. `estimated_resolution_time` set for every strategy

**Frontend type check:** `cd frontend && npx tsc --noEmit`

### Manual Verification

For each control, open the remediation modal and verify:
- EC2.53: 4-option dropdown; CIDR input reveals conditionally; IP auto-detected
- Config.1: scope pre-selected based on existing recorder; bucket pre-filled
- S3.9: log bucket blocked on submit if empty; escape hatch suggests a name
- All controls: before/after diff card renders; blast radius badge visible
- All controls: rollback command collapsed section present
- Post-apply: change summary card appears on finding/action detail
- Exception: duration + reason inline in modal without separate flow
