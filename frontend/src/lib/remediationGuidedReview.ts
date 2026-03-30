import type { RemediationPreview } from '@/lib/api';
import type { RemediationOutcomePresentation } from '@/lib/remediationOutcome';
import {
  getRemediationSettingsLink,
  type RemediationSettingsLink,
} from '@/lib/remediationSettingsLinks';

type Resolution = NonNullable<RemediationPreview['resolution']>;

type GuidedReviewTone = 'default' | 'info' | 'warning';

export interface GuidedReviewPrompt {
  detail: string;
  id: string;
  label: string;
  settingsLink?: RemediationSettingsLink | null;
  tone: GuidedReviewTone;
}

export interface GuidedReviewPreservationEntry {
  key: string;
  label: string;
  value: string;
}

export interface GuidedReviewPreservationGroup {
  entries: GuidedReviewPreservationEntry[];
  id: string;
  title: string;
}

export interface GuidedReviewContent {
  nextSteps: GuidedReviewPrompt[];
  preservationGroups: GuidedReviewPreservationGroup[];
  reviewChecklist: GuidedReviewPrompt[];
  whyThisPath: string;
}

const PRESERVATION_GROUPS: Array<{ id: string; title: string }> = [
  { id: 'policy', title: 'Policy and merge behavior' },
  { id: 'destination', title: 'Destination and target resources' },
  { id: 'customer', title: 'Customer defaults and required inputs' },
  { id: 'other', title: 'Other preserved context' },
];

const POLICY_TOKENS = ['merge', 'policy', 'statement'];
const DESTINATION_TOKENS = ['bucket', 'distribution', 'dns', 'domain', 'origin', 'target', 'trail'];
const CUSTOMER_TOKENS = ['bastion', 'cidr', 'default', 'group', 'input', 'kms'];

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function summarizePreservationValue(value: unknown): string | null {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (isNonEmptyString(value)) return value.trim();
  if (Array.isArray(value)) return summarizeArrayValue(value);
  if (value && typeof value === 'object') return summarizeObjectValue(value as Record<string, unknown>);
  return null;
}

function summarizeArrayValue(value: unknown[]): string | null {
  const items = value
    .map((item) => (isNonEmptyString(item) ? item.trim() : String(item ?? '').trim()))
    .filter((item) => item.length > 0);
  return items.length > 0 ? items.join(', ') : null;
}

function summarizeObjectValue(value: Record<string, unknown>): string | null {
  const entries = Object.entries(value)
    .map(([key, nestedValue]) => {
      const summary = summarizePreservationValue(nestedValue);
      return summary ? `${key}: ${summary}` : null;
    })
    .filter((entry): entry is string => Boolean(entry));
  return entries.length > 0 ? entries.join(' · ') : null;
}

function formatPreservationKey(key: string): string {
  return key.replace(/_/g, ' ');
}

function includesToken(key: string, tokens: string[]): boolean {
  return tokens.some((token) => key.includes(token));
}

function getPreservationGroupId(key: string): string {
  const normalizedKey = key.toLowerCase();
  if (includesToken(normalizedKey, POLICY_TOKENS)) return 'policy';
  if (includesToken(normalizedKey, DESTINATION_TOKENS)) return 'destination';
  if (includesToken(normalizedKey, CUSTOMER_TOKENS)) return 'customer';
  return 'other';
}

function buildPreservationEntries(summary: Resolution['preservation_summary']): GuidedReviewPreservationEntry[] {
  if (!summary || typeof summary !== 'object' || Array.isArray(summary)) return [];
  return Object.entries(summary)
    .map(([key, value]) => {
      const summarizedValue = summarizePreservationValue(value);
      if (!summarizedValue) return null;
      return { key, label: formatPreservationKey(key), value: summarizedValue };
    })
    .filter((entry): entry is GuidedReviewPreservationEntry => Boolean(entry));
}

function buildPreservationGroups(
  entries: GuidedReviewPreservationEntry[]
): GuidedReviewPreservationGroup[] {
  return PRESERVATION_GROUPS.map((group) => ({
    ...group,
    entries: entries.filter((entry) => getPreservationGroupId(entry.key) === group.id),
  })).filter((group) => group.entries.length > 0);
}

function addPrompt(
  prompts: Map<string, GuidedReviewPrompt>,
  label: string,
  detail: string,
  tone: GuidedReviewTone,
  settingsLink?: RemediationSettingsLink | null
): void {
  if (!label.trim()) return;
  if (prompts.has(label)) return;
  prompts.set(label, {
    detail,
    id: label.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
    label,
    settingsLink: settingsLink || null,
    tone,
  });
}

function buildReviewChecklist(
  supportTier: string | undefined,
  preservationEntries: GuidedReviewPreservationEntry[],
  blockedReasons: string[],
  missingDefaults: string[]
): GuidedReviewPrompt[] {
  if (supportTier !== 'review_required_bundle') return [];
  const prompts = new Map<string, GuidedReviewPrompt>();
  preservationEntries.forEach((entry) => addPrompt(prompts, `Verify preserved ${entry.label}`, entry.value, 'default'));
  blockedReasons.forEach((reason) => addPrompt(prompts, `Confirm this review condition: ${reason}`, reason, 'warning'));
  missingDefaults.forEach((item) => {
    addPrompt(
      prompts,
      `Provide or confirm ${item} before apply`,
      'This input is still required for the selected remediation path.',
      'warning',
      getRemediationSettingsLink(item),
    );
  });
  return [...prompts.values()];
}

function buildNextSteps(
  outcome: RemediationOutcomePresentation | null,
  preservationEntries: GuidedReviewPreservationEntry[],
  blockedReasons: string[],
  missingDefaults: string[]
): GuidedReviewPrompt[] {
  const prompts = new Map<string, GuidedReviewPrompt>();
  blockedReasons.forEach((reason) => addPrompt(prompts, `Confirm this review condition: ${reason}`, reason, 'warning'));
  missingDefaults.forEach((item) => {
    addPrompt(
      prompts,
      `Provide or confirm ${item} before apply`,
      'This input is still required for the selected remediation path.',
      'warning',
      getRemediationSettingsLink(item),
    );
  });
  if (prompts.size === 0) {
    preservationEntries.slice(0, 2).forEach((entry) => {
      addPrompt(prompts, `Verify preserved ${entry.label}`, entry.value, 'default');
    });
  }
  if (prompts.size === 0 && outcome) {
    addPrompt(prompts, outcome.label, outcome.description, outcome.tone === 'warning' ? 'warning' : 'info');
  }
  return [...prompts.values()];
}

function normalizeStringArray(value: Resolution['blocked_reasons'] | Resolution['missing_defaults']): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isNonEmptyString).map((item) => item.trim());
}

export function buildGuidedReviewContent(
  resolution: Resolution | null | undefined,
  outcome: RemediationOutcomePresentation | null
): GuidedReviewContent {
  const preservationEntries = buildPreservationEntries(resolution?.preservation_summary);
  const blockedReasons = normalizeStringArray(resolution?.blocked_reasons);
  const missingDefaults = normalizeStringArray(resolution?.missing_defaults);
  return {
    nextSteps: buildNextSteps(outcome, preservationEntries, blockedReasons, missingDefaults),
    preservationGroups: buildPreservationGroups(preservationEntries),
    reviewChecklist: buildReviewChecklist(resolution?.support_tier, preservationEntries, blockedReasons, missingDefaults),
    whyThisPath: resolution?.decision_rationale?.trim() || outcome?.description || 'Review the generated guidance before taking the next remediation step.',
  };
}
