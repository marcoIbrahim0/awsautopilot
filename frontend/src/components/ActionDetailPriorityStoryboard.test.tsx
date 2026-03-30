import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import { ActionDetailPriorityStoryboard } from "@/components/ActionDetailPriorityStoryboard";
import type {
  ActionBusinessImpact,
  ActionCriticalityDimension,
  ActionScoreFactor,
} from "@/lib/api";

vi.mock("motion/react", () => ({
  motion: {
    div: ({
      children,
      animate,
      initial,
      transition,
      ...props
    }: React.HTMLAttributes<HTMLDivElement> & {
      animate?: unknown;
      children: React.ReactNode;
      initial?: unknown;
      transition?: unknown;
    }) => (
      <div {...props}>{children}</div>
    ),
  },
}));

vi.mock("@/components/ui/AnimatedTooltip", () => ({
  AnimatedTooltip: ({
    children,
    content,
  }: {
    children: React.ReactNode;
    content?: React.ReactNode;
  }) => (
    <span
      data-tooltip-content={
        typeof content === "string" ? content : undefined
      }
    >
      {children}
    </span>
  ),
}));

function buildDimension(
  overrides: Partial<ActionCriticalityDimension>,
): ActionCriticalityDimension {
  return {
    contribution: 0,
    dimension: "customer_facing",
    explanation: "Customer-facing is explicit unknown for this action.",
    label: "Customer-facing",
    matched: false,
    signals: [],
    weight: 25,
    ...overrides,
  };
}

function buildImpact(
  dimensions: ActionCriticalityDimension[],
  overrides: Partial<ActionBusinessImpact> = {},
): ActionBusinessImpact {
  return {
    criticality: {
      dimensions,
      explanation: "Criticality scored 15 points from matched dimensions.",
      score: 15,
      status: "known",
      tier: "medium",
      weight: 2,
    },
    matrix_position: {
      cell: "high:medium",
      column: "medium",
      criticality_weight: 2,
      explanation:
        "Matrix row uses technical risk tier high; matrix column uses business criticality tier medium.",
      rank: 30276,
      risk_weight: 3,
      row: "high",
    },
    summary: "High technical risk intersects with Medium business criticality.",
    technical_risk_score: 76,
    technical_risk_tier: "high",
    ...overrides,
  };
}

function buildScoreFactor(
  factor_name: string,
  contribution: number,
): ActionScoreFactor {
  return {
    contribution,
    evidence_source: "unit_test",
    explanation: `${factor_name} explanation`,
    factor_name,
    provenance: [],
    signals: [],
    weight: Math.max(contribution, 0),
  };
}

function buildScoreFactors(): ActionScoreFactor[] {
  return [
    buildScoreFactor("severity", 35),
    buildScoreFactor("internet_exposure", 16),
    buildScoreFactor("privilege_level", 15),
    buildScoreFactor("data_sensitivity", 0),
  ];
}

describe("ActionDetailPriorityStoryboard", () => {
  it("keeps the mobile reading order and mutes zero-point factors", () => {
    render(
      <ActionDetailPriorityStoryboard
        actionType="iam_root_access_key_absent"
        businessImpact={buildImpact([
          buildDimension({
            contribution: 15,
            dimension: "identity_boundary",
            explanation: "Identity-boundary contributed 15 criticality points.",
            label: "Identity-boundary",
            matched: true,
            signals: ["resource_type:AwsAccount", "keyword:root user"],
            weight: 15,
          }),
        ])}
        scoreFactors={buildScoreFactors()}
      />,
    );

    const headline = screen.getByTestId("priority-storyboard-headline");
    const waterfall = screen.getByTestId("priority-storyboard-waterfall");
    const constellation = screen.getByTestId("priority-storyboard-constellation");
    const command = screen.getByTestId("priority-storyboard-command");

    expect(
      screen.getAllByText(
        /high-risk issue affecting your shared access boundary/i,
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Severity")).toBeInTheDocument();
    expect(screen.getByText("+35")).toBeInTheDocument();
    expect(screen.getByText("Internet Exposure")).toBeInTheDocument();
    expect(screen.getByText("+16")).toBeInTheDocument();
    expect(screen.getByText("Privilege Level")).toBeInTheDocument();
    expect(screen.getByText("+15")).toBeInTheDocument();
    expect(screen.getByText("Data Sensitivity")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getAllByText("Shared access boundary").length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getByText("Score waterfall").closest("[data-tooltip-content]"),
    ).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining("biggest reasons this action was pushed up or down"),
    );
    expect(
      screen.getByText("Visible lift +66").closest("[data-tooltip-content]"),
    ).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining("extra urgency comes from the reasons listed"),
    );
    expect(
      screen.getByText("Severity").closest("[data-tooltip-content]"),
    ).toHaveAttribute(
      "data-tooltip-content",
      "Severity added +35. This is about how serious the finding itself is.",
    );
    expect(
      screen.getByText(/Focus dimension:/i).closest("[data-tooltip-content]"),
    ).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining("main business clue behind"),
    );
    expect(
      screen.getByText(/Immediately audit break-glass workflows and rotations/i),
    ).toBeInTheDocument();
    expect(
      screen
        .getByText("Data Sensitivity")
        .closest('[data-factor-tone="muted"]'),
    ).not.toBeNull();
    expect(
      headline.compareDocumentPosition(waterfall) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      waterfall.compareDocumentPosition(constellation) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      constellation.compareDocumentPosition(command) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("renders up to three business-impact evidence nodes around the primary dimension", () => {
    render(
      <ActionDetailPriorityStoryboard
        actionType="unknown_action_type"
        businessImpact={buildImpact([
          buildDimension({
            contribution: 15,
            dimension: "identity_boundary",
            explanation: "Identity-boundary contributed 15 criticality points.",
            label: "Identity-boundary",
            matched: true,
            signals: ["resource_type:AwsAccount"],
            weight: 15,
          }),
          buildDimension({
            contribution: 10,
            dimension: "production_environment",
            explanation:
              "Production-environment contributed 10 criticality points.",
            label: "Production-environment",
            matched: true,
            signals: ["tag:env=prod"],
            weight: 10,
          }),
          buildDimension({
            contribution: 8,
            dimension: "regulated_data",
            explanation: "Regulated-data contributed 8 criticality points.",
            label: "Regulated-data",
            matched: true,
            signals: ["tag:data_classification=pii"],
            weight: 8,
          }),
        ])}
        scoreFactors={buildScoreFactors()}
      />,
    );

    expect(
      screen.getByTestId("priority-storyboard-primary-node"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("priority-storyboard-evidence-grid"),
    ).toBeInTheDocument();
    expect(
      screen
        .getByText("Impact constellation")
        .closest("[data-tooltip-content]"),
    ).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining("why the issue could matter to the business"),
    );
    expect(screen.getByText("Why it matters")).toBeInTheDocument();
    expect(screen.getByText("Production environment")).toBeInTheDocument();
    expect(screen.getByText("Sensitive or regulated data")).toBeInTheDocument();
    expect(
      screen.getAllByText(/This control affects IAM trust boundaries/i).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText(/This asset is tied to production/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /This resource is connected to regulated or sensitive data classes/i,
      ),
    ).toBeInTheDocument();
  });

  it("falls back cleanly when no business dimensions are matched and criticality is unknown", () => {
    const dimensions = [
      buildDimension({
        dimension: "identity_boundary",
        label: "Identity-boundary",
        weight: 15,
      }),
      buildDimension({
        dimension: "production_environment",
        label: "Production-environment",
        weight: 10,
      }),
      buildDimension({
        dimension: "regulated_data",
        label: "Regulated-data",
      }),
    ];

    render(
      <ActionDetailPriorityStoryboard
        actionType="s3_block_public_access"
        businessImpact={buildImpact(dimensions, {
          criticality: {
            dimensions,
            explanation: "Criticality remains explicit unknown.",
            score: 0,
            status: "unknown",
            tier: "unknown",
            weight: 1,
          },
        })}
        scoreFactors={buildScoreFactors()}
      />,
    );

    expect(
      screen.getAllByText(/Business context is unverified/i).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Business context pending")).toBeInTheDocument();
    expect(screen.getByText("Context missing")).toBeInTheDocument();
    expect(
      screen.getByText("Context missing").closest("[data-tooltip-content]"),
    ).toHaveAttribute(
      "data-tooltip-content",
      expect.stringContaining(
        "do not yet know enough about the affected system",
      ),
    );
    expect(
      screen.getByText(/Tag this account with environment/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Verify whether any S3 buckets in this account serve intentionally public content/i,
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText("Why it matters")).not.toBeInTheDocument();
  });
});
