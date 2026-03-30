'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { remediationInsetClass } from '@/components/ui/remediation-surface';
import { useAuth } from '@/contexts/AuthContext';
import {
  getErrorMessage,
  listIntegrationSettings,
  patchIntegrationSettings,
  runJiraCanarySync,
  syncJiraIntegrationWebhook,
  type IntegrationProvider,
  type IntegrationSettingsItemResponse,
  type JiraUtilityResponse,
  validateJiraIntegrationSettings,
} from '@/lib/api';
import { SettingsCard, SettingsNotice, SettingsSectionIntro, TextAreaField } from './settings-ui';

type ProviderFormState = {
  enabled: boolean;
  outbound_enabled: boolean;
  inbound_enabled: boolean;
  auto_create: boolean;
  reopen_on_regression: boolean;
  base_url: string;
  project_key: string;
  issue_type: string;
  transition_map: string;
  assignee_account_map: string;
  canary_action_id: string;
  table: string;
  channel_id: string;
  api_base_url: string;
  user_email: string;
  api_token: string;
  username: string;
  password: string;
  bot_token: string;
  webhook_token: string;
};

type ProviderState = {
  saving: boolean;
  clearing: boolean;
  validating: boolean;
  syncingWebhook: boolean;
  rotatingSecret: boolean;
  runningCanary: boolean;
  error: string | null;
  success: string | null;
};

type SecretField = 'user_email' | 'api_token' | 'username' | 'password' | 'bot_token' | 'webhook_token';

const PROVIDERS: IntegrationProvider[] = ['jira', 'servicenow', 'slack'];

const PROVIDER_LABELS: Record<IntegrationProvider, string> = {
  jira: 'Jira',
  servicenow: 'ServiceNow',
  slack: 'Slack',
};

function defaultItem(provider: IntegrationProvider): IntegrationSettingsItemResponse {
  return {
    provider,
    enabled: false,
    outbound_enabled: false,
    inbound_enabled: false,
    auto_create: false,
    reopen_on_regression: false,
    config: {},
    secret_configured: false,
    webhook_configured: false,
  };
}

function defaultProviderState(): ProviderState {
  return {
    saving: false,
    clearing: false,
    validating: false,
    syncingWebhook: false,
    rotatingSecret: false,
    runningCanary: false,
    error: null,
    success: null,
  };
}

function buildDefaultState<T>(factory: () => T): Record<IntegrationProvider, T> {
  return {
    jira: factory(),
    servicenow: factory(),
    slack: factory(),
  };
}

function normalizeItem(item: IntegrationSettingsItemResponse | undefined, provider: IntegrationProvider): IntegrationSettingsItemResponse {
  return item ?? defaultItem(provider);
}

function buildFormState(item: IntegrationSettingsItemResponse): ProviderFormState {
  const config = item.config ?? {};
  const transitionMap = config.transition_map;
  const assigneeAccountMap = config.assignee_account_map;
  const transitionMapText =
    transitionMap && typeof transitionMap === 'object'
      ? JSON.stringify(transitionMap, null, 2)
      : '';
  const assigneeAccountMapText =
    assigneeAccountMap && typeof assigneeAccountMap === 'object'
      ? JSON.stringify(assigneeAccountMap, null, 2)
      : '';

  return {
    enabled: item.enabled,
    outbound_enabled: item.outbound_enabled,
    inbound_enabled: item.inbound_enabled,
    auto_create: item.auto_create,
    reopen_on_regression: item.reopen_on_regression,
    base_url: typeof config.base_url === 'string' ? config.base_url : '',
    project_key: typeof config.project_key === 'string' ? config.project_key : '',
    issue_type: typeof config.issue_type === 'string' ? config.issue_type : '',
    transition_map: transitionMapText,
    assignee_account_map: assigneeAccountMapText,
    canary_action_id: typeof config.canary_action_id === 'string' ? config.canary_action_id : '',
    table: typeof config.table === 'string' ? config.table : '',
    channel_id: typeof config.channel_id === 'string' ? config.channel_id : '',
    api_base_url: typeof config.api_base_url === 'string' ? config.api_base_url : '',
    user_email: '',
    api_token: '',
    username: '',
    password: '',
    bot_token: '',
    webhook_token: '',
  };
}

function parseStringMap(source: string, label: string): Record<string, string> {
  const parsed = JSON.parse(source) as unknown;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return Object.fromEntries(
    Object.entries(parsed).map(([key, value]) => {
      if (typeof value !== 'string') {
        throw new Error(`${label} values must be strings.`);
      }
      return [key, value];
    }),
  );
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) return 'Not yet recorded';
  return new Date(value).toLocaleString();
}

function healthBadgeVariant(
  status: string | null | undefined,
): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'healthy') return 'success';
  if (status === 'warning') return 'warning';
  if (status === 'error') return 'danger';
  if (status === 'validating') return 'info';
  return 'default';
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function jiraClientValidation(form: ProviderFormState): {
  errors: string[];
  warnings: string[];
} {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (form.base_url.trim() && !form.base_url.trim().startsWith('https://')) {
    errors.push('Jira base URL must start with https://.');
  }
  if (form.base_url.trim().endsWith('/')) {
    warnings.push('Jira base URL will be normalized without the trailing slash.');
  }
  if (form.transition_map.trim()) {
    try {
      parseStringMap(form.transition_map.trim(), 'Transition map');
    } catch (error) {
      errors.push(getErrorMessage(error));
    }
  }
  if (form.assignee_account_map.trim()) {
    try {
      parseStringMap(form.assignee_account_map.trim(), 'Assignee account map');
    } catch (error) {
      errors.push(getErrorMessage(error));
    }
  }
  if (form.canary_action_id.trim() && !UUID_PATTERN.test(form.canary_action_id.trim())) {
    errors.push('Canary action ID must be a valid UUID.');
  }
  return { errors, warnings };
}

function HealthField({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className={remediationInsetClass('default', 'space-y-1 px-3 py-3')}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted/72">{label}</p>
      <p className="text-sm font-medium text-text">{value}</p>
    </div>
  );
}

function secretFieldsForProvider(provider: IntegrationProvider): SecretField[] {
  if (provider === 'jira') return ['user_email', 'api_token', 'webhook_token'];
  if (provider === 'servicenow') return ['username', 'password', 'webhook_token'];
  return ['bot_token', 'webhook_token'];
}

function requiredSecretFieldsForProvider(provider: IntegrationProvider): SecretField[] {
  if (provider === 'jira') return ['user_email', 'api_token'];
  if (provider === 'servicenow') return ['username', 'password'];
  return ['bot_token'];
}

export function IntegrationsSettingsTab() {
  const { user, isAuthenticated } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [items, setItems] = useState<Record<IntegrationProvider, IntegrationSettingsItemResponse>>({
    jira: defaultItem('jira'),
    servicenow: defaultItem('servicenow'),
    slack: defaultItem('slack'),
  });
  const [forms, setForms] = useState<Record<IntegrationProvider, ProviderFormState>>({
    jira: buildFormState(defaultItem('jira')),
    servicenow: buildFormState(defaultItem('servicenow')),
    slack: buildFormState(defaultItem('slack')),
  });
  const [providerState, setProviderState] = useState<Record<IntegrationProvider, ProviderState>>(
    buildDefaultState(defaultProviderState),
  );
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setLoadError(null);

    try {
      const response = await listIntegrationSettings();
      const fetched = response.items.reduce<Partial<Record<IntegrationProvider, IntegrationSettingsItemResponse>>>((acc, item) => {
        acc[item.provider] = item;
        return acc;
      }, {});
      const nextItems = {
        jira: normalizeItem(fetched.jira, 'jira'),
        servicenow: normalizeItem(fetched.servicenow, 'servicenow'),
        slack: normalizeItem(fetched.slack, 'slack'),
      };
      setItems(nextItems);
      setForms({
        jira: buildFormState(nextItems.jira),
        servicenow: buildFormState(nextItems.servicenow),
        slack: buildFormState(nextItems.slack),
      });
    } catch (err) {
      setLoadError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  const cards = useMemo(
    () =>
      PROVIDERS.map((provider) => ({
        provider,
        item: items[provider],
        form: forms[provider],
        state: providerState[provider],
        jiraValidation: provider === 'jira' ? jiraClientValidation(forms[provider]) : null,
      })),
    [forms, items, providerState],
  );

  function updateForm(
    provider: IntegrationProvider,
    patch: Partial<ProviderFormState>,
  ) {
    setForms((current) => ({
      ...current,
      [provider]: {
        ...current[provider],
        ...patch,
      },
    }));
  }

  function setProviderStatePatch(provider: IntegrationProvider, patch: Partial<ProviderState>) {
    setProviderState((current) => ({
      ...current,
      [provider]: {
        ...current[provider],
        ...patch,
      },
    }));
  }

  function applyJiraUtilityResponse(response: JiraUtilityResponse) {
    setItems((current) => ({ ...current, jira: response.item }));
    setForms((current) => ({ ...current, jira: buildFormState(response.item) }));
  }

  async function handleSave(provider: IntegrationProvider) {
    const item = items[provider];
    const form = forms[provider];
    setProviderStatePatch(provider, { saving: true, error: null, success: null });

    try {
      const nextConfig: Record<string, unknown> = { ...item.config };

      if (provider === 'jira') {
        if (form.base_url.trim()) {
          nextConfig.base_url = form.base_url.trim();
        } else {
          delete nextConfig.base_url;
        }
        if (form.project_key.trim()) {
          nextConfig.project_key = form.project_key.trim();
        } else {
          delete nextConfig.project_key;
        }
        if (form.issue_type.trim()) {
          nextConfig.issue_type = form.issue_type.trim();
        } else {
          delete nextConfig.issue_type;
        }
        if (form.transition_map.trim()) {
          nextConfig.transition_map = parseStringMap(form.transition_map.trim(), 'Transition map');
        } else {
          delete nextConfig.transition_map;
        }
        if (form.assignee_account_map.trim()) {
          nextConfig.assignee_account_map = parseStringMap(form.assignee_account_map.trim(), 'Assignee account map');
        } else {
          delete nextConfig.assignee_account_map;
        }
        if (form.canary_action_id.trim()) {
          if (!UUID_PATTERN.test(form.canary_action_id.trim())) {
            throw new Error('Canary action ID must be a valid UUID.');
          }
          nextConfig.canary_action_id = form.canary_action_id.trim();
        } else {
          delete nextConfig.canary_action_id;
        }
      } else if (provider === 'servicenow') {
        if (form.base_url.trim()) {
          nextConfig.base_url = form.base_url.trim();
        } else {
          delete nextConfig.base_url;
        }
        if (form.table.trim()) {
          nextConfig.table = form.table.trim();
        } else {
          delete nextConfig.table;
        }
      } else {
        if (form.channel_id.trim()) {
          nextConfig.channel_id = form.channel_id.trim();
        } else {
          delete nextConfig.channel_id;
        }
        if (form.api_base_url.trim()) {
          nextConfig.api_base_url = form.api_base_url.trim();
        } else {
          delete nextConfig.api_base_url;
        }
      }

      const enteredSecretFields = secretFieldsForProvider(provider).filter((field) => form[field].trim().length > 0);
      let secretConfig: Record<string, string> | undefined;

      if (enteredSecretFields.length > 0) {
        const requiredFields = requiredSecretFieldsForProvider(provider);
        const missingRequired = requiredFields.filter((field) => !form[field].trim());
        if (missingRequired.length > 0) {
          throw new Error(`Enter all required secret fields before replacing ${PROVIDER_LABELS[provider]} credentials.`);
        }
        if (provider !== 'jira' && item.webhook_configured && !form.webhook_token.trim()) {
          throw new Error('Webhook token must be re-entered when replacing a provider secret set that already has inbound auth configured.');
        }

        secretConfig = {};
        secretFieldsForProvider(provider).forEach((field) => {
          const value = form[field].trim();
          if (value) {
            secretConfig![field] = value;
          }
        });
      }

      const updated = await patchIntegrationSettings(provider, {
        enabled: form.enabled,
        outbound_enabled: form.outbound_enabled,
        inbound_enabled: form.inbound_enabled,
        auto_create: form.auto_create,
        reopen_on_regression: form.reopen_on_regression,
        config: nextConfig,
        ...(secretConfig ? { secret_config: secretConfig } : {}),
      });

      setItems((current) => ({ ...current, [provider]: updated }));
      setForms((current) => ({ ...current, [provider]: buildFormState(updated) }));
      setProviderStatePatch(provider, { success: `${PROVIDER_LABELS[provider]} settings saved.` });
    } catch (err) {
      setProviderStatePatch(provider, { error: getErrorMessage(err) });
    } finally {
      setProviderStatePatch(provider, { saving: false });
    }
  }

  async function handleValidateJira() {
    setProviderStatePatch('jira', { validating: true, error: null, success: null });
    try {
      const response = await validateJiraIntegrationSettings();
      applyJiraUtilityResponse(response);
      setProviderStatePatch('jira', { success: response.message });
    } catch (err) {
      setProviderStatePatch('jira', { error: getErrorMessage(err) });
    } finally {
      setProviderStatePatch('jira', { validating: false });
    }
  }

  async function handleSyncJiraWebhook(rotateSecret = false) {
    setProviderStatePatch('jira', {
      syncingWebhook: !rotateSecret,
      rotatingSecret: rotateSecret,
      error: null,
      success: null,
    });
    try {
      const response = await syncJiraIntegrationWebhook(rotateSecret ? { rotate_secret: true } : {});
      applyJiraUtilityResponse(response);
      setProviderStatePatch('jira', { success: response.message });
    } catch (err) {
      setProviderStatePatch('jira', { error: getErrorMessage(err) });
    } finally {
      setProviderStatePatch('jira', { syncingWebhook: false, rotatingSecret: false });
    }
  }

  async function handleRunJiraCanary(form: ProviderFormState) {
    setProviderStatePatch('jira', { runningCanary: true, error: null, success: null });
    try {
      const body = form.canary_action_id.trim() ? { action_id: form.canary_action_id.trim() } : {};
      const response = await runJiraCanarySync(body);
      applyJiraUtilityResponse(response);
      setProviderStatePatch('jira', {
        success:
          response.task_ids.length > 0
            ? `${response.message} ${response.task_ids.length} task queued.`
            : response.message,
      });
    } catch (err) {
      setProviderStatePatch('jira', { error: getErrorMessage(err) });
    } finally {
      setProviderStatePatch('jira', { runningCanary: false });
    }
  }

  async function handleClearSecrets(provider: IntegrationProvider) {
    setProviderStatePatch(provider, { clearing: true, error: null, success: null });
    try {
      const updated = await patchIntegrationSettings(provider, { clear_secret_config: true });
      setItems((current) => ({ ...current, [provider]: updated }));
      setForms((current) => ({ ...current, [provider]: buildFormState(updated) }));
      setProviderStatePatch(provider, { success: `${PROVIDER_LABELS[provider]} secrets cleared.` });
    } catch (err) {
      setProviderStatePatch(provider, { error: getErrorMessage(err) });
    } finally {
      setProviderStatePatch(provider, { clearing: false });
    }
  }

  return (
    <div id="settings-panel-integrations" role="tabpanel" tabIndex={0} className="space-y-6">
      <SettingsSectionIntro
        title="Integrations"
        description="Configure tenant-scoped Jira, ServiceNow, and Slack sync settings. Stored credentials are write-only and never re-displayed."
        titleExplainer={{ conceptId: 'settings_integrations', context: 'settings' }}
        action={isAdmin ? undefined : <Badge variant="info">Members are read-only</Badge>}
      />

      <SettingsNotice tone="info">
        Any value entered in a secret field replaces the stored secret set for that provider. Leave secret inputs blank
        to keep the currently stored credentials unchanged.
      </SettingsNotice>

      {loadError ? <SettingsNotice tone="danger">{loadError}</SettingsNotice> : null}

      {isLoading ? (
        <SettingsCard>
          <p className="animate-pulse text-muted">Loading integration settings...</p>
        </SettingsCard>
      ) : (
        <div className="space-y-6">
          {cards.map(({ provider, item, form, state, jiraValidation }) => (
            <SettingsCard key={provider} className="space-y-6">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-text">{PROVIDER_LABELS[provider]}</h3>
                    <Badge variant={item.enabled ? 'success' : 'default'}>{item.enabled ? 'Enabled' : 'Disabled'}</Badge>
                    <Badge variant={item.secret_configured ? 'success' : 'default'}>
                      {item.secret_configured ? 'Secrets configured' : 'Secrets missing'}
                    </Badge>
                    <Badge variant={item.webhook_configured ? 'success' : 'default'}>
                      {item.webhook_configured ? 'Webhook auth configured' : 'Webhook auth missing'}
                    </Badge>
                    {provider === 'jira' ? (
                      <Badge variant={healthBadgeVariant(item.health?.status)}>
                        {item.health?.status ? `Health: ${item.health.status}` : 'Health unknown'}
                      </Badge>
                    ) : null}
                    {provider === 'jira' && item.health?.signed_webhook_enabled ? (
                      <Badge variant="info">Signed webhook</Badge>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm text-muted">
                    {provider === 'jira'
                      ? 'Sync actions into Jira issues with optional transition mappings.'
                      : provider === 'servicenow'
                        ? 'Sync actions into ServiceNow records and preserve tenant-scoped provider auth.'
                        : 'Sync actions into Slack with a bot token and tenant-scoped channel target.'}
                  </p>
                </div>

                {isAdmin ? (
                  <div className="flex flex-wrap gap-2">
                    {provider === 'jira' ? (
                      <>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleValidateJira()}
                          isLoading={state.validating}
                        >
                          Validate connection
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleSyncJiraWebhook(false)}
                          isLoading={state.syncingWebhook}
                        >
                          Register/repair webhook
                        </Button>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void handleRunJiraCanary(form)}
                          isLoading={state.runningCanary}
                        >
                          Run canary sync
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void handleSyncJiraWebhook(true)}
                          isLoading={state.rotatingSecret}
                        >
                          Rotate webhook secret
                        </Button>
                      </>
                    ) : null}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => void handleClearSecrets(provider)}
                      isLoading={state.clearing}
                      className="text-danger hover:bg-danger/10 hover:text-danger"
                    >
                      Clear secrets
                    </Button>
                    <Button size="sm" onClick={() => void handleSave(provider)} isLoading={state.saving}>
                      Save {PROVIDER_LABELS[provider]}
                    </Button>
                  </div>
                ) : null}
              </div>

              <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
                <div className="space-y-4">
                  {provider === 'jira' ? (
                    <div className={remediationInsetClass('default', 'space-y-4 p-4')}>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={healthBadgeVariant(item.health?.status)}>
                          {item.health?.status ? item.health.status : 'unknown'}
                        </Badge>
                        <Badge variant={item.health?.credentials_valid ? 'success' : 'default'}>
                          {item.health?.credentials_valid ? 'Credentials valid' : 'Credentials unchecked'}
                        </Badge>
                        <Badge variant={item.health?.webhook_registered ? 'success' : 'default'}>
                          {item.health?.webhook_registered ? 'Webhook registered' : 'Webhook unregistered'}
                        </Badge>
                        <Badge variant={item.health?.signed_webhook_enabled ? 'info' : 'default'}>
                          {item.health?.signed_webhook_enabled ? 'Signed delivery enabled' : 'Legacy token / none'}
                        </Badge>
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <HealthField
                          label="Project check"
                          value={
                            item.health?.project_valid == null
                              ? 'Not validated'
                              : item.health.project_valid
                                ? 'Project found'
                                : 'Project invalid'
                          }
                        />
                        <HealthField
                          label="Issue type check"
                          value={
                            item.health?.issue_type_valid == null
                              ? 'Not validated'
                              : item.health.issue_type_valid
                                ? 'Issue type valid'
                                : 'Issue type invalid'
                          }
                        />
                        <HealthField
                          label="Transition map"
                          value={
                            item.health?.transition_map_valid == null
                              ? 'Not validated'
                              : item.health.transition_map_valid
                                ? 'Workflow compatible'
                                : 'Needs workflow fix'
                          }
                        />
                        <HealthField
                          label="Webhook mode"
                          value={item.health?.webhook_mode ? item.health.webhook_mode.replace(/_/g, ' ') : 'unconfigured'}
                        />
                        <HealthField label="Last validated" value={formatTimestamp(item.health?.last_validated_at)} />
                        <HealthField label="Last inbound" value={formatTimestamp(item.health?.last_inbound_at)} />
                        <HealthField label="Last outbound" value={formatTimestamp(item.health?.last_outbound_at)} />
                        <HealthField
                          label="Provider error"
                          value={item.health?.last_provider_error ? item.health.last_provider_error : 'No recent provider error'}
                        />
                      </div>
                      {item.health?.last_validation_error ? (
                        <SettingsNotice tone="danger">{item.health.last_validation_error}</SettingsNotice>
                      ) : null}
                      {item.health?.transition_map_valid === false ? (
                        <SettingsNotice tone="warning">
                          The saved Jira transition map does not match the target workflow. Review the project workflow
                          and transition IDs before rollout.
                        </SettingsNotice>
                      ) : null}
                    </div>
                  ) : null}

                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="flex items-center gap-2 text-sm font-medium text-text">
                      <input
                        type="checkbox"
                        checked={form.enabled}
                        onChange={(event) => updateForm(provider, { enabled: event.target.checked })}
                        disabled={!isAdmin}
                        className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                      />
                      Enabled
                    </label>
                    <label className="flex items-center gap-2 text-sm font-medium text-text">
                      <input
                        type="checkbox"
                        checked={form.outbound_enabled}
                        onChange={(event) => updateForm(provider, { outbound_enabled: event.target.checked })}
                        disabled={!isAdmin}
                        className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                      />
                      Outbound sync
                    </label>
                    <label className="flex items-center gap-2 text-sm font-medium text-text">
                      <input
                        type="checkbox"
                        checked={form.inbound_enabled}
                        onChange={(event) => updateForm(provider, { inbound_enabled: event.target.checked })}
                        disabled={!isAdmin}
                        className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                      />
                      Inbound sync
                    </label>
                    <label className="flex items-center gap-2 text-sm font-medium text-text">
                      <input
                        type="checkbox"
                        checked={form.auto_create}
                        onChange={(event) => updateForm(provider, { auto_create: event.target.checked })}
                        disabled={!isAdmin}
                        className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                      />
                      Auto-create
                    </label>
                  </div>

                  <label className="flex items-center gap-2 text-sm font-medium text-text">
                    <input
                      type="checkbox"
                      checked={form.reopen_on_regression}
                      onChange={(event) => updateForm(provider, { reopen_on_regression: event.target.checked })}
                      disabled={!isAdmin}
                      className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                    />
                    Reopen on regression
                  </label>

                  <div className={remediationInsetClass('default', 'p-4')}>
                    <p className="text-sm font-medium text-text">Secret replacement</p>
                    <p className="mt-1 text-sm text-muted">
                      Leave these blank to keep the current stored secret set. Clearing uses the dedicated button above.
                    </p>
                    <div className="mt-4 grid gap-4">
                      {provider === 'jira' ? (
                        <>
                          <Input
                            label="User email"
                            value={form.user_email}
                            onChange={(event) => updateForm(provider, { user_email: event.target.value })}
                            disabled={!isAdmin}
                            placeholder="jira-user@example.com"
                          />
                          <Input
                            label="API token"
                            value={form.api_token}
                            onChange={(event) => updateForm(provider, { api_token: event.target.value })}
                            disabled={!isAdmin}
                            placeholder="Jira API token"
                            type="password"
                          />
                        </>
                      ) : null}

                      {provider === 'servicenow' ? (
                        <>
                          <Input
                            label="Username"
                            value={form.username}
                            onChange={(event) => updateForm(provider, { username: event.target.value })}
                            disabled={!isAdmin}
                            placeholder="ServiceNow username"
                          />
                          <Input
                            label="Password"
                            value={form.password}
                            onChange={(event) => updateForm(provider, { password: event.target.value })}
                            disabled={!isAdmin}
                            placeholder="ServiceNow password"
                            type="password"
                          />
                        </>
                      ) : null}

                      {provider === 'slack' ? (
                        <Input
                          label="Bot token"
                          value={form.bot_token}
                          onChange={(event) => updateForm(provider, { bot_token: event.target.value })}
                          disabled={!isAdmin}
                          placeholder="xoxb-..."
                          type="password"
                        />
                      ) : null}

                      <Input
                        label="Inbound webhook token"
                        value={form.webhook_token}
                        onChange={(event) => updateForm(provider, { webhook_token: event.target.value })}
                        disabled={!isAdmin}
                        placeholder="Shared webhook token"
                        type="password"
                        helperText={
                          provider === 'jira'
                            ? 'Legacy fallback only for Jira. Leave blank to keep signed webhook delivery as the primary auth path.'
                            : 'Re-enter this when replacing a secret set that already has inbound auth configured.'
                        }
                      />
                      </div>
                    </div>
                </div>

                <div className="space-y-4">
                  {provider === 'jira' ? (
                    <>
                      {jiraValidation && jiraValidation.errors.length > 0 ? (
                        <SettingsNotice tone="danger">
                          {jiraValidation.errors.join(' ')}
                        </SettingsNotice>
                      ) : null}
                      {jiraValidation && jiraValidation.warnings.length > 0 ? (
                        <SettingsNotice tone="warning">
                          {jiraValidation.warnings.join(' ')}
                        </SettingsNotice>
                      ) : null}
                      <div className="grid gap-4 md:grid-cols-2">
                        <Input
                          label="Base URL"
                          value={form.base_url}
                          onChange={(event) => updateForm(provider, { base_url: event.target.value })}
                          disabled={!isAdmin}
                          placeholder="https://your-domain.atlassian.net"
                        />
                        <Input
                          label="Project key"
                          value={form.project_key}
                          onChange={(event) => updateForm(provider, { project_key: event.target.value })}
                          disabled={!isAdmin}
                          placeholder="SEC"
                        />
                      </div>
                      <Input
                        label="Issue type"
                        value={form.issue_type}
                        onChange={(event) => updateForm(provider, { issue_type: event.target.value })}
                        disabled={!isAdmin}
                        placeholder="Task"
                      />
                      <TextAreaField
                        id="jira-transition-map"
                        label="Transition map"
                        value={form.transition_map}
                        onChange={(value) => updateForm(provider, { transition_map: value })}
                        disabled={!isAdmin}
                        placeholder={'{\n  "resolved": "31"\n}'}
                        helperText="Optional JSON object keyed by canonical status."
                      />
                      <TextAreaField
                        id="jira-assignee-account-map"
                        label="Assignee account map"
                        value={form.assignee_account_map}
                        onChange={(value) => updateForm(provider, { assignee_account_map: value })}
                        disabled={!isAdmin}
                        placeholder={'{\n  "owner@company.com": "5b10ac8d82e05b22cc7d4ef5"\n}'}
                        helperText="Optional JSON object mapping platform owner keys to verified Jira accountId values."
                      />
                      <Input
                        label="Canary action ID"
                        value={form.canary_action_id}
                        onChange={(event) => updateForm(provider, { canary_action_id: event.target.value })}
                        disabled={!isAdmin}
                        placeholder="00000000-0000-0000-0000-000000000000"
                        helperText="Optional action UUID used by the Run canary sync control."
                      />
                    </>
                  ) : null}

                  {provider === 'servicenow' ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      <Input
                        label="Base URL"
                        value={form.base_url}
                        onChange={(event) => updateForm(provider, { base_url: event.target.value })}
                        disabled={!isAdmin}
                        placeholder="https://instance.service-now.com"
                      />
                      <Input
                        label="Table"
                        value={form.table}
                        onChange={(event) => updateForm(provider, { table: event.target.value })}
                        disabled={!isAdmin}
                        placeholder="incident"
                      />
                    </div>
                  ) : null}

                  {provider === 'slack' ? (
                    <div className="grid gap-4 md:grid-cols-2">
                      <Input
                        label="Channel ID"
                        value={form.channel_id}
                        onChange={(event) => updateForm(provider, { channel_id: event.target.value })}
                        disabled={!isAdmin}
                        placeholder="C0123456789"
                      />
                      <Input
                        label="API base URL"
                        value={form.api_base_url}
                        onChange={(event) => updateForm(provider, { api_base_url: event.target.value })}
                        disabled={!isAdmin}
                        placeholder="https://slack.com/api"
                      />
                    </div>
                  ) : null}

                  {state.error ? <SettingsNotice tone="danger">{state.error}</SettingsNotice> : null}
                  {state.success ? <SettingsNotice tone="success">{state.success}</SettingsNotice> : null}
                </div>
              </div>
            </SettingsCard>
          ))}
        </div>
      )}
    </div>
  );
}
