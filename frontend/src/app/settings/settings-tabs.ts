export type SettingsTab =
  | 'account'
  | 'team'
  | 'organization'
  | 'notifications'
  | 'integrations'
  | 'governance'
  | 'remediation-defaults'
  | 'baseline-report';

export const DEFAULT_SETTINGS_TAB: SettingsTab = 'account';

export const SETTINGS_TAB_ITEMS: Array<{ value: SettingsTab; label: string; panelId: string }> = [
  { value: 'account', label: 'Account', panelId: 'settings-panel-account' },
  { value: 'team', label: 'Team', panelId: 'settings-panel-team' },
  { value: 'organization', label: 'Organization', panelId: 'settings-panel-organization' },
  { value: 'notifications', label: 'Notifications', panelId: 'settings-panel-notifications' },
  { value: 'integrations', label: 'Integrations', panelId: 'settings-panel-integrations' },
  { value: 'governance', label: 'Governance', panelId: 'settings-panel-governance' },
  { value: 'remediation-defaults', label: 'Remediation Defaults', panelId: 'settings-panel-remediation-defaults' },
  { value: 'baseline-report', label: 'Baseline Report', panelId: 'settings-panel-baseline-report' },
];

const SETTINGS_TAB_ALIASES: Record<string, SettingsTab> = {
  profile: 'account',
};

const LEGACY_EXPORTS_SETTINGS_TABS = new Set([
  'exports-compliance',
  'evidence-export',
  'control-mappings',
]);

export function isSettingsTab(value: string | null | undefined): value is SettingsTab {
  return SETTINGS_TAB_ITEMS.some((tab) => tab.value === value);
}

export function normalizeSettingsTab(value: string | null | undefined): SettingsTab {
  if (!value) return DEFAULT_SETTINGS_TAB;
  if (isSettingsTab(value)) return value;
  return SETTINGS_TAB_ALIASES[value] ?? DEFAULT_SETTINGS_TAB;
}

export function buildSettingsTabHref(tab: SettingsTab): string {
  return `/settings?tab=${tab}`;
}

export function isLegacyExportsSettingsTab(value: string | null | undefined): boolean {
  return typeof value === 'string' && LEGACY_EXPORTS_SETTINGS_TABS.has(value);
}
