/**
 * Step 2B.4: Finding source labels and helpers.
 * Sources: security_hub | access_analyzer | inspector
 */
export const SOURCE_SECURITY_HUB = 'security_hub';
export const SOURCE_ACCESS_ANALYZER = 'access_analyzer';
export const SOURCE_INSPECTOR = 'inspector';

const SOURCE_LABELS: Record<string, string> = {
  [SOURCE_SECURITY_HUB]: 'Security Hub',
  [SOURCE_ACCESS_ANALYZER]: 'Access Analyzer',
  [SOURCE_INSPECTOR]: 'Inspector',
};

const SOURCE_SHORT_LABELS: Record<string, string> = {
  [SOURCE_SECURITY_HUB]: 'SH',
  [SOURCE_ACCESS_ANALYZER]: 'AA',
  [SOURCE_INSPECTOR]: 'Insp',
};

/** Display label for source (e.g. "Security Hub"). */
export function getSourceLabel(source: string | undefined | null): string {
  if (!source || !source.trim()) return '';
  const key = source.trim().toLowerCase();
  return SOURCE_LABELS[key] ?? source;
}

/** Short label for badges (e.g. "SH", "AA", "Insp"). */
export function getSourceShortLabel(source: string | undefined | null): string {
  if (!source || !source.trim()) return '';
  const key = source.trim().toLowerCase();
  return SOURCE_SHORT_LABELS[key] ?? source.slice(0, 4);
}

/** All source values for filter tabs. */
export const SOURCE_FILTER_VALUES = [
  { value: '', label: 'All sources' },
  { value: SOURCE_SECURITY_HUB, label: SOURCE_LABELS[SOURCE_SECURITY_HUB] },
  { value: SOURCE_ACCESS_ANALYZER, label: SOURCE_LABELS[SOURCE_ACCESS_ANALYZER] },
  { value: SOURCE_INSPECTOR, label: SOURCE_LABELS[SOURCE_INSPECTOR] },
] as const;
