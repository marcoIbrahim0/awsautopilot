import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { IntegrationsSettingsTab } from './IntegrationsSettingsTab';
import {
  listIntegrationSettings,
  patchIntegrationSettings,
  runJiraCanarySync,
  syncJiraIntegrationWebhook,
  type IntegrationSettingsItemResponse,
  validateJiraIntegrationSettings,
} from '@/lib/api';

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { role: 'admin' },
  }),
}));

vi.mock('@/lib/api', () => ({
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
  listIntegrationSettings: vi.fn(),
  patchIntegrationSettings: vi.fn(),
  runJiraCanarySync: vi.fn(),
  syncJiraIntegrationWebhook: vi.fn(),
  validateJiraIntegrationSettings: vi.fn(),
}));

const mockedListIntegrationSettings = vi.mocked(listIntegrationSettings);
const mockedPatchIntegrationSettings = vi.mocked(patchIntegrationSettings);
const mockedRunJiraCanarySync = vi.mocked(runJiraCanarySync);
const mockedSyncJiraIntegrationWebhook = vi.mocked(syncJiraIntegrationWebhook);
const mockedValidateJiraIntegrationSettings = vi.mocked(validateJiraIntegrationSettings);

function buildJiraItem(overrides: Partial<IntegrationSettingsItemResponse> = {}): IntegrationSettingsItemResponse {
  return {
    provider: 'jira',
    enabled: true,
    outbound_enabled: true,
    inbound_enabled: true,
    auto_create: true,
    reopen_on_regression: true,
    config: {
      base_url: 'https://example.atlassian.net',
      project_key: 'SEC',
      issue_type: 'Task',
      canary_action_id: '11111111-1111-4111-8111-111111111111',
    },
    secret_configured: true,
    webhook_configured: true,
    health: {
      status: 'healthy',
      credentials_valid: true,
      project_valid: true,
      issue_type_valid: true,
      transition_map_valid: true,
      webhook_registered: true,
      signed_webhook_enabled: true,
      webhook_mode: 'signed_admin_webhook',
      last_validated_at: '2026-03-30T10:00:00Z',
      last_validation_error: null,
      last_inbound_at: '2026-03-30T10:05:00Z',
      last_outbound_at: '2026-03-30T10:06:00Z',
      last_provider_error: null,
      last_provider_error_at: null,
      details: {},
    },
    ...overrides,
  };
}

describe('IntegrationsSettingsTab', () => {
  beforeEach(() => {
    mockedPatchIntegrationSettings.mockReset();
    mockedRunJiraCanarySync.mockReset();
    mockedSyncJiraIntegrationWebhook.mockReset();
    mockedValidateJiraIntegrationSettings.mockReset();
    mockedListIntegrationSettings.mockResolvedValue({
      items: [
        buildJiraItem(),
        {
          provider: 'servicenow',
          enabled: false,
          outbound_enabled: false,
          inbound_enabled: false,
          auto_create: false,
          reopen_on_regression: false,
          config: {},
          secret_configured: false,
          webhook_configured: false,
          health: null,
        } satisfies IntegrationSettingsItemResponse,
        {
          provider: 'slack',
          enabled: false,
          outbound_enabled: false,
          inbound_enabled: false,
          auto_create: false,
          reopen_on_regression: false,
          config: {},
          secret_configured: false,
          webhook_configured: false,
          health: null,
        } satisfies IntegrationSettingsItemResponse,
      ],
    });
  });

  it('renders Jira health details and runs the validate action', async () => {
    const user = userEvent.setup();
    mockedValidateJiraIntegrationSettings.mockResolvedValue({
      provider: 'jira',
      message: 'Jira validation completed.',
      item: buildJiraItem(),
      task_ids: [],
      queued: 0,
      failed_to_enqueue: 0,
    });

    render(<IntegrationsSettingsTab />);

    expect(await screen.findByText('Signed delivery enabled')).toBeInTheDocument();
    expect(screen.getByText('Webhook mode')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Validate connection' }));

    await waitFor(() => {
      expect(mockedValidateJiraIntegrationSettings).toHaveBeenCalledOnce();
    });
    expect(await screen.findByText('Jira validation completed.')).toBeInTheDocument();
  });

  it('shows inline Jira validation errors before save', async () => {
    const user = userEvent.setup();

    render(<IntegrationsSettingsTab />);

    const canaryActionId = await screen.findByLabelText('Canary action ID');
    await user.clear(canaryActionId);
    await user.type(canaryActionId, 'not-a-uuid');

    expect(await screen.findByText('Canary action ID must be a valid UUID.')).toBeInTheDocument();
    expect(mockedPatchIntegrationSettings).not.toHaveBeenCalled();
  });
});
