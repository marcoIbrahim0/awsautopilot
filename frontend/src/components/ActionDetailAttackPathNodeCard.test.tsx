import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import { ActionDetailAttackPathNodeCard } from "@/components/ActionDetailAttackPathNodeCard";
import type { ActionAttackPathNode } from "@/lib/api";

function buildNode(
  overrides: Partial<ActionAttackPathNode> = {},
): ActionAttackPathNode {
  return {
    node_id: "target-1",
    kind: "target_asset",
    label: "AWS::::Account:696505809372",
    detail: "AwsAccount · anchor",
    badges: ["business_critical"],
    facts: [
      { label: "Asset", value: "AwsAccount", tone: "accent" },
      {
        label: "Scope",
        value: "696505809372 · eu-north-1",
        tone: "code",
      },
    ],
    ...overrides,
  };
}

describe("ActionDetailAttackPathNodeCard", () => {
  it("renders fact rows directly from node facts", () => {
    render(<ActionDetailAttackPathNodeCard node={buildNode()} />);

    expect(screen.getByText("Target Asset")).toBeInTheDocument();
    expect(screen.getByText("Asset")).toBeInTheDocument();
    expect(screen.getByText("AwsAccount")).toBeInTheDocument();
    expect(screen.getByText("Scope")).toBeInTheDocument();
    expect(
      screen.getByText("696505809372 · eu-north-1"),
    ).toBeInTheDocument();
  });

  it("applies monospace wrapping classes to code-tone fact values", () => {
    render(<ActionDetailAttackPathNodeCard node={buildNode()} />);

    const scopeValue = screen.getByText("696505809372 · eu-north-1");
    expect(scopeValue.className).toContain("font-mono");
    expect(scopeValue.className).toContain("break-all");
  });

  it("omits the redundant recommended badge on the next-step card", () => {
    render(
      <ActionDetailAttackPathNodeCard
        node={buildNode({
          node_id: "next-1",
          kind: "next_step",
          label: "Disable public SSM document sharing",
          detail: "Changes stay scoped to the affected account.",
          badges: ["recommended"],
          facts: [
            { label: "Mode", value: "PR only", tone: "accent" },
            { label: "Blast radius", value: "Account", tone: "default" },
          ],
        })}
      />,
    );

    expect(screen.queryByText("Safest next step")).not.toBeInTheDocument();
    expect(screen.getByText("PR only")).toBeInTheDocument();
  });

  it("keeps non-next-step badges visible", () => {
    render(<ActionDetailAttackPathNodeCard node={buildNode()} />);

    expect(screen.getByText("Business critical")).toBeInTheDocument();
  });

  it("renders safely when backend nodes omit optional facts and badges", () => {
    render(
      <ActionDetailAttackPathNodeCard
        node={buildNode({
          badges: undefined,
          facts: undefined,
        })}
      />,
    );

    expect(screen.getByText("Target Asset")).toBeInTheDocument();
    expect(screen.getByText("AWS::::Account:696505809372")).toBeInTheDocument();
    expect(screen.queryByText("Asset")).not.toBeInTheDocument();
    expect(screen.queryByText("Business critical")).not.toBeInTheDocument();
  });
});
