'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Badge, getActionStatusBadgeVariant } from '@/components/ui/Badge';
import { ActionListItem } from '@/lib/api';
import { CONTROL_FAMILY_TOOLTIP, getActionControlSummary } from '@/lib/controlFamily';

interface ActionCardProps {
  action: ActionListItem;
  isHighlighted?: boolean;
  onGenerateBatchPr?: (action: ActionListItem) => void;
  batchGenerating?: boolean;
}

function titleCaseToken(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatMatrixLabel(action: ActionListItem): string {
  const risk = titleCaseToken(action.business_impact.technical_risk_tier);
  const criticality = titleCaseToken(action.business_impact.criticality.tier);
  return `${risk} x ${criticality}`;
}

export function ActionCard({
  action,
  isHighlighted = false,
  onGenerateBatchPr,
  batchGenerating = false,
}: ActionCardProps) {
  const router = useRouter();
  const isPrOnlyBatch = action.is_batch && action.action_type === 'pr_only';
  const formatDate = (dateString: string | null) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString();
  };

  const formatExpiryDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const totalFindings = action.batch_finding_count ?? action.finding_count;
  const actionCount = action.batch_action_count ?? 1;
  const emphasisClass = isHighlighted ? 'ring-1 ring-accent/40' : '';
  const sharedCardClass =
    `block bg-surface border border-accent/30 rounded-xl p-6 shadow-glow transition-all duration-200 ${emphasisClass}`;
  const interactiveCardClass = `${sharedCardClass} hover:border-accent/50 hover:shadow-glow`;
  const batchGroupHref = `/actions/group?group_id=${encodeURIComponent(action.id)}&action_type=${encodeURIComponent(action.action_type)}&account_id=${encodeURIComponent(action.account_id)}&status=${encodeURIComponent(action.status)}${action.region ? `&region=${encodeURIComponent(action.region)}` : ''}`;
  const controlSummary = getActionControlSummary(action.control_family, action.control_id);

  const cardContent = (
    <>
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-text font-medium truncate mb-2" title={action.title}>
            {action.title}
          </h3>
          {controlSummary && (
            <p
              className="text-xs text-accent font-mono"
              title={action.control_family?.is_mapped ? CONTROL_FAMILY_TOOLTIP : undefined}
            >
              {controlSummary}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          <Badge variant={getActionStatusBadgeVariant(action.status)}>
            {action.status.replace('_', ' ')}
          </Badge>
          <Badge variant="info">Risk {action.score}</Badge>
          <Badge variant="warning">{formatMatrixLabel(action)}</Badge>
          {action.is_batch && (
            <Badge variant="default">
              {actionCount} action{actionCount !== 1 ? 's' : ''}
            </Badge>
          )}
          {!action.is_batch && action.exception_id && action.exception_expires_at && (
            <Badge
              variant="warning"
              title={`Suppressed until ${formatExpiryDate(action.exception_expires_at)}`}
            >
              <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
              Until {formatExpiryDate(action.exception_expires_at)}
            </Badge>
          )}
          {!action.is_batch && action.exception_expired && (
            <Badge variant="danger" title="Exception has expired">
              <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              Expired
            </Badge>
          )}
        </div>
      </div>

      {action.resource_id && !action.is_batch && (
        <div className="mb-4">
          <p className="text-sm text-muted truncate font-mono" title={action.resource_id}>
            {action.resource_id}
          </p>
          <p className="mt-2 text-xs text-muted">
            {action.business_impact.summary}
          </p>
        </div>
      )}

      {action.is_batch && (
        <div className="mb-4 space-y-3">
          <p className="text-sm text-muted">
            Execution group summary. Click to open group details and review all included actions.
          </p>
          {isPrOnlyBatch && (
            <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2">
              <p className="text-xs font-medium text-warning">PR bundle not available</p>
              <p className="mt-1 text-xs text-warning/90">
                This execution group is pr_only (unmapped control). Remediate manually in AWS, then recompute actions.
              </p>
            </div>
          )}
          {onGenerateBatchPr && (
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                if (isPrOnlyBatch) return;
                onGenerateBatchPr(action);
              }}
              disabled={batchGenerating || isPrOnlyBatch}
              className="inline-flex items-center rounded-lg border border-accent/40 px-3 py-1.5 text-xs font-medium text-accent hover:bg-accent/10 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {batchGenerating ? 'Generating…' : 'Generate PR bundles for group'}
            </button>
          )}
        </div>
      )}

      <div className="flex items-center gap-5 pt-4 border-t border-border text-xs text-muted">
        {!action.is_batch && (
          <div className="flex items-center gap-1.5">
            <Link
              href={`/attack-paths?action_id=${encodeURIComponent(action.id)}`}
              className="font-semibold uppercase tracking-[0.14em] text-accent hover:text-text"
              onClick={(event) => event.stopPropagation()}
            >
              Attack path
            </Link>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
          </svg>
          <span className="font-mono">{action.account_id}</span>
        </div>
        {action.region && (
          <div className="flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
            </svg>
            <span>{action.region}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5">
          <span className="text-accent font-medium">{totalFindings}</span>
          <span>finding{totalFindings !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-1.5 ml-auto">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{formatDate(action.updated_at)}</span>
        </div>
      </div>
    </>
  );

  if (action.is_batch) {
    return (
      <div
        role="link"
        tabIndex={0}
        onClick={() => router.push(batchGroupHref)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            router.push(batchGroupHref);
          }
        }}
        className={`${sharedCardClass} cursor-pointer hover:border-accent/50 hover:shadow-glow focus:outline-none focus:ring-2 focus:ring-accent/30`}
      >
        {cardContent}
      </div>
    );
  }

  return (
    <Link
      href={`/actions/${action.id}`}
      className={interactiveCardClass}
    >
      {cardContent}
    </Link>
  );
}
