'use client';

import Link from 'next/link';
import { Badge, getSeverityBadgeVariant } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { PendingConfirmationNote } from '@/components/ui/PendingConfirmationNote';
import { RemediationStateBadge } from '@/components/ui/RemediationStateBadge';
import { Finding } from '@/lib/api';
import {
  getNoRemediationActionPresentationForReason,
  getRemediationStatePresentation,
} from '@/lib/remediationState';
import {
  CONTROL_FAMILY_TOOLTIP,
  getFindingControlLabel,
  getFindingControlSecondaryLabel,
} from '@/lib/controlFamily';
import { getSourceLabel, getSourceShortLabel } from '@/lib/source';

interface FindingCardProps {
  finding: Finding;
  isHighlighted?: boolean;
  onActionSelect?: (actionId: string) => void;
}

export function FindingCard({ finding, isHighlighted = false, onActionSelect }: FindingCardProps) {
  const effectiveStatus = (finding.effective_status || finding.status || '').toUpperCase();
  const groupStatusBucket = (finding.remediation_action_group_status_bucket || '').trim();
  const isMetadataOnly = groupStatusBucket === 'run_finished_metadata_only';
  const isSuppressed = effectiveStatus === 'SUPPRESSED' && !finding.exception_expired;
  const showPendingConfirmation = Boolean(
    effectiveStatus !== 'RESOLVED' &&
    !isMetadataOnly &&
    finding.status_message &&
    finding.status_severity
  );
  const pendingConfirmationMessage = showPendingConfirmation ? finding.status_message ?? null : null;
  const pendingConfirmationSeverity = showPendingConfirmation ? finding.status_severity ?? null : null;

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString();
  };

  const formatDateTime = (dateString: string | null | undefined) => {
    if (!dateString) return null;
    return new Date(dateString).toLocaleString();
  };

  const shadowVariant = (normalized?: string | null) => {
    const s = (normalized || '').toUpperCase();
    if (s === 'RESOLVED') return 'success';
    if (s === 'OPEN') return 'warning';
    return 'default';
  };

  const formatExpiryDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const fixHref = finding.remediation_action_id ? `/actions/${finding.remediation_action_id}` : null;
  const groupHref = finding.remediation_action_group_id
    ? `/actions/group?group_id=${encodeURIComponent(finding.remediation_action_group_id)}`
    : finding.remediation_action_type && finding.remediation_action_account_id && finding.remediation_action_status
      ? `/actions/group?action_type=${encodeURIComponent(finding.remediation_action_type)}&account_id=${encodeURIComponent(
        finding.remediation_action_account_id
      )}&status=${encodeURIComponent(finding.remediation_action_status)}${finding.remediation_action_region ? `&region=${encodeURIComponent(finding.remediation_action_region)}` : ''
      }`
      : null;

  const remediationState = fixHref
    ? getRemediationStatePresentation(
      groupStatusBucket,
      true,
      finding.remediation_action_status,
      finding.status_message
    )
    : getNoRemediationActionPresentationForReason(
      finding.remediation_visibility_reason,
      finding.remediation_scope_message
    );
  const fixUnavailableReason = remediationState?.description || 'No remediation workflow is available for this finding yet.';
  const groupUnavailableReason =
    remediationState?.description || 'This finding is not yet included in a PR bundle group.';
  const hasNonOpenRemediationAction =
    Boolean(finding.remediation_action_status) && finding.remediation_action_status !== 'open';
  const controlLabel = getFindingControlLabel(finding.control_family, finding.control_id);
  const controlSecondaryLabel = getFindingControlSecondaryLabel(finding.control_family, finding.control_id);
  const serviceLabel = finding.aws_service || finding.service || null;

  return (
    <article
      className={`nm-neu-sm rounded-2xl p-6 flex flex-col h-full relative group transition-all duration-300 hover:-translate-y-1 ${isHighlighted ? 'ring-2 ring-amber-500/40 ring-offset-2 ring-offset-transparent' : ''
        }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          <Link href={`/findings/${finding.id}`} className="group inline-flex max-w-full">
            <h3 className="text-text font-medium truncate mb-2 group-hover:text-accent transition-colors" title={finding.title}>
              {finding.title}
            </h3>
          </Link>
          {controlLabel && (
            <div className="space-y-1">
              <p className="text-xs text-accent font-mono">{controlLabel}</p>
              {controlSecondaryLabel && (
                <p className="text-[11px] text-muted" title={CONTROL_FAMILY_TOOLTIP}>
                  {controlSecondaryLabel}
                </p>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
          {serviceLabel && (
            <Badge
              variant="info"
              title={`AWS service: ${serviceLabel}`}
              className="font-mono text-xs"
            >
              {serviceLabel}
            </Badge>
          )}
          {finding.source && (
            <Badge
              variant="default"
              title={`Source: ${getSourceLabel(finding.source)}`}
              className="font-mono text-xs"
            >
              {getSourceShortLabel(finding.source)}
            </Badge>
          )}
          <Badge variant={getSeverityBadgeVariant(finding.severity_label)}>
            {finding.severity_label}
          </Badge>
          {finding.shadow && (
            <Badge
              variant={shadowVariant(finding.shadow.status_normalized)}
              title={`Control plane shadow: ${finding.shadow.status_raw}`}
              className="font-mono text-xs"
            >
              Shadow {finding.shadow.status_normalized}
            </Badge>
          )}
          {finding.risk_acknowledged && (
            <Badge
              variant="default"
              title={
                finding.risk_acknowledged_at
                  ? `Risk acknowledged on ${formatDateTime(finding.risk_acknowledged_at)}`
                  : 'Risk acknowledged'
              }
            >
              Risk acknowledged
            </Badge>
          )}
          {finding.exception_id && finding.exception_expires_at && (
            <Badge
              variant="warning"
              title={`Suppressed until ${formatExpiryDate(finding.exception_expires_at)}`}
            >
              <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
              Until {formatExpiryDate(finding.exception_expires_at)}
            </Badge>
          )}
          {!finding.exception_expires_at && isSuppressed && (
            <Badge variant="warning" title="Suppressed">
              Suppressed
            </Badge>
          )}
          {finding.exception_expired && (
            <Badge variant="danger" title="Exception has expired">
              <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              Expired
            </Badge>
          )}
        </div>
      </div>

      {/* Resource */}
      {finding.resource_id && (
        <div className="mb-4">
          <p className="text-sm text-muted mb-1">Resource</p>
          <p
            className="text-sm text-text truncate font-mono"
            title={finding.resource_id}
          >
            {finding.resource_id}
          </p>
        </div>
      )}

      {/* Footer details */}
      <div className="flex items-center gap-5 pt-4 border-t border-border text-xs text-muted">
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
          </svg>
          <span className="font-mono">{finding.account_id}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
          </svg>
          <span>{finding.region}</span>
        </div>
        <div className="flex items-center gap-1.5 ml-auto">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{formatDate(finding.updated_at)}</span>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-start gap-3">
        <div className="flex flex-col items-start gap-1">
          {remediationState && (
            <RemediationStateBadge presentation={remediationState} />
          )}
          {effectiveStatus === 'RESOLVED' ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-success/10 border border-success/30 text-success text-xs font-medium">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Resolved
            </div>
          ) : hasNonOpenRemediationAction && fixHref ? (
            <Button size="sm" variant="accent" onClick={() => {
              if (onActionSelect && finding.remediation_action_id) {
                onActionSelect(finding.remediation_action_id);
              } else {
                window.location.href = fixHref;
              }
            }}>
              View action
            </Button>
          ) : fixHref ? (
            <Button size="sm" variant="primary" className="nm-neu-sm" onClick={() => {
              if (onActionSelect && finding.remediation_action_id) {
                onActionSelect(finding.remediation_action_id);
              } else {
                window.location.href = fixHref;
              }
            }}>
              {finding.remediation_action_type === 'pr_only' ? 'Generate PR Bundle' : 'Fix this finding'}
            </Button>
          ) : (
            <span title={fixUnavailableReason}>
              <Button size="sm" variant="primary" disabled>
                Fix this finding
              </Button>
            </span>
          )}
          {!fixHref && (
            <p className="text-xs text-muted max-w-sm pt-1">
              {remediationState?.description || 'No remediation action available yet.'}{` `}
              <Link href={`/findings/${finding.id}`} className="text-accent hover:underline">
                Open finding details
              </Link>
            </p>
          )}
        </div>

        {effectiveStatus !== 'RESOLVED' && (
          groupHref ? (
            <Link href={groupHref}>
              <Button size="sm" variant="secondary">
                View PR bundle group
              </Button>
            </Link>
          ) : fixHref ? null : (
            <span title={groupUnavailableReason}>
              <Button size="sm" variant="secondary" disabled>
                View PR bundle group
              </Button>
            </span>
          )
        )}
      </div>
      {showPendingConfirmation && pendingConfirmationMessage && pendingConfirmationSeverity && (
        <div className="mt-4">
          <PendingConfirmationNote
            message={pendingConfirmationMessage}
            severity={pendingConfirmationSeverity}
            compact
          />
        </div>
      )}
    </article>
  );
}
