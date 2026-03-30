import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it, vi } from "vitest";

import {
  AnimatedTooltip,
  computeTooltipLayout,
} from "@/components/ui/AnimatedTooltip";

vi.mock("motion/react", () => ({
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  motion: {
    div: ({
      children,
      animate,
      initial,
      transition,
      exit,
      ...props
    }: React.HTMLAttributes<HTMLDivElement> & {
      animate?: unknown;
      children: React.ReactNode;
      exit?: unknown;
      initial?: unknown;
      transition?: unknown;
    }) => <div {...props}>{children}</div>,
  },
}));

function renderTooltip(props: Partial<React.ComponentProps<typeof AnimatedTooltip>> = {}) {
  return render(
    <AnimatedTooltip
      content="Tooltip copy"
      delayMs={0}
      focusable
      tapToToggle
      {...props}
    >
      <span>Risk 82</span>
    </AnimatedTooltip>,
  );
}

describe("AnimatedTooltip", () => {
  it("shows and hides on hover", async () => {
    const user = userEvent.setup();
    renderTooltip();
    const trigger = screen.getByText("Risk 82").parentElement as HTMLElement;

    await user.hover(trigger);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Tooltip copy");

    await user.unhover(trigger);
    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
  });

  it("opens on keyboard focus for focusable label triggers", async () => {
    renderTooltip();
    const trigger = screen.getByText("Risk 82").parentElement as HTMLElement;

    expect(trigger).toHaveAttribute("tabindex", "0");
    trigger.focus();

    expect(await screen.findByRole("tooltip")).toHaveTextContent("Tooltip copy");
  });

  it("toggles on touch press and closes on outside press", async () => {
    renderTooltip();
    const trigger = screen.getByText("Risk 82").parentElement as HTMLElement;

    fireEvent.pointerDown(trigger, { pointerType: "touch" });
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Tooltip copy");

    fireEvent.pointerDown(document.body, { pointerType: "touch" });
    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
  });

  it("supports left placement for edge-adjacent triggers", () => {
    renderTooltip({ forceShow: true, placement: "left" });
    const tooltip = screen.getByRole("tooltip", { hidden: true });

    expect(tooltip).toHaveAttribute("data-placement", "left");
    expect(tooltip.parentElement).toBe(document.body);
  });

  it("flips from top to bottom when the preferred placement would clip", () => {
    const originalWidth = window.innerWidth;
    const originalHeight = window.innerHeight;
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1280,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 800,
    });

    const layout = computeTooltipLayout(
      "top",
      {
        bottom: 34,
        height: 24,
        left: 100,
        right: 180,
        top: 10,
        width: 80,
      } as DOMRect,
      {
        height: 120,
        width: 240,
      } as DOMRect,
      true,
    );

    expect(layout.placement).toBe("bottom");

    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: originalWidth,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: originalHeight,
    });
  });
});
