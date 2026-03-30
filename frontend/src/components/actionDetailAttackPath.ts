import type {
  ActionAttackPathView,
  ActionDetail,
  ActionGraphContext,
} from "@/lib/api";

export interface AttackPathSummaryContext {
  entryLabel: string;
  targetLabel: string;
  targetDetail: string | null;
  scopeLabel: string;
  cautionLabel: string | null;
  cautionDetail: string | null;
  nextStepLabel: string | null;
  impactLabel: string | null;
}

type AttackPathActionContext = Pick<
  ActionDetail,
  "account_id" | "region" | "resource_id" | "resource_type" | "target_id"
>;

export function buildAttackPathSummaryContext(
  action: AttackPathActionContext,
  view: ActionAttackPathView,
  graph?: ActionGraphContext | null,
): AttackPathSummaryContext {
  return {
    entryLabel: firstText(view.entry_points[0]?.label, "Local risk context"),
    targetLabel: firstText(
      action.resource_id,
      view.target_assets[0]?.label,
      action.target_id,
      "Target asset unresolved",
    ),
    targetDetail: firstText(
      action.resource_type,
      view.target_assets[0]?.detail,
      null,
    ),
    scopeLabel: action.region
      ? `${action.account_id} · ${action.region}`
      : `${action.account_id} · global`,
    cautionLabel: cautionLabel(view, graph),
    cautionDetail: cautionDetail(view, graph),
    nextStepLabel: cleanedRecommendation(view.recommendation_summary),
    impactLabel: normalizeText(view.business_impact_summary),
  };
}

function cautionLabel(
  view: ActionAttackPathView,
  graph?: ActionGraphContext | null,
): string | null {
  if (
    view.status === "partial" &&
    view.availability_reason === "bounded_context_truncated"
  ) {
    return "Take care";
  }
  if (
    view.status === "partial" &&
    view.availability_reason === "entry_point_unresolved"
  ) {
    return "Take care";
  }
  if (
    view.status === "partial" &&
    view.availability_reason === "target_assets_unresolved"
  ) {
    return "Take care";
  }
  if (graph?.self_resolved) {
    return "Autopilot note";
  }
  if (view.status === "context_incomplete") {
    return "Take care";
  }
  return null;
}

function cautionDetail(
  view: ActionAttackPathView,
  graph?: ActionGraphContext | null,
): string | null {
  if (
    view.status === "partial" &&
    view.availability_reason === "bounded_context_truncated"
  ) {
    return "Extra graph context was capped to keep this view bounded.";
  }
  if (
    view.status === "partial" &&
    view.availability_reason === "entry_point_unresolved"
  ) {
    return "The entry point is not fully resolved yet.";
  }
  if (
    view.status === "partial" &&
    view.availability_reason === "target_assets_unresolved"
  ) {
    return "The final target asset still needs verification.";
  }
  if (graph?.self_resolved) {
    return "Provider metadata was missing, so this path was reconstructed from persisted action fields.";
  }
  if (view.status === "context_incomplete") {
    return "Relationship context is incomplete, so treat this as directly observed evidence only.";
  }
  return null;
}

function cleanedRecommendation(
  summary: string | null | undefined,
): string | null {
  const text = normalizeText(summary);
  if (!text) return null;
  return text.replace(/^Safest next step:\s*/i, "").trim();
}

function firstText(...values: Array<string | null | undefined>): string {
  for (const value of values) {
    const text = normalizeText(value);
    if (text) return text;
  }
  return "";
}

function normalizeText(value: string | null | undefined): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}
