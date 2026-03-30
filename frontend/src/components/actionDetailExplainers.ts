import type { BusinessImpactPanel } from "@/components/actionDetailBusinessImpact";
import type { ActionBusinessImpact, ActionScoreFactor } from "@/lib/api";

const BOUNDED_DECISION_VIEW_EXPLAINER =
  "This is a short, simplified story of how this issue could lead to harm. We keep it brief on purpose so it is easier to act on.";

const SCORE_WATERFALL_EXPLAINER =
  "This shows the biggest reasons this action was pushed up or down in the list. It is meant to explain the ranking, not be a precise chart.";

const FACTOR_PLAIN_LANGUAGE: Record<string, string> = {
  severity: "how serious the finding itself is",
  internet_exposure: "whether this looks open to the internet or public access",
  privilege_level: "whether powerful accounts or permissions are involved",
  data_sensitivity: "whether sensitive data or important information may be involved",
  exploit_signals: "whether attackers are likely to take advantage of it",
  toxic_combinations: "whether several smaller risks combine into a bigger problem",
  compensating_controls: "whether existing safeguards make it less urgent",
  score_bounds_adjustment: "a small guardrail that keeps the ranking in a sane range",
};

function compactParts(parts: Array<string | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function titleCaseToken(value: string): string {
  return value
    .replace(/[_-]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function joinLabels(labels: string[]): string {
  if (labels.length <= 1) return labels[0] ?? "";
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`;
  return `${labels.slice(0, -1).join(", ")}, and ${labels[labels.length - 1]}`;
}

function matchedDimensionLabels(impact: ActionBusinessImpact): string[] {
  return impact.criticality.dimensions
    .filter((dimension) => dimension.matched)
    .sort(
      (left, right) =>
        right.contribution - left.contribution || right.weight - left.weight,
    )
    .map((dimension) => titleCaseToken(dimension.label || dimension.dimension));
}

export function buildRiskScoreExplainer(score: number): string {
  return `This is the overall danger rating for this issue, out of 100. Right now it is ${score}, so the platform thinks it deserves relatively quick attention.`;
}

export function buildBusinessImpactBadgeExplainer(
  impact: ActionBusinessImpact,
): string {
  const riskTier = titleCaseToken(impact.technical_risk_tier).toLowerCase();
  const criticalityTier = titleCaseToken(impact.criticality.tier).toLowerCase();
  if (impact.criticality.status === "unknown") {
    return `We know this issue looks ${riskTier} risk. We do not yet know how important the affected system is to the business, so this label stays cautious.`;
  }
  return `This label mixes two ideas: how risky the issue looks, and how important the affected system seems to the business. Here, the risk looks ${riskTier} and the business importance looks ${criticalityTier}.`;
}

export function buildBusinessCriticalExplainer(
  impact: ActionBusinessImpact,
): string {
  const matched = matchedDimensionLabels(impact).slice(0, 2);
  const driverText =
    matched.length > 0
      ? `The strongest clue here is ${joinLabels(matched)}.`
      : null;
  return compactParts([
    "This means the issue may touch something the business cares about a lot, not just a technical setting.",
    driverText,
  ]);
}

export function getBoundedDecisionViewExplainer(): string {
  return BOUNDED_DECISION_VIEW_EXPLAINER;
}

export function getScoreWaterfallExplainer(): string {
  return SCORE_WATERFALL_EXPLAINER;
}

export function buildVisibleLiftExplainer(total: number): string {
  return `This number shows how much extra urgency comes from the reasons listed in this chart. Right now those visible reasons add +${total}.`;
}

export function buildScoreFactorExplainer(factor: ActionScoreFactor): string {
  const factorLabel = titleCaseToken(factor.factor_name);
  const explanation =
    FACTOR_PLAIN_LANGUAGE[factor.factor_name] ??
    "one of the signals used to judge urgency";
  if (factor.contribution > 0) {
    return `${factorLabel} added +${factor.contribution}. This is about ${explanation}.`;
  }
  if (factor.contribution < 0) {
    return `${factorLabel} reduced the score by ${Math.abs(factor.contribution)}. This is about ${explanation}.`;
  }
  return `${factorLabel} did not change the score this time. This is about ${explanation}.`;
}

export function buildImpactConstellationExplainer(
  panel: BusinessImpactPanel,
): string {
  const supporting = panel.evidenceCards.slice(1).map((card) => card.title);
  const supportingText =
    supporting.length > 0
      ? `The smaller cards are supporting clues, such as ${joinLabels(supporting)}.`
      : "If there are more clues, they appear as smaller supporting cards.";
  return compactParts([
    "This area explains why the issue could matter to the business.",
    supportingText,
  ]);
}

export function buildFocusDimensionExplainer(
  _impact: ActionBusinessImpact,
  primaryLabel: string | null,
): string {
  if (!primaryLabel) {
    return "This is the main business clue behind the badge on this action.";
  }
  return `${primaryLabel} is the main business clue behind this action's business-impact label.`;
}

export function buildContextMissingExplainer(
  _impact: ActionBusinessImpact,
  panel: BusinessImpactPanel,
): string {
  return compactParts([
    "We do not yet know enough about the affected system to say how important it is to the business.",
    panel.enrichmentPrompt
      ? "Adding owner, environment, or data tags will make this easier to judge next time."
      : null,
  ]);
}
