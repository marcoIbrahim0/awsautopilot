import "@testing-library/jest-dom/vitest";

import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ActionDetailModal } from "@/components/ActionDetailModal";
import {
  type ActionDetail,
  type ActionRecommendation,
  createException,
  createRemediationRun,
  getAction,
  getAccounts,
  getRemediationOptions,
  getRemediationPreview,
  triggerIngest,
  listManualWorkflowEvidence,
  listRemediationRuns,
  type RemediationOptionsResponse,
  type RemediationRunListItem,
  triggerActionReevaluation,
} from "@/lib/api";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

vi.mock("motion/react", () => ({
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  motion: {
    div: ({
      children,
      ...props
    }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
  },
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { role: "admin" },
  }),
}));

const mockAddJob = vi.fn(() => "job-1");
const mockCompleteJob = vi.fn();
const mockFailJob = vi.fn();
const mockUpdateJob = vi.fn();

vi.mock("@/contexts/BackgroundJobsContext", () => ({
  useBackgroundJobs: () => ({
    addJob: mockAddJob,
    completeJob: mockCompleteJob,
    failJob: mockFailJob,
    updateJob: mockUpdateJob,
  }),
}));

vi.mock("@/lib/tenant", () => ({
  useTenantId: () => ({
    tenantId: "tenant-1",
    setTenantId: vi.fn(),
  }),
}));

vi.mock("@/components/ui/AnimatedTooltip", () => ({
  AnimatedTooltip: ({
    children,
    content,
    focusable,
    placement,
  }: {
    children: React.ReactNode;
    content?: React.ReactNode;
    focusable?: boolean;
    placement?: string;
  }) => (
    <span
      data-focusable={focusable ? "true" : undefined}
      data-placement={placement}
      data-tooltip-content={
        typeof content === "string" ? content : undefined
      }
    >
      {children}
    </span>
  ),
}));

vi.mock("@/components/ActionDetailPriorityStoryboard", () => ({
  ActionDetailPriorityStoryboard: () => (
    <div data-testid="priority-storyboard">Priority storyboard</div>
  ),
}));

vi.mock("@/components/ActionDetailAttackPathNodeCard", () => ({
  ActionDetailAttackPathNodeCard: ({
    node,
  }: {
    node: { label: string };
  }) => <div>{node.label}</div>,
}));

vi.mock("@/components/RemediationRunProgress", () => ({
  RemediationRunProgress: ({ runId }: { runId: string }) => (
    <div>Progress for {runId}</div>
  ),
}));

vi.mock("@/lib/api", () => ({
  createException: vi.fn(),
  createRemediationRun: vi.fn(),
  createRootKeyRemediationRun: vi.fn(),
  getAction: vi.fn(),
  getAccounts: vi.fn(),
  getErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
  getRemediationOptions: vi.fn(),
  getRemediationPreview: vi.fn(),
  triggerIngest: vi.fn(),
  isApiError: (error: unknown) =>
    typeof error === "object" && error !== null && "status" in error,
  listManualWorkflowEvidence: vi.fn(),
  listRemediationRuns: vi.fn(),
  triggerActionReevaluation: vi.fn(),
  uploadManualWorkflowEvidence: vi.fn(),
}));

const mockedCreateException = vi.mocked(createException);
const mockedCreateRemediationRun = vi.mocked(createRemediationRun);
const mockedGetAction = vi.mocked(getAction);
const mockedGetAccounts = vi.mocked(getAccounts);
const mockedGetRemediationOptions = vi.mocked(getRemediationOptions);
const mockedGetRemediationPreview = vi.mocked(getRemediationPreview);
const mockedTriggerIngest = vi.mocked(triggerIngest);
const mockedListManualWorkflowEvidence = vi.mocked(listManualWorkflowEvidence);
const mockedListRemediationRuns = vi.mocked(listRemediationRuns);
const mockedTriggerActionReevaluation = vi.mocked(triggerActionReevaluation);

const DEFAULT_RECOMMENDATION: ActionRecommendation = {
  advisory: false,
  default_mode: "pr_only",
  evidence: {
    context_incomplete: false,
    data_sensitivity: 0,
    exploit_signals: 0,
    internet_exposure: 0,
    matched_signals: [],
    privilege_level: 0,
    score: 0,
  },
  matrix_position: {
    business_criticality: "medium",
    cell: "C2",
    risk_tier: "high",
  },
  mode: "pr_only",
  rationale: "Recommended PR bundle strategy.",
};

function buildActionDetail(): ActionDetail {
  return {
    account_id: "123456789012",
    action_type: "aws_config_enabled",
    business_impact: {
      criticality: {
        dimensions: [],
        explanation: "Business context is known.",
        score: 10,
        status: "known",
        tier: "medium",
        weight: 1,
      },
      matrix_position: {
        cell: "high:medium",
        column: "medium",
        criticality_weight: 2,
        explanation: "High technical risk intersects with medium criticality.",
        rank: 10,
        risk_weight: 3,
        row: "high",
      },
      summary: "High technical risk intersects with medium business criticality.",
      technical_risk_score: 82,
      technical_risk_tier: "high",
    },
    control_id: "Config.1",
    created_at: "2026-03-13T00:00:00Z",
    description: "AWS Config is not enabled.",
    execution_guidance: [],
    findings: [
      {
        account_id: "123456789012",
        finding_id: "finding-1",
        id: "finding-1",
        region: "us-east-1",
        resource_id: null,
        severity_label: "HIGH",
        title: "AWS Config disabled",
        updated_at: "2026-03-13T00:00:00Z",
      },
    ],
    id: "action-1",
    path_id: "path-1",
    implementation_artifacts: [],
    owner_key: "svc-platform",
    owner_label: "Platform",
    owner_type: "service",
    priority: 1,
    recommendation: DEFAULT_RECOMMENDATION,
    region: "us-east-1",
    resource_id: "123456789012",
    resource_type: "AwsAccount",
    score: 82,
    score_factors: [],
    status: "open",
    target_id: "account:123456789012",
    tenant_id: "tenant-1",
    title: "Enable AWS Config",
    updated_at: "2026-03-13T00:00:00Z",
    what_is_wrong: "AWS Config is disabled for this account.",
    what_the_fix_does: "Enables AWS Config with the selected delivery strategy.",
  } satisfies ActionDetail;
}

function buildActionDetailWithAttackPath(): ActionDetail {
  const action = buildActionDetail();
  return {
    ...action,
    attack_path_view: {
      availability_reason: null,
      business_impact_summary:
        "Compromise would affect a shared production-facing configuration path.",
      confidence: 0.82,
      entry_points: [],
      path_edges: [
        {
          label: "reaches",
          source_node_id: "entry-1",
          target_node_id: "target-1",
        },
      ],
      path_nodes: [
        {
          badges: ["entry"],
          detail: "Public access exposes the current configuration path.",
          facts: [],
          kind: "entry_point",
          label: "Public config access",
          node_id: "entry-1",
        },
        {
          badges: ["target"],
          detail: "The attacker reaches a production-facing configuration rule.",
          facts: [],
          kind: "target_asset",
          label: "Trusted Config Rule",
          node_id: "target-1",
        },
      ],
      recommendation_summary: "Review the shared production dependency first.",
      risk_reasons: ["Shared production dependency"],
      status: "available",
      summary:
        "An attacker can abuse Public config access to reach Trusted Config Rule.",
      target_assets: [],
      truncated: false,
    },
    business_impact: {
      ...action.business_impact,
      criticality: {
        ...action.business_impact.criticality,
        dimensions: [
          {
            contribution: 25,
            dimension: "customer_facing",
            explanation:
              "Customer-facing contributed 25 criticality points using: keyword:customer portal.",
            label: "Customer-facing",
            matched: true,
            signals: ["keyword:customer portal"],
            weight: 25,
          },
        ],
        explanation:
          "Criticality scored 25 points from matched dimensions including customer-facing.",
        score: 25,
        tier: "high",
        weight: 2,
      },
      matrix_position: {
        ...action.business_impact.matrix_position,
        cell: "high:high",
        column: "high",
        explanation:
          "Matrix row uses technical risk tier high; matrix column uses business criticality tier high.",
      },
      summary: "High technical risk intersects with High business criticality.",
    },
  } satisfies ActionDetail;
}

function buildActionDetailWithException(): ActionDetail {
  return {
    ...buildActionDetail(),
    exception_expired: false,
    exception_expires_at: "2026-04-12T00:00:00Z",
    exception_id: "exception-1",
  };
}

function buildActionDetailWithJiraSync(): ActionDetail {
  return {
    ...buildActionDetail(),
    external_sync: [
      {
        provider: "jira",
        external_id: "10001",
        external_key: "SEC-9",
        external_url: "https://jira.example/browse/SEC-9",
        external_status: "In Progress",
        sync_status: "drifted",
        preferred_external_status: "To Do",
        mapped_internal_status: "in_progress",
        canonical_internal_status: "open",
        resolution_decision: "preserve_internal",
        conflict_reason: "Platform state remains authoritative until outbound reconciliation succeeds.",
        last_inbound_at: "2026-03-30T10:05:00Z",
        last_outbound_at: "2026-03-30T10:06:00Z",
        last_event_at: "2026-03-30T10:07:00Z",
        last_reconciled_at: "2026-03-30T10:08:00Z",
        assignee_sync_state: "verified",
        assignee_sync_detail: "Jira assignee accountId acct-42 will be used on outbound sync.",
        recent_events: [
          {
            id: "evt-1",
            source: "external",
            event_type: "external_observed",
            created_at: "2026-03-30T10:05:00Z",
            external_status: "In Progress",
            preferred_external_status: "To Do",
            resolution_decision: "preserve_internal",
            decision_detail: "Observed Jira drift without changing the canonical platform action state.",
          },
        ],
      },
    ],
  } satisfies ActionDetail;
}

function buildPrOnlyOptions(): RemediationOptionsResponse {
  return {
    action_id: "action-1",
    action_type: "aws_config_enabled",
    manual_workflow: null,
    mode_options: ["pr_only"],
    recommendation: DEFAULT_RECOMMENDATION,
    strategies: [
      {
        blast_radius: "resource",
        dependency_checks: [],
        estimated_resolution_time: "1-6 hours",
        exception_only: false,
        input_schema: { fields: [] },
        label: "Enable AWS Config with account-local delivery",
        mode: "pr_only",
        recommended: true,
        requires_inputs: false,
        risk_level: "medium",
        rollback_command:
          "aws configservice stop-configuration-recorder --configuration-recorder-name <RECORDER_NAME>",
        strategy_id: "config_enable_account_local_delivery",
        supports_exception_flow: false,
        supports_immediate_reeval: true,
        warnings: [],
      },
      {
        blast_radius: "resource",
        dependency_checks: [
          {
            code: "config_visibility_gap",
            message: "Keeping AWS Config disabled reduces visibility.",
            status: "warn",
          },
        ],
        estimated_resolution_time: "1-6 hours",
        exception_only: true,
        input_schema: {
          fields: [
            {
              default_value: "30",
              description: "How long should this exception remain active?",
              key: "exception_duration_days",
              options: [
                { label: "7 days", value: "7" },
                { label: "14 days", value: "14" },
                { label: "30 days", value: "30" },
                { label: "90 days", value: "90" },
              ],
              required: false,
              type: "select",
            },
            {
              description: "Why can't you apply this fix right now?",
              key: "exception_reason",
              required: false,
              type: "string",
            },
          ],
        },
        label: "Keep current state (exception path)",
        mode: "pr_only",
        recommended: false,
        requires_inputs: true,
        risk_level: "high",
        rollback_command:
          "aws configservice stop-configuration-recorder --configuration-recorder-name <RECORDER_NAME>",
        strategy_id: "config_keep_exception",
        supports_exception_flow: true,
        supports_immediate_reeval: true,
        warnings: [
          "Skipping Config reduces change visibility and audit evidence quality.",
        ],
      },
    ],
  } satisfies RemediationOptionsResponse;
}

describe("ActionDetailModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        json: async () => ({ ip: "203.0.113.10" }),
        ok: true,
      }),
    );

    mockedGetAction.mockResolvedValue(buildActionDetail());
    mockedGetAccounts.mockResolvedValue([
      {
        account_id: "123456789012",
        created_at: "2026-03-13T00:00:00Z",
        id: "account-1",
        last_validated_at: "2026-03-13T00:00:00Z",
        regions: ["us-east-1"],
        role_read_arn: "arn:aws:iam::123456789012:role/ReadRole",
        role_write_arn: "arn:aws:iam::123456789012:role/WriteRole",
        status: "validated",
        updated_at: "2026-03-13T00:00:00Z",
      },
    ]);
    mockedGetRemediationOptions.mockResolvedValue(buildPrOnlyOptions());
    mockedGetRemediationPreview.mockResolvedValue({
      compliant: false,
      diff_lines: [
        {
          label: "Configuration recorder",
          type: "add",
          value: "enabled",
        },
      ],
      message: "Config recorder will be enabled.",
      will_apply: true,
    });
    mockedListManualWorkflowEvidence.mockResolvedValue([]);
    mockedListRemediationRuns.mockResolvedValue({ items: [], total: 0 });
    mockedTriggerIngest.mockResolvedValue({
      account_id: "123456789012",
      jobs_queued: 1,
      regions: ["us-east-1"],
      message_ids: ["msg-1"],
      message: "Ingest jobs queued",
    });
    mockedTriggerActionReevaluation.mockResolvedValue({
      action_id: "action-1",
      enqueued_jobs: 1,
      estimated_resolution_time: "1-6 hours",
      message: "Immediate re-evaluation jobs queued",
      scope: { account_id: "123456789012", region: "us-east-1" },
      strategy_id: "config_enable_account_local_delivery",
      supports_immediate_reeval: true,
      tenant_id: "tenant-1",
    });
    mockedCreateException.mockResolvedValue({
      approved_by_email: null,
      approved_by_user_id: "user-1",
      created_at: "2026-03-13T00:00:00Z",
      entity_id: "action-1",
      entity_type: "action",
      expires_at: "2026-04-12T00:00:00Z",
      id: "exception-1",
      reason: "Approved temporary exception due to rollout freeze.",
      ticket_link: null,
      tenant_id: "tenant-1",
      updated_at: "2026-03-13T00:00:00Z",
    });
    mockedCreateRemediationRun.mockResolvedValue({
      action_id: "action-1",
      created_at: "2026-03-13T00:00:00Z",
      id: "run-1",
      mode: "pr_only",
      status: "pending",
      updated_at: "2026-03-13T00:00:00Z",
    });
  });

  it("renders the same action-detail modal shell on server and client without a hydration mismatch", async () => {
    const onClose = vi.fn();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const container = document.createElement("div");
    document.body.appendChild(container);
    let root: ReturnType<typeof hydrateRoot> | null = null;

    try {
      const html = renderToString(
        <ActionDetailModal actionId="action-1" isOpen={true} onClose={onClose} />,
      );

      expect(html).toContain("Action Detail");
      container.innerHTML = html;

      await act(async () => {
        root = hydrateRoot(
          container,
          <ActionDetailModal actionId="action-1" isOpen={true} onClose={onClose} />,
        );
        await Promise.resolve();
      });

      await waitFor(() => {
        expect(mockedGetAction).toHaveBeenCalledWith("action-1", undefined);
      });

      const hydrationMessages = consoleError.mock.calls
        .flatMap((args) => args.map((arg) => String(arg)))
        .filter(
          (message) =>
            message.includes("Hydration failed") ||
            message.includes("server rendered HTML"),
        );

      expect(hydrationMessages).toHaveLength(0);
    } finally {
      if (root) {
        await act(async () => {
          root?.unmount();
        });
      }
      consoleError.mockRestore();
      container.remove();
    }
  });

  it("wires hover explanations into the action header and bounded attack-path labels", async () => {
    mockedGetAction.mockResolvedValue(buildActionDetailWithAttackPath());

    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await screen.findByRole("dialog", { name: "Action Detail" });

    expect((await screen.findByText("Risk 82")).parentElement).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining("overall danger rating for this issue"),
    );
    expect(
      screen.getByText("High risk x High criticality").parentElement,
    ).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining("mixes two ideas"),
    );
    expect(screen.getByText("Bounded decision view").parentElement).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining("short, simplified story"),
    );
    expect(screen.getByText("Business critical").parentElement).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining("business cares about a lot"),
    );
    expect(
      screen.getByRole("link", { name: "Open Attack Paths" }),
    ).toHaveAttribute("href", "/attack-paths?path_id=path-1");
  });

  it("renders Jira external sync details when a linked issue exists", async () => {
    mockedGetAction.mockResolvedValue(buildActionDetailWithJiraSync());

    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    expect(await screen.findByText("External Sync")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "SEC-9" })).toHaveAttribute(
      "href",
      "https://jira.example/browse/SEC-9",
    );
    expect(
      screen.getByText(
        "Jira assignee accountId acct-42 will be used on outbound sync.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Observed Jira drift without changing the canonical platform action state.",
      ),
    ).toBeInTheDocument();
  });

  it("switches Generate PR bundle into the same dialog and returns to Action Detail on back", async () => {
    const user = userEvent.setup();
    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await screen.findByRole("dialog", { name: "Action Detail" });
    await user.click(
      screen.getByRole("button", { name: "Generate PR bundle" }),
    );

    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(
      await screen.findByRole("dialog", { name: "Generate PR Bundle" }),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("action-detail-pr-bundle-view"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Refresh State")).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Back to action detail" }),
    );

    expect(
      await screen.findByRole("dialog", { name: "Action Detail" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Refresh State")).toBeInTheDocument();
    expect(
      screen.queryByTestId("action-detail-pr-bundle-view"),
    ).not.toBeInTheDocument();
  });

  it("keeps run progress in the same popup and refreshes history when returning to detail", async () => {
    const user = userEvent.setup();
    mockedListRemediationRuns
      .mockResolvedValueOnce({ items: [], total: 0 })
      .mockResolvedValue({
        items: [
          {
            action_id: "action-1",
            artifacts_summary: "PR bundle",
            completed_at: null,
            created_at: "2026-03-13T00:05:00Z",
            id: "run-1",
            mode: "pr_only",
            outcome: "Queued",
            started_at: null,
            status: "pending",
          } satisfies RemediationRunListItem,
        ],
        total: 1,
      });

    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await screen.findByRole("dialog", { name: "Action Detail" });
    await user.click(
      screen.getByRole("button", { name: "Generate PR bundle" }),
    );

    await user.click(
      await screen.findByRole("button", { name: "Generate PR bundle" }),
    );

    expect(
      await screen.findByRole("dialog", { name: "Bundle progress" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Progress for run-1")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Back to action detail" }),
    );

    await screen.findByRole("dialog", { name: "Action Detail" });
    await waitFor(() => {
      expect(mockedListRemediationRuns.mock.calls.length).toBeGreaterThan(1);
    });
    expect(screen.getByText("Progress for run-1")).toBeInTheDocument();
  });

  it("switches Suppress into the same dialog and returns to Action Detail on back", async () => {
    const user = userEvent.setup();
    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await screen.findByRole("dialog", { name: "Action Detail" });
    await user.click(screen.getByRole("button", { name: "Suppress" }));

    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(
      await screen.findByRole("dialog", { name: "Suppress Action" }),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("action-detail-suppress-view"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Reason/i)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Back to action detail" }),
    );

    expect(
      await screen.findByRole("dialog", { name: "Action Detail" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("action-detail-suppress-view"),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suppress" })).toBeInTheDocument();
  });

  it("submits suppress inline, returns to Action Detail, and refreshes the action state", async () => {
    const user = userEvent.setup();
    mockedGetAction
      .mockResolvedValueOnce(buildActionDetail())
      .mockResolvedValue(buildActionDetailWithException());

    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await screen.findByRole("dialog", { name: "Action Detail" });
    await user.click(screen.getByRole("button", { name: "Suppress" }));
    await user.type(
      screen.getByLabelText(/Reason/i),
      "Approved temporary exception due to rollout freeze.",
    );
    await user.click(screen.getByRole("button", { name: "Create Exception" }));

    expect(
      await screen.findByRole("dialog", { name: "Action Detail" }),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(mockedCreateException).toHaveBeenCalledTimes(1);
      expect(mockedGetAction.mock.calls.length).toBeGreaterThan(1);
    });
    expect(
      screen.queryByRole("button", { name: "Suppress" }),
    ).not.toBeInTheDocument();
  });

  it("routes PR-bundle exception selection into the inline suppress view", async () => {
    const user = userEvent.setup();
    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await screen.findByRole("dialog", { name: "Action Detail" });
    await user.click(
      screen.getByRole("button", { name: "Generate PR bundle" }),
    );

    await user.click(screen.getByText("I need an exception"));
    const reasonInput = await screen.findByLabelText(
      "Why can't you apply this fix right now?",
    );
    await user.type(
      reasonInput,
      "Approved temporary exception due to rollout freeze.",
    );
    await user.click(screen.getByRole("button", { name: "Create exception" }));

    expect(
      await screen.findByRole("dialog", { name: "Suppress Action" }),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("action-detail-suppress-view"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("action-detail-pr-bundle-view"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByDisplayValue(
        "Approved temporary exception due to rollout freeze.",
      ),
    ).toBeInTheDocument();
  });

  it("shows reported rules and remediation family when the action belongs to a mapped control family", async () => {
    mockedGetAction.mockResolvedValue({
      ...buildActionDetail(),
      control_id: "EC2.53",
      control_family: {
        source_control_ids: ["EC2.18", "EC2.19"],
        canonical_control_id: "EC2.53",
        related_control_ids: ["EC2.53", "EC2.13", "EC2.18", "EC2.19"],
        is_mapped: true,
      },
    });

    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    expect(await screen.findByText("Reported rule(s)")).toBeInTheDocument();
    expect(screen.getByText("EC2.18, EC2.19")).toBeInTheDocument();
    expect(screen.getByText("Remediation family")).toBeInTheDocument();
    expect(screen.getByText("EC2.53")).toBeInTheDocument();
    expect(screen.getByText("EC2.18 +1 -> EC2.53")).toBeInTheDocument();
  });

  it("fetches remediation history with grouped runs included", async () => {
    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await screen.findByRole("dialog", { name: "Action Detail" });

    await waitFor(() => {
      expect(mockedListRemediationRuns).toHaveBeenCalledWith(
        {
          action_id: "action-1",
          include_group_related: true,
          limit: 10,
        },
        undefined,
      );
    });
  });

  it("uses targeted re-evaluation for Refresh State and dedupes the background job", async () => {
    const user = userEvent.setup();
    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await screen.findByRole("dialog", { name: "Action Detail" });
    await user.click(screen.getByRole("button", { name: "Refresh State" }));

    await waitFor(() => {
      expect(mockedTriggerActionReevaluation).toHaveBeenCalledWith(
        "action-1",
        undefined,
      );
    });
    expect(mockedTriggerIngest).not.toHaveBeenCalled();
    expect(mockAddJob).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Refreshing action state (action-1)",
        dedupeKey: "action-refresh:session:action-1",
        resourceId: "action-1",
        actorId: "session",
      }),
    );
  });

  it("falls back to scoped ingest when immediate re-evaluation is unsupported", async () => {
    const user = userEvent.setup();
    mockedTriggerActionReevaluation.mockRejectedValue({
      error: "Bad Request",
      status: 400,
      detail: {
        error: "Immediate re-evaluation not supported",
        detail: "Immediate re-evaluation is not supported for this remediation strategy.",
      },
    });

    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await screen.findByRole("dialog", { name: "Action Detail" });
    await user.click(screen.getByRole("button", { name: "Refresh State" }));

    await waitFor(() => {
      expect(mockedTriggerIngest).toHaveBeenCalledWith(
        "123456789012",
        undefined,
        ["us-east-1"],
      );
    });
  });

  it("completes the refresh job when no visible change appears before the poll window ends", async () => {
    vi.useFakeTimers();

    render(
      <ActionDetailModal actionId="action-1" isOpen={true} onClose={vi.fn()} />,
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(
      screen.getByRole("dialog", { name: "Action Detail" }),
    ).toBeInTheDocument();
    act(() => {
      screen.getByRole("button", { name: "Refresh State" }).click();
    });

    await act(async () => {
      await Promise.resolve();
    });
    expect(mockedTriggerActionReevaluation).toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(45_000);
    });

    expect(mockCompleteJob).toHaveBeenCalledWith(
      "job-1",
      "Action refresh completed.",
      "No visible changes yet. Downstream refresh processing may still be finishing.",
    );
  });
});
