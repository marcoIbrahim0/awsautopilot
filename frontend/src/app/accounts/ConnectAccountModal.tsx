'use client';

import { type FormEvent, useEffect, useRef, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { SelectDropdown } from '@/components/ui/SelectDropdown';
import {
  REMEDIATION_EYEBROW_CLASS,
  RemediationCallout,
  RemediationPanel,
  SectionTitleExplainer,
  remediationInsetClass,
} from '@/components/ui/remediation-surface';
import { useAuth } from '@/contexts/AuthContext';
import { AwsAccount, getErrorMessage, registerAccount, updateAccount } from '@/lib/api';
import { AWS_REGIONS, DEFAULT_REGION, MAX_REGIONS } from '@/lib/aws-regions';

function parseAccountIdFromRoleArn(roleArn: string): string {
  const match = /arn:aws:iam::(\d{12}):role\//.exec(roleArn.trim());
  return match ? match[1] : '';
}

function copyToClipboard(value: string) {
  void navigator.clipboard?.writeText(value);
}

function CopyValueRow({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  if (value == null || value === '') return null;

  return (
    <div className={remediationInsetClass('default', 'flex flex-wrap items-center gap-3 p-4')}>
      <div className="min-w-0 flex-1">
        <p className={REMEDIATION_EYEBROW_CLASS}>{label}</p>
        <code className="mt-3 block overflow-x-auto rounded-xl bg-bg/65 px-3 py-2 font-mono text-sm text-text">
          {String(value)}
        </code>
      </div>
      <Button type="button" variant="secondary" size="sm" onClick={() => copyToClipboard(String(value))}>
        Copy
      </Button>
    </div>
  );
}

interface ConnectAccountModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  tenantId?: string;
  existingAccount?: AwsAccount | null;
}

export function ConnectAccountModal({
  isOpen,
  onClose,
  onSuccess,
  tenantId: tenantIdProp,
  existingAccount,
}: ConnectAccountModalProps) {
  const {
    tenant,
    saas_account_id,
    read_role_default_stack_name,
    read_role_launch_stack_url,
    read_role_template_url,
    buildReadRoleLaunchStackUrl,
    isAuthenticated,
  } = useAuth();
  const [accountId, setAccountId] = useState('');
  const [roleArn, setRoleArn] = useState('');
  const [regions, setRegions] = useState<string[]>([DEFAULT_REGION]);
  const [regionToAdd, setRegionToAdd] = useState('');
  const [readStackName, setReadStackName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const stepBRef = useRef<HTMLDivElement>(null);

  const tenantId = isAuthenticated && tenant ? tenant.id : tenantIdProp;
  const isReconnect = !!existingAccount;

  useEffect(() => {
    if (!isOpen) return;
    if (existingAccount) {
      setAccountId(existingAccount.account_id);
      setRoleArn(existingAccount.role_read_arn);
      setRegions(existingAccount.regions?.length ? [...existingAccount.regions] : [DEFAULT_REGION]);
      setReadStackName('');
      setError(null);
      return;
    }

    setAccountId('');
    setRoleArn('');
    setRegions([DEFAULT_REGION]);
    setReadStackName('');
    setError(null);
  }, [existingAccount, isOpen]);

  const effectiveAccountId = accountId.trim() || parseAccountIdFromRoleArn(roleArn);
  const readStackNameValue = readStackName || read_role_default_stack_name;
  const canSubmit =
    effectiveAccountId.length === 12 &&
    roleArn.trim().length > 0 &&
    regions.length >= 1 &&
    regions.length <= MAX_REGIONS;
  const availableToAdd = AWS_REGIONS.filter((region) => !regions.includes(region.value));

  function handleRoleArnChange(value: string) {
    setRoleArn(value);
    const parsed = parseAccountIdFromRoleArn(value);
    if (parsed && !accountId) {
      setAccountId(parsed);
    }
  }

  function handleClose() {
    if (!isSubmitting) {
      setError(null);
      onClose();
    }
  }

  function addRegion(value: string) {
    if (!value || regions.includes(value) || regions.length >= MAX_REGIONS) return;
    setRegions((current) => [...current, value].sort());
  }

  function removeRegion(value: string) {
    if (regions.length <= 1) return;
    setRegions((current) => current.filter((region) => region !== value));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!tenantId || !canSubmit) return;

    setError(null);
    setIsSubmitting(true);

    try {
      const shouldReconnectExistingAccount =
        !!existingAccount && effectiveAccountId === existingAccount.account_id;

      if (shouldReconnectExistingAccount) {
        await updateAccount(
          existingAccount.account_id,
          {
            role_read_arn: roleArn.trim(),
            regions,
          },
          tenantId,
        );
      } else {
        await registerAccount({
          account_id: effectiveAccountId,
          role_read_arn: roleArn.trim(),
          regions,
          tenant_id: tenantId,
        });
      }

      if (!isReconnect) {
        setAccountId('');
        setRoleArn('');
        setRegions([DEFAULT_REGION]);
        setReadStackName('');
      }
      onSuccess();
      onClose();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isReconnect ? 'Reconnect AWS account' : 'Connect AWS account'}
      size="xl"
      variant="dashboard"
      headerContent={<Badge variant="info">{isReconnect ? 'Reconnect' : 'New account'}</Badge>}
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        <RemediationCallout
          tone="info"
          title="Connection flow"
          description="Deploy the ReadRole stack first, then save the role ARN and monitored regions here. Final readiness checks continue in onboarding."
        />

        <div className="grid gap-6 xl:grid-cols-[1fr_1.05fr]">
          <RemediationPanel className="p-6" tone="accent">
            <div className="space-y-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Step A</p>
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-semibold text-text">Deploy the ReadRole stack in AWS</h3>
                    <SectionTitleExplainer conceptId="read_role_posture" context="accounts" label="Deploy the ReadRole stack in AWS" />
                  </div>
                </div>
                <Badge variant="info">Required</Badge>
              </div>

              <RemediationCallout
                tone="accent"
                description="Use the one-click CloudFormation launch when available. If not, copy the platform account ID and external ID for manual setup."
              />

              <CopyValueRow label="External ID" value={tenant?.external_id} />
              <CopyValueRow label="Platform account ID" value={saas_account_id} />

              {read_role_launch_stack_url ? (
                <>
                  <Input
                    id="connect-read-stack-name"
                    label="ReadRole stack name"
                    type="text"
                    value={readStackNameValue}
                    onChange={(event) => setReadStackName(event.target.value)}
                    placeholder={read_role_default_stack_name}
                    className="font-mono"
                    disabled={isSubmitting}
                  />

                  <div className={remediationInsetClass('accent', 'flex flex-wrap items-center gap-3 p-5')}>
                    <ButtonLink
                      href={buildReadRoleLaunchStackUrl(readStackNameValue) ?? read_role_launch_stack_url}
                      target="_blank"
                    >
                      Deploy ReadRole in AWS
                    </ButtonLink>
                    <button
                      type="button"
                      className="text-sm font-medium text-accent transition hover:text-accent-hover"
                      onClick={() => stepBRef.current?.scrollIntoView({ behavior: 'smooth' })}
                    >
                      I already deployed it
                    </button>
                  </div>

                  {read_role_template_url ? (
                    <p className="text-xs text-text/62" data-testid="template-version">
                      Template version: {read_role_template_url.match(/\/(v?\d+\.\d+\.\d+)\.yaml$/)?.[1] ?? '—'}
                    </p>
                  ) : null}
                </>
              ) : (
                <RemediationCallout
                  tone="warning"
                  description="Launch-stack automation is not configured in this environment. Use the copied platform account ID and external ID with your administrator-provided template URL."
                />
              )}
            </div>
          </RemediationPanel>

          <div ref={stepBRef}>
            <RemediationPanel className="p-6">
              <div className="space-y-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Step B</p>
                  <h3 className="mt-3 text-lg font-semibold text-text">Save the ReadRole ARN and monitored regions</h3>
                </div>
                <Badge variant="info">Required</Badge>
              </div>

              {isSubmitting ? (
                <RemediationCallout
                  tone="info"
                  description={isReconnect ? 'Saving the updated account connection...' : 'Saving the new account connection...'}
                />
              ) : error ? (
                <RemediationCallout tone="danger" description={error} />
              ) : isReconnect ? (
                <RemediationCallout
                  tone="info"
                  description="Update the ReadRole ARN or monitored regions if needed, then save the existing account connection."
                />
              ) : (
                <RemediationCallout
                  tone="default"
                  description="Paste the ReadRole ARN from CloudFormation outputs. Onboarding final checks remain the source of truth for readiness."
                />
              )}

              <div className="grid gap-4">
                <Input
                  label="ReadRole ARN"
                  placeholder="arn:aws:iam::123456789012:role/SecurityAutopilotReadRole"
                  value={roleArn}
                  onChange={(event) => handleRoleArnChange(event.target.value)}
                  required
                  helperText="CloudFormation output: ReadRoleArn"
                  disabled={isSubmitting}
                />

                <div className={remediationInsetClass('default', 'space-y-4 p-5')}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className={REMEDIATION_EYEBROW_CLASS}>Monitored regions</p>
                      <p className="mt-2 text-sm text-text/72">
                        Select between 1 and {MAX_REGIONS} regions. Security Hub findings will be pulled from each selected region.
                      </p>
                    </div>
                    {effectiveAccountId ? (
                      <Badge variant="info">{effectiveAccountId}</Badge>
                    ) : (
                      <Badge variant="default">Account ID pending</Badge>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {regions.map((region) => {
                      const label = AWS_REGIONS.find((entry) => entry.value === region)?.label ?? region;
                      return (
                        <span
                          key={region}
                          className={remediationInsetClass('default', 'inline-flex items-center gap-2 px-3 py-2 text-sm')}
                        >
                          {label}
                          <button
                            type="button"
                            onClick={() => removeRegion(region)}
                            disabled={isSubmitting || regions.length <= 1}
                            className="text-muted transition hover:text-text disabled:opacity-50"
                            aria-label={`Remove ${region}`}
                          >
                            ×
                          </button>
                        </span>
                      );
                    })}
                  </div>

                  {regions.length < MAX_REGIONS ? (
                    <SelectDropdown
                      value={regionToAdd}
                      onValueChange={(value) => {
                        if (value) addRegion(value);
                        setRegionToAdd('');
                      }}
                      options={availableToAdd.map((region) => ({ value: region.value, label: region.label }))}
                      placeholder="Add a region..."
                      disabled={isSubmitting || availableToAdd.length === 0}
                      aria-label="Add region"
                      triggerClassName="w-full min-w-0"
                      contentClassName="w-[min(420px,80vw)]"
                    />
                  ) : null}
                </div>
              </div>

                <div className="flex flex-wrap justify-end gap-3 border-t border-border/35 pt-5">
                  <Button type="button" variant="secondary" onClick={handleClose} disabled={isSubmitting}>
                    Cancel
                  </Button>
                  <Button type="submit" isLoading={isSubmitting} disabled={!canSubmit}>
                    {isSubmitting
                      ? isReconnect
                        ? 'Saving...'
                        : 'Saving...'
                      : isReconnect
                        ? 'Save account connection'
                        : 'Connect account'}
                  </Button>
                </div>
              </div>
            </RemediationPanel>
          </div>
        </div>
      </form>
    </Modal>
  );
}
