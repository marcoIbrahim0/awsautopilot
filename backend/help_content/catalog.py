from __future__ import annotations

from typing import TypedDict


class HelpArticleSeed(TypedDict):
    slug: str
    title: str
    summary: str
    body: str
    audience: str
    published: bool
    sort_order: int
    tags: list[str]
    related_routes: list[str]


HELP_ARTICLE_SEEDS: list[HelpArticleSeed] = [
    {
        "slug": "getting-started-account-setup",
        "title": "Get started with account setup",
        "summary": "Create your tenant, finish onboarding, and connect your first AWS account.",
        "body": (
            "Use the onboarding flow to connect your first AWS account with the ReadRole contract.\n\n"
            "Start in Onboarding and complete the steps for Integration Role, Inspector, Security Hub + Config, "
            "and the control-plane checks. When onboarding succeeds, the Accounts page becomes the ongoing place "
            "to monitor validation state and queue ingest.\n\n"
            "If a connected account shows pending or error, rerun the relevant onboarding checks and verify the "
            "configured regions and ReadRole ARN are correct."
        ),
        "audience": "customer",
        "published": True,
        "sort_order": 10,
        "tags": ["onboarding", "account", "readrole", "validation"],
        "related_routes": ["/onboarding", "/accounts"],
    },
    {
        "slug": "connect-and-validate-aws",
        "title": "Connect and validate an AWS account",
        "summary": "Understand the ReadRole contract, regions, and validation outcomes for connected accounts.",
        "body": (
            "AWS Security Autopilot currently uses the customer ReadRole and does not rely on direct-fix execution "
            "or the WriteRole in active onboarding flows.\n\n"
            "On the Accounts page you can inspect account health, monitored regions, and last validation time. "
            "If validation fails, open the account detail flow, review onboarding checks, and confirm Security Hub, "
            "Inspector, AWS Config, and control-plane readiness for the selected regions."
        ),
        "audience": "customer",
        "published": True,
        "sort_order": 20,
        "tags": ["aws", "accounts", "security hub", "inspector", "config"],
        "related_routes": ["/accounts", "/onboarding"],
    },
    {
        "slug": "understand-findings-and-actions",
        "title": "Understand findings and actions",
        "summary": "Findings are raw signals. Actions are the prioritized remediation units you should work from.",
        "body": (
            "Findings are the raw security signals ingested from AWS services such as Security Hub, Access Analyzer, "
            "and Inspector. Actions group and prioritize those findings into remediation work.\n\n"
            "Use Findings when you need source-level details. Use Actions when you need the recommended remediation "
            "queue, execution guidance, and PR bundle workflow. If a finding includes a linked remediation action, "
            "open the action detail view to see the recommended next step."
        ),
        "audience": "customer",
        "published": True,
        "sort_order": 30,
        "tags": ["findings", "actions", "prioritization", "triage"],
        "related_routes": ["/findings", "/actions", "/top-risks"],
    },
    {
        "slug": "exceptions-and-governance",
        "title": "Work with exceptions and governance",
        "summary": "Use exceptions for documented risk acceptance with reason, expiry, and review visibility.",
        "body": (
            "Exceptions suppress or risk-acknowledge findings and actions for a bounded period. They should include "
            "a clear reason, an expiry date, and any supporting ticket link.\n\n"
            "Governance notifications and the notification center surface expiring or action-required states. "
            "If you are unsure whether a case should be suppressed or remediated, capture the action or finding id "
            "in a help request so support can review the exact workflow."
        ),
        "audience": "customer",
        "published": True,
        "sort_order": 40,
        "tags": ["exceptions", "governance", "notifications"],
        "related_routes": ["/exceptions", "/settings?tab=governance"],
    },
    {
        "slug": "pr-bundles-and-remediation-runs",
        "title": "Use PR bundles and remediation runs",
        "summary": "Remediation is currently PR-bundle first. Review the generated artifacts and run them through your workflow.",
        "body": (
            "The current supported remediation path is reviewed PR bundles and customer-run execution artifacts. "
            "Direct-fix execution and customer WriteRole workflows remain out of scope.\n\n"
            "Open an action detail page to review execution guidance, remediation options, and any related PR bundle "
            "runs. Use Remediation Runs to inspect generated artifacts, run activity, and closure evidence."
        ),
        "audience": "customer",
        "published": True,
        "sort_order": 50,
        "tags": ["pr bundles", "remediation", "runs", "artifacts"],
        "related_routes": ["/actions", "/pr-bundles", "/remediation-runs"],
    },
    {
        "slug": "notifications-and-shared-files",
        "title": "Use notifications and shared files",
        "summary": "Track background jobs and governance alerts in the bell, and download files shared by support.",
        "body": (
            "The notification center in the top bar shows background job progress and governance alerts. "
            "Unread items stay visible until you mark them read or archive them.\n\n"
            "Support may also share artifacts or guidance files through Shared Files. These files are visible in the "
            "Help Hub and are separate from private case attachments."
        ),
        "audience": "customer",
        "published": True,
        "sort_order": 60,
        "tags": ["notifications", "shared files", "support"],
        "related_routes": ["/help", "/support-files"],
    },
    {
        "slug": "settings-and-integrations",
        "title": "Configure settings and integrations",
        "summary": "Use Settings for notifications, governance, integrations, team management, and exports.",
        "body": (
            "Settings is the canonical admin surface for account profile, team management, organization settings, "
            "notifications, integrations, governance controls, remediation defaults, and exports/compliance.\n\n"
            "If an integration is failing, include the provider and the affected route in your help request. "
            "If the issue involves Jira, ServiceNow, or Slack sync, support will usually need the relevant action id "
            "or external-link context to diagnose it."
        ),
        "audience": "customer",
        "published": True,
        "sort_order": 70,
        "tags": ["settings", "jira", "servicenow", "slack", "exports"],
        "related_routes": ["/settings"],
    },
    {
        "slug": "when-to-contact-support",
        "title": "When to contact support",
        "summary": "Escalate when onboarding is blocked, validation repeatedly fails, or a route behaves differently than expected.",
        "body": (
            "Contact support when onboarding checks stay blocked after rerunning them, an account cannot validate, "
            "a remediation workflow appears incorrect, or the app shows a route-specific error you cannot resolve "
            "from the Help Center.\n\n"
            "For the fastest response, open support from the page where the problem occurred so the request includes "
            "the route, account, action, or finding context automatically."
        ),
        "audience": "customer",
        "published": True,
        "sort_order": 80,
        "tags": ["support", "troubleshooting", "cases"],
        "related_routes": ["/help", "/onboarding", "/accounts", "/actions", "/findings", "/settings"],
    },
]
