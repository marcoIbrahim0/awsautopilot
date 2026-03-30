'use client';

import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useAuth } from '@/contexts/AuthContext';
import {
  type ConfigDeliveryMode,
  getErrorMessage,
  getRemediationSettings,
  patchRemediationSettings,
  type S3EncryptionMode,
  type SGAccessPathPreference,
  type RemediationSettingsResponse,
} from '@/lib/api';
import { SelectField, SettingsCard, SettingsNotice, SettingsSectionIntro, TextAreaField } from './settings-ui';
import { getRemediationSettingsFieldIds } from '@/lib/remediationSettingsLinks';

type RemediationFormState = {
  sg_access_path_preference: string;
  approved_admin_cidrs: string;
  approved_bastion_security_group_ids: string;
  cloudtrail_default_bucket_name: string;
  cloudtrail_default_kms_key_arn: string;
  config_delivery_mode: string;
  config_default_bucket_name: string;
  config_default_kms_key_arn: string;
  s3_access_logs_default_target_bucket_name: string;
  s3_encryption_mode: string;
  s3_encryption_kms_key_arn: string;
};

function listToText(values: string[]): string {
  return values.join('\n');
}

function parseListInput(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function toSgAccessPathPreference(value: string): SGAccessPathPreference | null {
  if (!value) return null;
  return value as SGAccessPathPreference;
}

function toConfigDeliveryMode(value: string): ConfigDeliveryMode | null {
  if (!value) return null;
  return value as ConfigDeliveryMode;
}

function toS3EncryptionMode(value: string): S3EncryptionMode | null {
  if (!value) return null;
  return value as S3EncryptionMode;
}

function buildFormState(settings: RemediationSettingsResponse): RemediationFormState {
  return {
    sg_access_path_preference: settings.sg_access_path_preference ?? '',
    approved_admin_cidrs: listToText(settings.approved_admin_cidrs),
    approved_bastion_security_group_ids: listToText(settings.approved_bastion_security_group_ids),
    cloudtrail_default_bucket_name: settings.cloudtrail.default_bucket_name ?? '',
    cloudtrail_default_kms_key_arn: settings.cloudtrail.default_kms_key_arn ?? '',
    config_delivery_mode: settings.config.delivery_mode ?? '',
    config_default_bucket_name: settings.config.default_bucket_name ?? '',
    config_default_kms_key_arn: settings.config.default_kms_key_arn ?? '',
    s3_access_logs_default_target_bucket_name: settings.s3_access_logs.default_target_bucket_name ?? '',
    s3_encryption_mode: settings.s3_encryption.mode ?? '',
    s3_encryption_kms_key_arn: settings.s3_encryption.kms_key_arn ?? '',
  };
}

const FIELD_IDS = getRemediationSettingsFieldIds();
const LINKABLE_FIELD_IDS = new Set<string>(Object.values(FIELD_IDS));

export function RemediationDefaultsTab() {
  const { user, isAuthenticated } = useAuth();
  const isAdmin = user?.role === 'admin';

  const [settings, setSettings] = useState<RemediationSettingsResponse | null>(null);
  const [form, setForm] = useState<RemediationFormState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadSettings = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await getRemediationSettings();
      setSettings(response);
      setForm(buildFormState(response));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  useEffect(() => {
    if (isLoading || !form || !settings || typeof window === 'undefined') return;
    const hash = window.location.hash.replace(/^#/, '').trim();
    if (!LINKABLE_FIELD_IDS.has(hash)) return;
    const element = document.getElementById(hash);
    if (!element) return;
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    window.requestAnimationFrame(() => {
      if (typeof (element as HTMLElement).focus === 'function') {
        (element as HTMLElement).focus();
      }
    });
  }, [form, isLoading, settings]);

  function updateForm(patch: Partial<RemediationFormState>) {
    setForm((current) => (current ? { ...current, ...patch } : current));
  }

  async function handleSave(event: React.FormEvent) {
    event.preventDefault();
    if (!form) return;

    setIsSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const updated = await patchRemediationSettings({
        sg_access_path_preference: toSgAccessPathPreference(form.sg_access_path_preference),
        approved_admin_cidrs: parseListInput(form.approved_admin_cidrs),
        approved_bastion_security_group_ids: parseListInput(form.approved_bastion_security_group_ids),
        cloudtrail: {
          default_bucket_name: form.cloudtrail_default_bucket_name.trim() || null,
          default_kms_key_arn: form.cloudtrail_default_kms_key_arn.trim() || null,
        },
        config: {
          delivery_mode: toConfigDeliveryMode(form.config_delivery_mode),
          default_bucket_name: form.config_default_bucket_name.trim() || null,
          default_kms_key_arn: form.config_default_kms_key_arn.trim() || null,
        },
        s3_access_logs: {
          default_target_bucket_name: form.s3_access_logs_default_target_bucket_name.trim() || null,
        },
        s3_encryption: {
          mode: toS3EncryptionMode(form.s3_encryption_mode),
          kms_key_arn: form.s3_encryption_kms_key_arn.trim() || null,
        },
      });
      setSettings(updated);
      setForm(buildFormState(updated));
      setSuccess('Remediation defaults saved.');
    } catch (err) {
      const status = typeof err === 'object' && err !== null && 'status' in err ? (err as { status: number }).status : 0;
      setError(status === 403 ? 'Only admins can update remediation defaults.' : getErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div id="settings-panel-remediation-defaults" role="tabpanel" tabIndex={0} className="space-y-6">
      <SettingsSectionIntro
        title="Remediation Defaults"
        description="Configure tenant-scoped defaults that shape PR-bundle generation and remediation profile resolution."
        titleExplainer={{ conceptId: 'settings_remediation_defaults', context: 'settings' }}
        action={isAdmin ? undefined : <Badge variant="info">Members can view only</Badge>}
      />

      {isLoading || !form || !settings ? (
        <SettingsCard>
          <p className="animate-pulse text-muted">Loading remediation defaults...</p>
        </SettingsCard>
      ) : (
        <form onSubmit={handleSave} className="space-y-6">
          <div className="grid gap-6 xl:grid-cols-2">
            <SettingsCard className="space-y-4">
              <h3 className="text-base font-semibold text-text">Security-group access defaults</h3>

              <SelectField
                id="sg-access-path-preference"
                label="Security-group access path preference"
                labelExplainer={{ conceptId: 'settings_remediation_defaults', context: 'settings' }}
                value={form.sg_access_path_preference}
                onChange={(value) => updateForm({ sg_access_path_preference: value })}
                disabled={!isAdmin}
                placeholder="No default preference"
                options={[
                  {
                    value: 'close_public',
                    label: 'Add restricted access without removing old public rules',
                  },
                  { value: 'restrict_to_detected_public_ip', label: 'Restrict to detected public IP' },
                  { value: 'restrict_to_approved_admin_cidr', label: 'Restrict to approved admin CIDRs' },
                  { value: 'bastion_sg_reference', label: 'Reference approved bastion security groups' },
                  { value: 'ssm_only', label: 'Require SSM-only access' },
                ]}
              />

              <TextAreaField
                id="approved-admin-cidrs"
                label="Approved admin CIDRs"
                labelExplainer={{ conceptId: 'settings_remediation_defaults', context: 'settings' }}
                value={form.approved_admin_cidrs}
                onChange={(value) => updateForm({ approved_admin_cidrs: value })}
                disabled={!isAdmin}
                placeholder={'203.0.113.10/32\n198.51.100.0/24'}
                helperText="Enter one CIDR per line or separate values with commas."
              />

              <TextAreaField
                id="approved-bastion-security-group-ids"
                label="Approved bastion security group IDs"
                labelExplainer={{ conceptId: 'settings_remediation_defaults', context: 'settings' }}
                value={form.approved_bastion_security_group_ids}
                onChange={(value) => updateForm({ approved_bastion_security_group_ids: value })}
                disabled={!isAdmin}
                placeholder={'sg-0123456789abcdef0\nsg-0123456789abcdef1'}
                helperText="Enter one security-group ID per line or separate values with commas."
              />
            </SettingsCard>

            <SettingsCard className="space-y-4">
              <h3 className="text-base font-semibold text-text">CloudTrail defaults</h3>
              <Input
                id={FIELD_IDS.cloudtrail_default_bucket_name}
                label="Default bucket name"
                labelExplainer={{ conceptId: 'settings_remediation_defaults', context: 'settings' }}
                value={form.cloudtrail_default_bucket_name}
                onChange={(event) => updateForm({ cloudtrail_default_bucket_name: event.target.value })}
                disabled={!isAdmin}
                placeholder="security-autopilot-cloudtrail"
              />
              <Input
                id={FIELD_IDS.cloudtrail_default_kms_key_arn}
                label="Default KMS key ARN"
                labelExplainer={{ conceptId: 'settings_remediation_defaults', context: 'settings' }}
                value={form.cloudtrail_default_kms_key_arn}
                onChange={(event) => updateForm({ cloudtrail_default_kms_key_arn: event.target.value })}
                disabled={!isAdmin}
                placeholder="arn:aws:kms:eu-north-1:123456789012:key/..."
              />
            </SettingsCard>

            <SettingsCard className="space-y-4">
              <h3 className="text-base font-semibold text-text">AWS Config defaults</h3>
              <SelectField
                id={FIELD_IDS.config_delivery_mode}
                label="Delivery mode"
                labelExplainer={{ conceptId: 'settings_remediation_defaults', context: 'settings' }}
                value={form.config_delivery_mode}
                onChange={(value) => updateForm({ config_delivery_mode: value })}
                disabled={!isAdmin}
                placeholder="No default delivery mode"
                options={[
                  { value: 'account_local_delivery', label: 'Account-local delivery' },
                  { value: 'centralized_delivery', label: 'Centralized delivery' },
                ]}
              />
              <Input
                id={FIELD_IDS.config_default_bucket_name}
                label="Default bucket name"
                value={form.config_default_bucket_name}
                onChange={(event) => updateForm({ config_default_bucket_name: event.target.value })}
                disabled={!isAdmin}
                placeholder="security-autopilot-config"
              />
              <Input
                id={FIELD_IDS.config_default_kms_key_arn}
                label="Default KMS key ARN"
                value={form.config_default_kms_key_arn}
                onChange={(event) => updateForm({ config_default_kms_key_arn: event.target.value })}
                disabled={!isAdmin}
                placeholder="arn:aws:kms:eu-north-1:123456789012:key/..."
              />
            </SettingsCard>

            <SettingsCard className="space-y-4">
              <h3 className="text-base font-semibold text-text">S3 logging and encryption defaults</h3>
              <Input
                id={FIELD_IDS.s3_access_logs_default_target_bucket_name}
                label="Access logs target bucket"
                value={form.s3_access_logs_default_target_bucket_name}
                onChange={(event) =>
                  updateForm({ s3_access_logs_default_target_bucket_name: event.target.value })
                }
                disabled={!isAdmin}
                placeholder="security-autopilot-access-logs"
              />
              <SelectField
                id={FIELD_IDS.s3_encryption_mode}
                label="Encryption mode"
                value={form.s3_encryption_mode}
                onChange={(value) => updateForm({ s3_encryption_mode: value })}
                disabled={!isAdmin}
                placeholder="No default encryption mode"
                options={[
                  { value: 'aws_managed', label: 'AWS managed KMS key' },
                  { value: 'customer_managed', label: 'Customer managed KMS key' },
                ]}
              />
              <Input
                id={FIELD_IDS.s3_encryption_kms_key_arn}
                label="Encryption KMS key ARN"
                value={form.s3_encryption_kms_key_arn}
                onChange={(event) => updateForm({ s3_encryption_kms_key_arn: event.target.value })}
                disabled={!isAdmin}
                placeholder="arn:aws:kms:eu-north-1:123456789012:key/..."
              />
            </SettingsCard>
          </div>

          {error ? <SettingsNotice tone="danger">{error}</SettingsNotice> : null}
          {success ? <SettingsNotice tone="success">{success}</SettingsNotice> : null}

          {isAdmin ? (
            <Button type="submit" isLoading={isSaving}>
              Save remediation defaults
            </Button>
          ) : null}
        </form>
      )}
    </div>
  );
}
