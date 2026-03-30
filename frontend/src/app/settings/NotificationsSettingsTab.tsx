'use client';

import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { dashboardFieldClass } from '@/components/ui/remediation-surface';
import { useAuth } from '@/contexts/AuthContext';
import {
  getDigestSettings,
  getErrorMessage,
  getSlackSettings,
  patchDigestSettings,
  patchSlackSettings,
  type DigestSettingsResponse,
  type SlackSettingsResponse,
} from '@/lib/api';
import { SettingsCard, SettingsNotice, SettingsSectionIntro } from './settings-ui';

export function NotificationsSettingsTab() {
  const { user, isAuthenticated } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [digestSettings, setDigestSettings] = useState<DigestSettingsResponse | null>(null);
  const [slackSettings, setSlackSettings] = useState<SlackSettingsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [digestForm, setDigestForm] = useState({ digest_enabled: true, digest_recipients: '' });
  const [slackForm, setSlackForm] = useState({ slack_digest_enabled: false, slack_webhook_url: '' });
  const [showSlackWebhookInput, setShowSlackWebhookInput] = useState(false);
  const [confirmClearWebhookOpen, setConfirmClearWebhookOpen] = useState(false);

  const [digestSaving, setDigestSaving] = useState(false);
  const [slackSaving, setSlackSaving] = useState(false);
  const [digestError, setDigestError] = useState<string | null>(null);
  const [slackError, setSlackError] = useState<string | null>(null);
  const [digestSuccess, setDigestSuccess] = useState<string | null>(null);
  const [slackSuccess, setSlackSuccess] = useState<string | null>(null);

  const fetchSettings = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setDigestError(null);
    setSlackError(null);
    try {
      const [digest, slack] = await Promise.all([getDigestSettings(), getSlackSettings()]);
      setDigestSettings(digest);
      setSlackSettings(slack);
      setDigestForm({
        digest_enabled: digest.digest_enabled,
        digest_recipients: digest.digest_recipients ?? '',
      });
      setSlackForm({
        slack_digest_enabled: slack.slack_digest_enabled,
        slack_webhook_url: '',
      });
      setShowSlackWebhookInput(false);
    } catch (err) {
      const message = getErrorMessage(err);
      setDigestError(message);
      setSlackError(message);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void fetchSettings();
  }, [fetchSettings]);

  async function handleSaveDigestSettings(event: React.FormEvent) {
    event.preventDefault();
    setDigestError(null);
    setDigestSuccess(null);
    setDigestSaving(true);
    try {
      const updated = await patchDigestSettings({
        digest_enabled: digestForm.digest_enabled,
        digest_recipients: digestForm.digest_recipients.trim() || null,
      });
      setDigestSettings(updated);
      setDigestForm({
        digest_enabled: updated.digest_enabled,
        digest_recipients: updated.digest_recipients ?? '',
      });
      setDigestSuccess('Digest settings saved.');
    } catch (err) {
      const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status: number }).status : 0;
      setDigestError(status === 403 ? 'Only admins can update digest settings.' : getErrorMessage(err));
    } finally {
      setDigestSaving(false);
    }
  }

  async function handleSaveSlackSettings(event: React.FormEvent) {
    event.preventDefault();
    setSlackError(null);
    setSlackSuccess(null);
    setSlackSaving(true);
    const includeWebhook = showSlackWebhookInput || !slackSettings?.slack_webhook_configured;

    try {
      const updated = await patchSlackSettings({
        ...(includeWebhook ? { slack_webhook_url: slackForm.slack_webhook_url.trim() || null } : {}),
        slack_digest_enabled: slackForm.slack_digest_enabled,
      });
      setSlackSettings(updated);
      setSlackForm({ slack_digest_enabled: updated.slack_digest_enabled, slack_webhook_url: '' });
      setShowSlackWebhookInput(false);
      setSlackSuccess('Slack settings saved.');
    } catch (err) {
      const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status: number }).status : 0;
      setSlackError(status === 403 ? 'Only admins can update Slack settings.' : getErrorMessage(err));
    } finally {
      setSlackSaving(false);
    }
  }

  async function handleClearSlackWebhook() {
    setSlackError(null);
    setSlackSuccess(null);
    setSlackSaving(true);
    try {
      const updated = await patchSlackSettings({ slack_webhook_url: '' });
      setSlackSettings(updated);
      setSlackForm((current) => ({ ...current, slack_digest_enabled: updated.slack_digest_enabled, slack_webhook_url: '' }));
      setShowSlackWebhookInput(false);
      setSlackSuccess('Slack webhook cleared.');
    } catch (err) {
      const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status: number }).status : 0;
      setSlackError(status === 403 ? 'Only admins can update Slack settings.' : getErrorMessage(err));
    } finally {
      setSlackSaving(false);
    }
  }

  return (
    <div id="settings-panel-notifications" role="tabpanel" tabIndex={0} className="space-y-6">
      <SettingsSectionIntro
        title="Notifications"
        description="Configure the weekly digest delivery channels. Governance escalations are managed in the separate Governance tab."
        action={isAdmin ? undefined : <Badge variant="info">Members are read-only</Badge>}
      />

      {isLoading ? (
        <SettingsCard>
          <p className="animate-pulse text-muted">Loading notification settings...</p>
        </SettingsCard>
      ) : (
        <>
          <SettingsCard className="space-y-4">
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-text">Weekly email digest</h3>
              {digestSettings ? (
                <Badge variant={digestSettings.digest_enabled ? 'success' : 'default'}>
                  {digestSettings.digest_enabled ? 'Enabled' : 'Disabled'}
                </Badge>
              ) : null}
            </div>
            <p className="text-sm text-muted">
              Send a weekly summary of open actions, new findings, and expiring exceptions by email.
            </p>

            <form onSubmit={handleSaveDigestSettings} className="space-y-4">
              <label className="flex items-center gap-2 text-sm font-medium text-text">
                <input
                  type="checkbox"
                  checked={digestForm.digest_enabled}
                  onChange={(event) => setDigestForm((current) => ({ ...current, digest_enabled: event.target.checked }))}
                  disabled={!isAdmin}
                  className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                />
                Send weekly digest
              </label>

              <div>
                <label htmlFor="digest-recipients" className="block text-sm font-medium text-text">
                  Recipients
                </label>
                <input
                  id="digest-recipients"
                  type="text"
                  value={digestForm.digest_recipients}
                  onChange={(event) => setDigestForm((current) => ({ ...current, digest_recipients: event.target.value }))}
                  disabled={!isAdmin}
                  placeholder="admin@company.com, team@company.com"
                  className={dashboardFieldClass('mt-1')}
                />
                <p className="mt-1.5 text-sm text-muted">Leave empty to send to all tenant admins.</p>
              </div>

              {digestError ? <SettingsNotice tone="danger">{digestError}</SettingsNotice> : null}
              {digestSuccess ? <SettingsNotice tone="success">{digestSuccess}</SettingsNotice> : null}

              {isAdmin ? (
                <Button type="submit" isLoading={digestSaving}>
                  Save digest settings
                </Button>
              ) : null}
            </form>
          </SettingsCard>

          <SettingsCard className="space-y-4">
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-text">Slack digest delivery</h3>
              {slackSettings?.slack_webhook_configured ? (
                <Badge variant="success">Webhook configured</Badge>
              ) : (
                <Badge variant="default">Webhook not configured</Badge>
              )}
            </div>
            <p className="text-sm text-muted">
              Post the weekly digest into Slack using an incoming webhook. Stored URLs are never shown after save.
            </p>

            <form onSubmit={handleSaveSlackSettings} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text">Slack webhook</label>
                {slackSettings?.slack_webhook_configured && !showSlackWebhookInput ? (
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <Badge variant="success">Configured</Badge>
                    {isAdmin ? (
                      <>
                        <Button type="button" variant="secondary" size="sm" onClick={() => setShowSlackWebhookInput(true)}>
                          Replace webhook
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setConfirmClearWebhookOpen(true)}
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
                    value={slackForm.slack_webhook_url}
                    onChange={(event) => setSlackForm((current) => ({ ...current, slack_webhook_url: event.target.value }))}
                    disabled={!isAdmin}
                    placeholder="https://hooks.slack.com/services/..."
                    className={dashboardFieldClass('mt-1')}
                  />
                )}
              </div>

              {showSlackWebhookInput && slackSettings?.slack_webhook_configured ? (
                <p className="text-sm text-muted">Enter a new webhook URL to replace the current one.</p>
              ) : null}

              <label className="flex items-center gap-2 text-sm font-medium text-text">
                <input
                  type="checkbox"
                  checked={slackForm.slack_digest_enabled}
                  onChange={(event) => setSlackForm((current) => ({ ...current, slack_digest_enabled: event.target.checked }))}
                  disabled={!isAdmin}
                  className="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                />
                Send weekly digest to Slack
              </label>

              {slackError ? <SettingsNotice tone="danger">{slackError}</SettingsNotice> : null}
              {slackSuccess ? <SettingsNotice tone="success">{slackSuccess}</SettingsNotice> : null}

              {isAdmin ? (
                <Button type="submit" isLoading={slackSaving}>
                  Save Slack settings
                </Button>
              ) : null}
            </form>
          </SettingsCard>
        </>
      )}

      <Modal
        isOpen={confirmClearWebhookOpen}
        onClose={() => setConfirmClearWebhookOpen(false)}
        title="Clear Slack webhook?"
      >
        <div className="space-y-4">
          <p className="text-sm text-muted">This stops Slack digest delivery until a new webhook URL is saved.</p>
          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setConfirmClearWebhookOpen(false)}
              disabled={slackSaving}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              onClick={async () => {
                setConfirmClearWebhookOpen(false);
                await handleClearSlackWebhook();
              }}
              isLoading={slackSaving}
            >
              Clear webhook
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
