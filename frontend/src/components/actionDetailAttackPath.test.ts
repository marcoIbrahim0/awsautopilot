import { describe, expect, it } from "vitest";

import type { ActionAttackPathView, ActionGraphContext } from "@/lib/api";
import { buildAttackPathSummaryContext } from "@/components/actionDetailAttackPath";

function buildView(
  overrides: Partial<ActionAttackPathView> = {},
): ActionAttackPathView {
  return {
    status: "partial",
    summary: "Privileged identity path can reach AWS::::Account:696505809372.",
    path_nodes: [],
    path_edges: [],
    entry_points: [],
    target_assets: [
      {
        node_id: "target-account",
        kind: "target_asset",
        label: "AWS::::Account:696505809372",
        detail: "AwsAccount · anchor",
        badges: [],
        facts: [],
      },
    ],
    business_impact_summary:
      "Medium technical risk intersects with Medium business criticality.",
    risk_reasons: [],
    recommendation_summary:
      "Safest next step: Enable CloudTrail logging (guided choices) via PR only.",
    confidence: 0.2,
    truncated: true,
    availability_reason: "bounded_context_truncated",
    ...overrides,
  };
}

function buildGraph(
  overrides: Partial<ActionGraphContext> = {},
): ActionGraphContext {
  return {
    status: "available",
    availability_reason: null,
    source: "finding_relationship_context+inventory_assets",
    self_resolved: false,
    connected_assets: [],
    identity_path: [],
    blast_radius_neighborhood: [],
    truncated_sections: ["connected_assets"],
    limits: {
      max_related_findings: 24,
      max_related_actions: 24,
      max_inventory_assets: 24,
      max_connected_assets: 6,
      max_identity_nodes: 6,
      max_blast_radius_neighbors: 6,
    },
    ...overrides,
  };
}

describe("buildAttackPathSummaryContext", () => {
  it("surfaces inline summary context for truncated bounded paths", () => {
    const context = buildAttackPathSummaryContext(
      {
        account_id: "696505809372",
        region: "us-east-1",
        resource_id: "AWS::::Account:696505809372",
        resource_type: "AwsAccount",
        target_id: "696505809372|us-east-1|CloudTrail.1",
      },
      buildView(),
      buildGraph(),
    );

    expect(context.entryLabel).toBe("Local risk context");
    expect(context.targetLabel).toBe("AWS::::Account:696505809372");
    expect(context.targetDetail).toBe("AwsAccount");
    expect(context.scopeLabel).toBe("696505809372 · us-east-1");
    expect(context.cautionLabel).toBe("Take care");
    expect(context.cautionDetail).toBe(
      "Extra graph context was capped to keep this view bounded.",
    );
    expect(context.nextStepLabel).toBe(
      "Enable CloudTrail logging (guided choices) via PR only.",
    );
    expect(context.impactLabel).toBe(
      "Medium technical risk intersects with Medium business criticality.",
    );
  });

  it("marks self-resolved paths without requiring a separate card view", () => {
    const context = buildAttackPathSummaryContext(
      {
        account_id: "696505809372",
        region: "us-east-1",
        resource_id: null,
        resource_type: null,
        target_id: "696505809372|us-east-1|CloudTrail.1",
      },
      buildView({
        status: "available",
        truncated: false,
        availability_reason: null,
        target_assets: [
          {
            node_id: "target-account",
            kind: "target_asset",
            label: "account:696505809372:region:us-east-1",
            detail: "account anchor",
            badges: [],
            facts: [],
          },
        ],
      }),
      buildGraph({ self_resolved: true, truncated_sections: [] }),
    );

    expect(context.targetLabel).toBe("account:696505809372:region:us-east-1");
    expect(context.targetDetail).toBe("account anchor");
    expect(context.scopeLabel).toBe("696505809372 · us-east-1");
    expect(context.cautionLabel).toBe("Autopilot note");
    expect(context.cautionDetail).toBe(
      "Provider metadata was missing, so this path was reconstructed from persisted action fields.",
    );
  });
});
