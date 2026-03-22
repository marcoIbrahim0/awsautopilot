# Remaining Phase 2 Features

These items were not implementable during the Phase 2 sprint because they each require infrastructure or pages that do not yet exist.

---

## E2 — Inline Resource Badges (Inventory View)

**What it is:** Yellow/red warning dot badges on a resource inventory page, indicating which AWS resources have active in-scope findings. Clicking a badge opens a side-panel with that resource's grouped findings.

**What's needed:**

1. **New page:** `/inventory` (or `/accounts/[id]/resources`) — lists AWS resources discovered across connected accounts (EC2 instances, S3 buckets, IAM roles, RDS instances, etc.)
2. **New backend endpoint:** `GET /resources` — returns a list of unique `resource_id` values with their `resource_type`, `account_id`, `region`, and an aggregated `finding_count` + `dominant_severity`. This is essentially `GET /findings/grouped` re-grouped by `resource_id` instead of `(control_id, resource_type)`.
3. **Badge component:** A small colour-coded dot (red = CRITICAL/HIGH, yellow = MEDIUM, grey = none/low) overlaid on each resource row. Already implementable once the page and data exist.
4. **Side panel:** Clicking the badge opens a drawer showing that resource's `FindingGroupCard` list — reuses existing components.

**Architecture decision needed:** Where does the resource inventory come from — Security Hub resource data from findings, or a separate AWS Config resource inventory sync?

---

## E3 — Notification Config (Slack / Email alerts)

**What it is:** Users configure a Slack webhook URL and/or email address. When ingestion completes and new in-scope Critical or High findings are detected, an alert fires.

**What's needed:**

1. **Database:** New `tenant_notification_config` table — columns: `tenant_id`, `slack_webhook_url`, `email_address`, `min_severity` (default `HIGH`), `enabled`.
2. **Alembic migration** for the new table.
3. **Backend CRUD:** `GET/PUT /notifications/config` endpoints in a new `notifications.py` router.
4. **Worker job:** After `compute_actions` completes, a new task `send_notifications` runs. It queries new findings (`created_at > last_notified_at`) filtered to in-scope + severity ≥ threshold, and dispatches:
   - **Slack:** HTTP POST to `slack_webhook_url` with a digest message (N critical, M high, top 3 rules).
   - **Email:** AWS SES `send_email` call to `email_address` with an HTML digest template.
5. **Settings UI:** A form in `/settings` — webhook URL field, email field, severity threshold dropdown, enable/disable toggle. Reuses existing `Button`, `SelectDropdown` components.
6. **Terraform:** SES verified identity + IAM policy granting `ses:SendEmail` to the ECS task role.

**Architecture decision needed:** Use AWS SES directly, or a third-party provider (Resend, SendGrid)? Use SNS as a fan-out layer, or call SES directly from the worker?

---

## §6 — "New Resources in Scope" Notification

**What it is:** When a resource's scope status changes from out-of-scope to in-scope (e.g. a new AWS account is added to the project), an in-app notification banner appears on the Findings page.

**What's needed:**

1. **Scope-change detection:** During ingestion, compare `Finding.in_scope` values before and after the new Security Hub pull. Any `resource_id` that transitions `False → True` is a "new in-scope resource" event.
2. **Notifications model:** A `tenant_notifications` table — `id`, `tenant_id`, `type` (`scope_change`), `payload` (JSON: new resource IDs, count), `created_at`, `read_at`.
3. **In-app banner:** A `NotificationBell` icon in `AppShell`'s top nav that polls `GET /notifications?unread=true`. On click, shows a dropdown list of recent notifications.
4. **Findings page banner:** On page load, if unread scope-change notifications exist, show a dismissible banner: *"3 new resources entered scope since your last visit — [View grouped findings]"*.

**Architecture decision needed:** Polling vs. WebSocket/SSE for real-time delivery? How long to retain notifications (7 days / 30 days)?
