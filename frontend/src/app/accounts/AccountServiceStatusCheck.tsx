'use client';

import { ButtonLink } from '@/components/ui/ButtonLink';
import { RemediationCallout, SectionTitleExplainer, remediationInsetClass, REMEDIATION_EYEBROW_CLASS } from '@/components/ui/remediation-surface';

interface AccountServiceStatusCheckProps {
  accountId: string;
  tenantId?: string;
  compact?: boolean;
  autoCheck?: boolean;
}

export function AccountServiceStatusCheck({
  accountId,
  compact = false,
}: AccountServiceStatusCheckProps) {
  if (compact) {
    return (
      <p className="text-xs text-muted max-w-xs">
        Verification runs during onboarding only.
      </p>
    );
  }

  return (
    <RemediationCallout
      tone="info"
      title="Service verification"
      description="Onboarding owns required verification for Inspector, Security Hub, AWS Config, and control-plane forwarding. Access Analyzer remains optional."
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className={remediationInsetClass('default', 'w-fit px-4 py-3')}>
          <div className="flex flex-wrap items-center gap-2">
            <p className={REMEDIATION_EYEBROW_CLASS}>Account</p>
            <SectionTitleExplainer conceptId="account_id" context="accounts" label="Account" />
          </div>
          <p className="mt-2 font-mono text-sm text-text">{accountId}</p>
        </div>
        <ButtonLink href="/onboarding" variant="secondary" size="sm">
          Open onboarding checks
        </ButtonLink>
      </div>
    </RemediationCallout>
  );
}
