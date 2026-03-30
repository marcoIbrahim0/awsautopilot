'use client';

import { ButtonLink } from '@/components/ui/ButtonLink';
import { Badge, getStatusBadgeVariant } from '@/components/ui/Badge';
import { AwsAccount } from '@/lib/api';
import { AccountIngestActions } from './AccountIngestActions';
import { formatUtcDateTime } from './date-format';

interface AccountCardProps {
  account: AwsAccount;
  tenantId: string;
  onUpdate: () => void;
}

export function AccountCard({ account, tenantId, onUpdate }: AccountCardProps) {
  const formatDate = (dateString: string | null) => {
    return formatUtcDateTime(dateString);
  };

  return (
    <div className="bg-surface border border-accent/30 rounded-xl p-5 shadow-glow hover:border-accent/50 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-lg font-semibold text-text font-mono">
              {account.account_id}
            </h3>
            <Badge variant={getStatusBadgeVariant(account.status)}>
              {account.status}
            </Badge>
          </div>
          <p className="text-sm text-muted truncate max-w-md" title={account.role_read_arn}>
            {account.role_read_arn}
          </p>
        </div>

        {/* Cloud icon */}
        <div className="p-2 bg-accent/10 rounded-xl">
          <svg className="w-6 h-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
          </svg>
        </div>
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
        <div>
          <p className="text-muted mb-1">Regions</p>
          <div className="flex flex-wrap gap-1">
            {account.regions.map((region) => (
              <Badge key={region} variant="default">
                {region}
              </Badge>
            ))}
          </div>
        </div>
        <div>
          <p className="text-muted mb-1">Last Validated</p>
          <p className="text-text">{formatDate(account.last_validated_at)}</p>
        </div>
      </div>

      {/* Actions */}
      <div className="pt-4 border-t border-border space-y-4">
        <div className="flex gap-2">
          <ButtonLink href="/onboarding" variant="secondary" size="sm">
            Run onboarding checks
          </ButtonLink>
        </div>
        <div>
          <p className="text-sm text-muted mb-2">Refresh findings</p>
          <AccountIngestActions
            account={account}
            tenantId={tenantId}
            onUpdate={onUpdate}
            compact={false}
          />
        </div>
      </div>
    </div>
  );
}
