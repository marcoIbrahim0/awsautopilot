import type { ControlFamily } from '@/lib/api';

export const CONTROL_FAMILY_TOOLTIP =
  'AWS reported one rule, remediation is performed at the shared family level because the fix path is the same.';

function normalizeSourceControls(
  controlFamily?: ControlFamily | null,
  fallbackControlId?: string | null,
): string[] {
  const values = controlFamily?.source_control_ids?.filter(Boolean) ?? [];
  if (values.length > 0) return values;
  return fallbackControlId ? [fallbackControlId] : [];
}

export function getFindingControlLabel(
  controlFamily?: ControlFamily | null,
  fallbackControlId?: string | null,
): string | null {
  return normalizeSourceControls(controlFamily, fallbackControlId)[0] ?? fallbackControlId ?? null;
}

export function getFindingControlSecondaryLabel(
  controlFamily?: ControlFamily | null,
  fallbackControlId?: string | null,
): string | null {
  const primary = getFindingControlLabel(controlFamily, fallbackControlId);
  const canonical = controlFamily?.canonical_control_id ?? null;
  if (!controlFamily?.is_mapped || !canonical || canonical === primary) return null;
  return `Remediation family: ${canonical}`;
}

export function getActionControlSummary(
  controlFamily?: ControlFamily | null,
  fallbackControlId?: string | null,
): string | null {
  const sources = normalizeSourceControls(controlFamily, fallbackControlId);
  const canonical = controlFamily?.canonical_control_id ?? fallbackControlId ?? null;
  if (!canonical) return sources[0] ?? null;
  if (!controlFamily?.is_mapped) return canonical;
  if (sources.length <= 1) return `${sources[0] ?? canonical} -> ${canonical}`;
  return `${sources[0]} +${sources.length - 1} -> ${canonical}`;
}

export function getReportedRulesLabel(
  controlFamily?: ControlFamily | null,
  fallbackControlId?: string | null,
): string | null {
  const sources = normalizeSourceControls(controlFamily, fallbackControlId);
  if (sources.length === 0) return fallbackControlId ?? null;
  return sources.join(', ');
}
