import type { BusinessImpactPanel } from "@/components/actionDetailBusinessImpact";
import {
  buildContextMissingExplainer,
  buildFocusDimensionExplainer,
  buildImpactConstellationExplainer,
  buildScoreFactorExplainer,
  buildVisibleLiftExplainer,
  getScoreWaterfallExplainer,
} from "@/components/actionDetailExplainers";
import type { ActionBusinessImpact, ActionScoreFactor } from "@/lib/api";

export interface PriorityStoryboardFactor {
  key: string;
  label: string;
  contribution: number;
  muted: boolean;
  laneStartPercent: number;
  laneWidthPercent: number;
  tooltip: string;
}

export interface PriorityStoryboardEvidenceNode {
  detail: string;
  id: string;
  title: string;
}

export interface PriorityStoryboardModel {
  activeContributionTotal: number;
  commandText: string;
  contextBadge: string | null;
  contextBadgeTooltip: string | null;
  evidenceNodes: PriorityStoryboardEvidenceNode[];
  factors: PriorityStoryboardFactor[];
  headline: string;
  focusDimensionTooltip: string | null;
  impactConstellationTooltip: string;
  primaryDetail: string | null;
  primaryLabel: string | null;
  scoreWaterfallTooltip: string;
  visibleLiftTooltip: string;
}

export function buildPriorityStoryboardModel(
  scoreFactors: ActionScoreFactor[],
  impact: ActionBusinessImpact,
  panel: BusinessImpactPanel,
): PriorityStoryboardModel {
  const factors = buildWaterfallFactors(scoreFactors);
  const primaryLabel = panel.evidenceCards[0]?.title ?? null;
  return {
    activeContributionTotal: factors.reduce(
      (total, factor) => total + Math.max(factor.contribution, 0),
      0,
    ),
    commandText: panel.nextStep,
    contextBadge: panel.enrichmentPrompt,
    contextBadgeTooltip: panel.enrichmentPrompt
      ? buildContextMissingExplainer(impact, panel)
      : null,
    evidenceNodes: buildEvidenceNodes(panel, impact),
    factors,
    headline: panel.riskSummary,
    focusDimensionTooltip: buildFocusDimensionExplainer(impact, primaryLabel),
    impactConstellationTooltip: buildImpactConstellationExplainer(panel),
    primaryDetail: panel.evidenceCards[0]?.impact ?? null,
    primaryLabel,
    scoreWaterfallTooltip: getScoreWaterfallExplainer(),
    visibleLiftTooltip: buildVisibleLiftExplainer(
      factors.reduce(
        (total, factor) => total + Math.max(factor.contribution, 0),
        0,
      ),
    ),
  };
}

function buildEvidenceNodes(
  panel: BusinessImpactPanel,
  impact: ActionBusinessImpact,
): PriorityStoryboardEvidenceNode[] {
  if (matchedDimensions(impact).length === 0) return [];
  return panel.evidenceCards.slice(0, 3).map((card, index) => ({
    detail: card.impact,
    id: `${card.dimension}-${index}`,
    title: index === 0 ? "Why it matters" : card.title,
  }));
}

function buildWaterfallFactor(
  factor: ActionScoreFactor,
  muted: boolean,
  laneStartPercent: number,
  laneWidthPercent: number,
): PriorityStoryboardFactor {
  return {
    contribution: factor.contribution,
    key: factor.factor_name,
    label: displayFactorName(factor.factor_name),
    laneStartPercent,
    laneWidthPercent,
    muted,
    tooltip: buildScoreFactorExplainer(factor),
  };
}

function buildWaterfallFactors(
  scoreFactors: ActionScoreFactor[],
): PriorityStoryboardFactor[] {
  const factors = topFactors(scoreFactors);
  const total = positiveContributionTotal(factors);
  let cursor = 0;

  return factors.map((factor) => {
    const muted = factor.contribution <= 0 || total <= 0;
    const width = muted
      ? mutedWidthPercent(factor.contribution)
      : factorWidthPercent(factor.contribution, total);
    const start = muted ? 0 : cursor;
    if (!muted) cursor += width;
    return buildWaterfallFactor(factor, muted, start, width);
  });
}

function displayFactorName(factorName: string): string {
  if (factorName === "score_bounds_adjustment") {
    return "Score bounds adjustment";
  }
  return factorName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function factorWidthPercent(contribution: number, total: number): number {
  if (contribution <= 0 || total <= 0) return 0;
  return (contribution / total) * 100;
}

function matchedDimensions(impact: ActionBusinessImpact) {
  return impact.criticality.dimensions
    .filter((dimension) => dimension.matched)
    .sort(
      (left, right) =>
        right.contribution - left.contribution || right.weight - left.weight,
    );
}

function mutedWidthPercent(contribution: number): number {
  const scaled = Math.abs(contribution) * 2;
  return Math.max(Math.min(scaled, 24), 16);
}

function positiveContributionTotal(scoreFactors: ActionScoreFactor[]): number {
  return scoreFactors.reduce(
    (total, factor) => total + Math.max(factor.contribution, 0),
    0,
  );
}

function topFactors(scoreFactors: ActionScoreFactor[]): ActionScoreFactor[] {
  return [...scoreFactors]
    .sort((left, right) => {
      if (right.contribution !== left.contribution) {
        return right.contribution - left.contribution;
      }
      return right.weight - left.weight;
    })
    .slice(0, 4);
}
