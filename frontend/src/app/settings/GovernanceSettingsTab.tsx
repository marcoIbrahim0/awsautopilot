'use client';

import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useAuth } from '@/contexts/AuthContext';
import {
  getErrorMessage,
  getGovernanceSettings,
  patchGovernanceSettings,
  type GovernanceSettingsResponse,
} from '@/lib/api';
import { SettingsCard, SettingsNotice, SettingsSectionIntro } from './settings-ui';

export function GovernanceSettingsTab() {
  const { user, isAuthenticated } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [settings, setSettings] = useState<GovernanceSettingsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showWebhookInput, setShowWebhookInput] = useState(false);
  const [clearModalOpen, setClearModalOpen] = useState(false);
  const [form, setForm] = useState({
    governance_notifications_enabled: false,
    governance_webhook_url: '',
  });

  const loadSettings = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await getGovernanceSettings();
      setSettings(response);
      setForm({
        governance_notifications_enabled: response.governance_notifications_enabled,
        governance_webhook_url: '',
      });
      setShowWebhookInput(false);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const includeWebhook = showWebhookInput || !settings?.governance_webhook_configured;
      const updated = await patchGovernanceSettings({
        governance_notifications_enabled: form.governance_notifications_enabled,
        ...(includeWebhook ? { governance_webhook_url: form.governance_webhook_url.trim() || null } : {}),
      });
      setSettings(updated);
      setForm({
        governance_notifications_enabled: updated.governance_notifications_enabled,
        governance_webhook_url: '',
      });
      setShowWebhookInput(false);
      setSuccess('Governance settings saved.');
    } catch (err) {
      const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status: number }).status : 0;
      setError(status === 403 ? 'Only admins can update governance settings.' : getErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleClearWebhook() {
    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const updated = await patchGovernanceSettings({ governance_webhook_url: '' });
      setSettings(updated);
      setForm((current) => ({ ...current, governance_webhook_url: '' }));
      setShowWebhookInput(false);
      setSuccess('Governance webhook cleared.');
    } catch (err) {
      const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status: number }).status : 0;
      setError(status === 403 ? 'Only admins can update governance settings.' : getErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div id="settings-panel-governance" role="tabpanel" tabIndex={0} className="space-y-6">
      <SettingsSectionIntro
        title="Governance"
        description="Configure tenant-scoped governance communication delivery and the escalation webhook used by the governance layer."
        titleExplainer={{ conceptId: 'settings_governance', context: 'settings' }}
        action={isAdmin ? undefined : <Badge variant="info">Members are read-only</Badge>}
      />

      {isLoading ? (
        <SettingsCard>
          <p className="animate-pulse text-muted">Loading governance settings...</p>
        </SettingsCard>
      ) : (
        <SettingsCard className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-text">Governance webhook</h3>
            {settings?.governance_webhook_configured ? (
              <Badge variant="success">Webhook configured</Badge>
            ) : (
              <Badge variant="default">Webhook not configured</Badge>
            )}
          </div>
          <p className="text-sm text-muted">
            Governance dispatch is additive to digest delivery. Stored webhook URLs are never shown after save.
          </p>

          <form onSubmit={handleSave} className="space-y-4">
            <label className="flex items-center gap-2 text-sm font-medium text-text">
              <input
                type="checkbox"
                checked={form.governance_notifications_enabled}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    governance_notifications_enabled: event.target.checked,
                  }))
                }
                disabled={!isAdmin}
                className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
              />
              Enable governance notifications
            </label>

            <div>
              <label className="block text-sm font-medium text-text">Webhook endpoint</label>
              {settings?.governance_webhook_configured && !showWebhookInput ? (
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <Badge variant="success">Configured</Badge>
                  {isAdmin ? (
                    <>
                      <Button type="button" variant="secondary" size="sm" onClick={() => setShowWebhookInput(true)}>
                        Replace webhook
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setClearModalOpen(true)}
                        className="text-danger hover:bg-danger/10 hover:text-danger"
                      >
                        Clear webhook
                      </Button>
                    </>
                  ) : null}
                </div>
              ) : (
                <input
                  type="url"
                  value={form.governance_webhook_url}
                  onChange={(event) => setForm((current) => ({ ...current, governance_webhook_url: event.target.value }))}
                  disabled={!isAdmin}
                  placeholder="https://example.com/governance"
                  className="mt-1 w-full rounded-xl border border-border bg-dropdown-bg px-3 py-2 text-sm text-text placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                />
              )}
            </div>

            {showWebhookInput && settings?.governance_webhook_configured ? (
              <p className="text-sm text-muted">Enter a new webhook URL to replace the current stored endpoint.</p>
            ) : null}

            {error ? <SettingsNotice tone="danger">{error}</SettingsNotice> : null}
            {success ? <SettingsNotice tone="success">{success}</SettingsNotice> : null}

            {isAdmin ? (
              <Button type="submit" isLoading={isSaving}>
                Save governance settings
              </Button>
            ) : null}
          </form>
        </SettingsCard>
      )}

      <Modal
        isOpen={clearModalOpen}
        onClose={() => setClearModalOpen(false)}
        title="Clear governance webhook?"
      >
        <div className="space-y-4">
          <p className="text-sm text-muted">
            This removes the stored governance webhook until a new endpoint is saved.
          </p>
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={() => setClearModalOpen(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={async () => {
                setClearModalOpen(false);
                await handleClearWebhook();
              }}
              isLoading={isSaving}
            >
              Clear webhook
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
