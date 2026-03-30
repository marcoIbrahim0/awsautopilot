'use client';

import { Button } from '@/components/ui/Button';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { AwsAccount } from '@/lib/api';
import { AccountIngestActions } from './AccountIngestActions';

interface AccountRowActionsProps {
  account: AwsAccount;
  tenantId?: string;
  onUpdate: () => void;
  onOpenDetails?: () => void;
}

export function AccountRowActions({
  account,
  tenantId,
  onUpdate,
  onOpenDetails,
}: AccountRowActionsProps) {
  return (
    <div className="flex min-w-[16rem] flex-col gap-2">
      <div className="flex flex-wrap items-center justify-end gap-2">
        {onOpenDetails ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={onOpenDetails}
            className="shrink-0"
          >
            Open details
          </Button>
        ) : null}
        <ButtonLink href="/onboarding" variant="secondary" size="sm" className="shrink-0">
          Onboarding checks
        </ButtonLink>
        <div className="flex items-center gap-2 shrink-0">
          <AccountIngestActions
            account={account}
            tenantId={tenantId}
            onUpdate={onUpdate}
            compact
          />
        </div>
      </div>
      <span className="block text-right text-xs text-muted/80">
        Account-read checks run during onboarding only.
      </span>
    </div>
  );
}
