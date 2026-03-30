import type { ActionBusinessImpact, ActionCriticalityDimension } from '@/lib/api';

type DimensionCopy = {
  title: string;
  effect: string;
};

export interface BusinessImpactEvidenceCard {
  dimension: string;
  impact: string;
  title: string;
}

export interface BusinessImpactPanel {
  evidenceCards: BusinessImpactEvidenceCard[];
  riskSummary: string;
  enrichmentPrompt: string | null;
  nextStep: string;
}

const DIMENSION_COPY: Record<string, DimensionCopy> = {
  customer_facing: {
    title: 'Customer-facing service',
    effect: 'Outages or abuse in this service will be immediately visible to your customers.',
  },
  identity_boundary: {
    title: 'Shared access boundary',
    effect: 'This control affects IAM trust boundaries — a compromise could impact multiple identities.',
  },
  production_environment: {
    title: 'Production environment',
    effect: 'This asset is tied to production; misconfigurations here carry high operational risk.',
  },
  regulated_data: {
    title: 'Sensitive or regulated data',
    effect: 'This resource is connected to regulated or sensitive data classes (PII, Financial, etc.).',
  },
  revenue_path: {
    title: 'Revenue flow',
    effect: 'This asset participates in checkout, billing, or subscription workflows.',
  },
};

const ACTION_TYPE_GUIDANCE: Record<string, string> = {
  s3_block_public_access: 'Verify whether any S3 buckets in this account serve intentionally public content before enabling account-level block.',
  ssm_block_public_sharing: 'Identify all SSM documents currently shared publicly to ensure no production automation depends on external access.',
  ebs_snapshot_block_public_access: 'Check for AMI or infrastructure backups that are shared across accounts before blocking public snapshot access.',
  ebs_default_encryption: 'Confirm that all existing deployment scripts and CMK policies in this region support KMS encryption as the new default.',
  enable_guardduty: 'Enable GuardDuty to establish a baseline for threat detection; review the active region list for optimal coverage.',
  enable_security_hub: 'Consolidate security findings by enabling Security Hub across all active regions to gain account-wide visibility.',
  iam_root_access_key_absent: 'Immediately audit break-glass workflows and rotations before deleting active root access keys.',
};

export function buildBusinessImpactPanel(
  impact: ActionBusinessImpact,
  actionType?: string
): BusinessImpactPanel {
  const matched = matchedDimensions(impact);
  const isUnknown = impact.criticality.status === 'unknown';

  return {
    evidenceCards: matched.slice(0, 3).map(buildEvidenceCard),
    riskSummary: riskSummaryText(impact, matched),
    enrichmentPrompt: isUnknown ? enrichmentPromptText() : null,
    nextStep: nextStepText(actionType, matched),
  };
}

function matchedDimensions(impact: ActionBusinessImpact): ActionCriticalityDimension[] {
  return impact.criticality.dimensions
    .filter((dimension) => dimension.matched)
    .sort((left, right) => right.contribution - left.contribution || right.weight - left.weight);
}

function buildEvidenceCard(dimension: ActionCriticalityDimension): BusinessImpactEvidenceCard {
  const copy = dimensionCopy(dimension.dimension);
  return {
    dimension: dimension.dimension,
    impact: copy.effect,
    title: copy.title,
  };
}

function riskSummaryText(
  impact: ActionBusinessImpact,
  matched: ActionCriticalityDimension[]
): string {
  if (matched.length === 0) {
    return `Business context is unverified — priority is driven by the technical risk score (${impact.technical_risk_score}/100).`;
  }

  const primary = dimensionCopy(matched[0].dimension).title;
  const risk = impact.technical_risk_tier.toLowerCase();
  
  if (matched.length === 1) {
    return `This is a ${risk}-risk issue affecting your ${primary.toLowerCase()}.`;
  }
  
  const secondary = matched.slice(1, 3).map((item) => dimensionCopy(item.dimension).title.toLowerCase());
  return `This ${risk}-risk issue affects your ${primary.toLowerCase()} and ${joinList(secondary)}.`;
}

function enrichmentPromptText(): string {
  return 'Tag this account with environment, data classification, and service ownership to auto-enrich future finding criticality.';
}

function nextStepText(actionType?: string, matched: ActionCriticalityDimension[] = []): string {
  if (actionType && ACTION_TYPE_GUIDANCE[actionType]) {
    return ACTION_TYPE_GUIDANCE[actionType];
  }

  if (matched.some(m => m.dimension === 'identity_boundary')) {
    return 'Confirm whether this account, role, or policy is shared across production or high-trust workflows.';
  }

  if (matched.some(m => m.dimension === 'production_environment')) {
    return 'Validate the impact of this change on production availability before executing the remediation.';
  }

  return 'Confirm the owning team and business dependency before changing the action priority.';
}

function dimensionCopy(dimension: string): DimensionCopy {
  return DIMENSION_COPY[dimension] || { 
    title: 'Business context signal', 
    effect: 'This issue may have meaningful business impact based on matched keywords or resource context.' 
  };
}

function joinList(items: string[]): string {
  if (items.length <= 1) return items[0] || '';
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(', ')}, and ${items[items.length - 1]}`;
}

function humanizeToken(value: string): string {
  return value
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

