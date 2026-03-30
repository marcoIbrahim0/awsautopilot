export type HelpTab = 'help-center' | 'assistant' | 'cases' | 'files';

export const HELP_TABS: Array<{ value: HelpTab; label: string }> = [
  { value: 'help-center', label: 'Help Center' },
  { value: 'assistant', label: 'Ask AI' },
  { value: 'cases', label: 'My Cases' },
  { value: 'files', label: 'Shared Files' },
];

export const HELP_CASE_CATEGORIES: Array<{ value: string; label: string }> = [
  { value: 'onboarding', label: 'Onboarding' },
  { value: 'aws_connection', label: 'AWS Connection' },
  { value: 'findings_actions', label: 'Findings & Actions' },
  { value: 'exceptions', label: 'Exceptions' },
  { value: 'remediation_pr_bundles', label: 'PR Bundles' },
  { value: 'notifications_integrations', label: 'Notifications & Integrations' },
  { value: 'shared_files', label: 'Shared Files' },
  { value: 'other', label: 'Other' },
];

export function normalizeHelpTab(value: string | null | undefined): HelpTab {
  return HELP_TABS.some((tab) => tab.value === value) ? (value as HelpTab) : 'help-center';
}

export function buildHelpHref(params: {
  tab?: HelpTab;
  from?: string | null;
  accountId?: string | null;
  actionId?: string | null;
  findingId?: string | null;
  caseId?: string | null;
  threadId?: string | null;
} = {}): string {
  const searchParams = new URLSearchParams();
  if (params.tab) searchParams.set('tab', params.tab);
  if (params.from) searchParams.set('from', params.from);
  if (params.accountId) searchParams.set('account_id', params.accountId);
  if (params.actionId) searchParams.set('action_id', params.actionId);
  if (params.findingId) searchParams.set('finding_id', params.findingId);
  if (params.caseId) searchParams.set('case', params.caseId);
  if (params.threadId) searchParams.set('thread', params.threadId);
  const query = searchParams.toString();
  return query ? `/help?${query}` : '/help';
}
