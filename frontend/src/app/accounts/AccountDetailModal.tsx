'use client';

import { useState } from 'react';

import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { Badge, getStatusBadgeVariant } from '@/components/ui/Badge';
import {
  REMEDIATION_EYEBROW_CLASS,
  RemediationCallout,
  RemediationPanel,
  SectionTitleExplainer,
  remediationInsetClass,
} from '@/components/ui/remediation-surface';
import {
  AwsAccount,
  deleteAccount,
  getErrorMessage,
  updateAccount,
} from '@/lib/api';
import { AccountIngestActions } from './AccountIngestActions';
import { AccountReconciliationPanel } from './AccountReconciliationPanel';
import { AccountServiceStatusCheck } from './AccountServiceStatusCheck';
import { formatUtcDateTime } from './date-format';

function formatLastValidated(dateString: string | null): string {
  return formatUtcDateTime(dateString);
}

interface AccountDetailModalProps {
  account: AwsAccount | null;
  isOpen: boolean;
  onClose: () => void;
  tenantId?: string | null;
  onUpdate: () => void;
  onReconnect?: (account: AwsAccount) => void;
}

export function AccountDetailModal({
  account,
  isOpen,
  onClose,
  tenantId,
  onUpdate,
  onReconnect,
}: AccountDetailModalProps) {
  const [isStopping, setIsStopping] = useState(false);
  const [showRemoveConfirm, setShowRemoveConfirm] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (!account) return null;

  const accountId = account.account_id;
  const isDisabled = account.status.toLowerCase() === 'disabled';

  async function handleStopOrResume() {
    setActionError(null);
    setIsStopping(true);
    try {
      await updateAccount(
        accountId,
        { status: isDisabled ? 'validated' : 'disabled' },
        tenantId ?? undefined,
      );
      onUpdate();
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setIsStopping(false);
    }
  }

  async function handleRemove() {
    setActionError(null);
    setIsRemoving(true);
    try {
      await deleteAccount(accountId, tenantId ?? undefined);
      onClose();
      onUpdate();
    } catch (err) {
      setActionError(getErrorMessage(err));
    } finally {
      setIsRemoving(false);
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Account ${account.account_id}`}
      size="xl"
      variant="dashboard"
      headerContent={<Badge variant={getStatusBadgeVariant(account.status)}>{account.status}</Badge>}
    >
      <div className="space-y-6">
        <RemediationPanel className="p-6" tone="accent">
          <div className="grid gap-4 lg:grid-cols-4">
            <div className={remediationInsetClass('default', 'p-4')}>
              <div className="flex flex-wrap items-center gap-2">
                <p className={REMEDIATION_EYEBROW_CLASS}>Account ID</p>
                <SectionTitleExplainer conceptId="account_id" context="accounts" label="Account ID" />
              </div>
              <p className="mt-3 font-mono text-sm font-semibold text-text">{account.account_id}</p>
            </div>
            <div className={remediationInsetClass('default', 'p-4')}>
              <div className="flex flex-wrap items-center gap-2">
                <p className={REMEDIATION_EYEBROW_CLASS}>Regions</p>
                <SectionTitleExplainer conceptId="monitored_regions" context="accounts" label="Regions" />
              </div>
              <p className="mt-3 text-sm text-text">{account.regions.join(', ')}</p>
            </div>
            <div className={remediationInsetClass('default', 'p-4')}>
              <div className="flex flex-wrap items-center gap-2">
                <p className={REMEDIATION_EYEBROW_CLASS}>Last validated</p>
                <SectionTitleExplainer conceptId="lifecycle_timestamps" context="accounts" label="Last validated" />
              </div>
              <p className="mt-3 text-sm text-text">{formatLastValidated(account.last_validated_at)}</p>
            </div>
            <div className={remediationInsetClass('default', 'p-4')}>
              <div className="flex flex-wrap items-center gap-2">
                <p className={REMEDIATION_EYEBROW_CLASS}>Connection status</p>
                <SectionTitleExplainer conceptId="connection_status" context="accounts" label="Connection status" />
              </div>
              <p className="mt-3 text-sm text-text">{isDisabled ? 'Monitoring paused' : 'ReadRole connected'}</p>
            </div>
          </div>

          <div className="mt-4">
            <div className={remediationInsetClass('default', 'p-4')}>
              <p className={REMEDIATION_EYEBROW_CLASS}>Read role ARN</p>
              <p className="mt-3 break-all font-mono text-xs text-text">{account.role_read_arn}</p>
            </div>
          </div>
        </RemediationPanel>

        <RemediationCallout
          tone="info"
          title="Connection validation"
          description="ReadRole validation and required service checks run through onboarding so the validation story stays explicit and auditable."
        >
          <div className="flex flex-wrap items-center gap-3">
            <ButtonLink href="/onboarding" variant="secondary" size="sm">
              Open onboarding checks
            </ButtonLink>
            {onReconnect && account.status !== 'validated' ? (
              <Button variant="secondary" size="sm" onClick={() => onReconnect(account)}>
                Reconnect account
              </Button>
            ) : null}
            <p className="text-sm text-text/70">Use reconnect when ARNs or monitored regions need to be revalidated.</p>
          </div>
        </RemediationCallout>

        <RemediationPanel className="p-6" tone="accent">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className={REMEDIATION_EYEBROW_CLASS}>Refresh findings</p>
              <h3 className="mt-3 text-lg font-semibold text-text">Queue source refreshes from the same account workflow</h3>
            </div>
            {isDisabled ? <Badge variant="warning">Monitoring paused</Badge> : null}
          </div>
          {isDisabled ? (
            <RemediationCallout
              tone="warning"
              description="Monitoring is paused. Resume monitoring before you queue ingest for this account."
            />
          ) : null}
          <div className={isDisabled ? 'mt-4' : undefined}>
            <AccountIngestActions
              account={account}
              tenantId={tenantId ?? undefined}
              onUpdate={onUpdate}
              layout="modal"
            />
          </div>
        </RemediationPanel>

        <AccountServiceStatusCheck
          accountId={account.account_id}
          tenantId={tenantId ?? undefined}
          compact={false}
          autoCheck
        />

        <AccountReconciliationPanel
          account={account}
          tenantId={tenantId ?? undefined}
          onUpdate={onUpdate}
        />

        <RemediationPanel className="p-6" tone="warning">
          <div className="space-y-5">
            <div>
              <p className={REMEDIATION_EYEBROW_CLASS}>Manage account</p>
              <h3 className="mt-3 text-lg font-semibold text-text">Pause monitoring or remove the account</h3>
            </div>

            {actionError ? (
              <RemediationCallout tone="danger" description={actionError} />
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleStopOrResume}
                isLoading={isStopping}
              >
                {isStopping
                  ? isDisabled
                    ? 'Resuming...'
                    : 'Stopping...'
                  : isDisabled
                    ? 'Resume monitoring'
                    : 'Stop monitoring'}
              </Button>

              {!showRemoveConfirm ? (
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => setShowRemoveConfirm(true)}
                >
                  Remove account
                </Button>
              ) : (
                <div className="flex flex-wrap items-center gap-3">
                  <p className="text-sm text-text/74">
                    Removing the account only disconnects it from the platform. It does not delete the AWS account.
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setShowRemoveConfirm(false)}
                    disabled={isRemoving}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleRemove}
                    isLoading={isRemoving}
                  >
                    Confirm removal
                  </Button>
                </div>
              )}
            </div>
          </div>
        </RemediationPanel>
      </div>
    </Modal>
  );
}
