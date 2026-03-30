import { describe, expect, it } from "vitest";

import {
  REMEDIATION_DIALOG_CLASS,
  REMEDIATION_DIALOG_HEADER_CLASS,
  remediationCalloutClass,
  remediationInsetClass,
  remediationPanelClass,
} from "@/components/ui/remediation-surface";

describe("remediation-surface", () => {
  it("swaps remediation panels and headers onto tokenized dashboard surfaces", () => {
    expect(remediationPanelClass("default")).toContain(
      "bg-[var(--card)]",
    );
    expect(REMEDIATION_DIALOG_HEADER_CLASS).toContain(
      "bg-[var(--card-hero)]",
    );
  });

  it("keeps inset and callout surfaces dark in every remediation tone", () => {
    const tones = [
      "default",
      "accent",
      "info",
      "success",
      "warning",
      "danger",
    ] as const;

    for (const tone of tones) {
      expect(remediationInsetClass(tone)).toContain(
        "dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]",
      );
    }

    expect(remediationCalloutClass("warning")).toContain(
      "dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]",
    );
  });

  it("preserves remediation dialog neumorphic dark tokens", () => {
    expect(REMEDIATION_DIALOG_CLASS).toContain("dark:[--nm-base:#010206]");
    expect(REMEDIATION_DIALOG_CLASS).toContain("bg-[var(--overlay)]");
  });
});
