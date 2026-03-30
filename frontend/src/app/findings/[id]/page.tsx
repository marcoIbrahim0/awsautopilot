'use client';

import { useCallback, useEffect, useState, use } from 'react';
import Link from 'next/link';
import { NeedHelpLink } from '@/components/help/NeedHelpLink';
import { AppShell } from '@/components/layout';
import { Button } from '@/components/ui/Button';
import { Badge, getSeverityBadgeVariant, getStatusBadgeVariant } from '@/components/ui/Badge';
import { PendingConfirmationNote } from '@/components/ui/PendingConfirmationNote';
import { RemediationStateBadge } from '@/components/ui/RemediationStateBadge';
import { TenantIdForm } from '@/components/TenantIdForm';
import { CreateExceptionModal } from '@/components/CreateExceptionModal';
import { ActionDetailModal } from '@/components/ActionDetailModal';
import { getFinding, Finding, getErrorMessage } from '@/lib/api';
import {
  getNoRemediationActionPresentationForReason,
  getRemediationStatePresentation,
} from '@/lib/remediationState';
import {
  CONTROL_FAMILY_TOOLTIP,
  getFindingControlLabel,
  getFindingControlSecondaryLabel,
} from '@/lib/controlFamily';
import { useTenantId } from '@/lib/tenant';
import { useAuth } from '@/contexts/AuthContext';
import { getSourceLabel } from '@/lib/source';

export const runtime = 'nodejs';

interface FindingDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function FindingDetailPage({ params }: FindingDetailPageProps) {
  const { id } = use(params);
  const { tenantId, setTenantId } = useTenantId();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [finding, setFinding] = useState<Finding | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showExceptionModal, setShowExceptionModal] = useState(false);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);

  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const showContent = isAuthenticated || tenantId;
  const effectiveStatus = (finding?.effective_status || finding?.status || '').toUpperCase();
  const isMetadataOnly = finding?.remediation_action_group_status_bucket === 'run_finished_metadata_only';
  const showPendingConfirmation = Boolean(
    effectiveStatus !== 'RESOLVED' &&
    !isMetadataOnly &&
    finding?.status_message &&
    finding?.status_severity
  );
  const pendingConfirmationMessage = showPendingConfirmation ? finding?.status_message ?? null : null;
  const pendingConfirmationSeverity = showPendingConfirmation ? finding?.status_severity ?? null : null;

  const fetchFinding = useCallback(() => {
    if (!isAuthenticated && !tenantId) {
      queueMicrotask(() => setIsLoading(false));
      return;
    }

    queueMicrotask(() => {
      setIsLoading(true);
      setError(null);
    });

    getFinding(id, effectiveTenantId)
      .then(setFinding)
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setIsLoading(false));
  }, [effectiveTenantId, id, isAuthenticated, tenantId]);

  useEffect(() => {
    fetchFinding();
  }, [fetchFinding]);

  const handleCopyId = async () => {
    if (!finding) return;
    await navigator.clipboard.writeText(finding.finding_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleString();
  };

  const shadowVariant = (normalized?: string | null) => {
    const s = (normalized || '').toUpperCase();
    if (s === 'RESOLVED') return 'success';
    if (s === 'OPEN') return 'warning';
    return 'default';
  };

  const fixHref = finding?.remediation_action_id ? `/actions/${finding.remediation_action_id}` : null;
  const groupHref = finding?.remediation_action_group_id
    ? `/actions/group?group_id=${encodeURIComponent(finding.remediation_action_group_id)}`
    : finding?.remediation_action_type &&
    finding.remediation_action_account_id &&
    finding.remediation_action_status
      ? `/actions/group?action_type=${encodeURIComponent(finding.remediation_action_type)}&account_id=${encodeURIComponent(
          finding.remediation_action_account_id
        )}&status=${encodeURIComponent(finding.remediation_action_status)}${
          finding.remediation_action_region ? `&region=${encodeURIComponent(finding.remediation_action_region)}` : ''
        }`
      : null;
  const remediationState = fixHref
    ? getRemediationStatePresentation(
        finding?.remediation_action_group_status_bucket,
        true,
        finding?.remediation_action_status,
        finding?.status_message
      )
    : getNoRemediationActionPresentationForReason(
        finding?.remediation_visibility_reason,
        finding?.remediation_scope_message
      );
  const fixUnavailableReason = remediationState?.description || 'No remediation workflow is available for this finding yet.';
  const groupUnavailableReason = 'This finding is not yet included in a PR bundle group.';
  const controlLabel = getFindingControlLabel(finding?.control_family, finding?.control_id);
  const controlSecondaryLabel = getFindingControlSecondaryLabel(finding?.control_family, finding?.control_id);

  return (
    <AppShell title="Finding Detail">
      <div className="max-w-4xl mx-auto w-full">
        {!showContent && !authLoading && isAuthenticated && (
          <TenantIdForm onSave={setTenantId} />
        )}

        {/* Back link */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <Link
            href="/findings"
            className="inline-flex items-center gap-2 text-muted hover:text-text transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
            Back to Findings
          </Link>
          <NeedHelpLink
            from={`/findings/${id}`}
            accountId={finding?.account_id ?? null}
            findingId={id}
            label="Need help with this finding?"
          />
        </div>

        {/* Loading state */}
        {showContent && isLoading && (
          <div className="space-y-4">
            <div className="nm-neu-lg border-none rounded-[2rem] p-8 animate-pulse">
              <div className="h-8 bg-border rounded w-3/4 mb-4" />
              <div className="flex gap-2 mb-4">
                <div className="h-6 bg-border rounded w-20" />
                <div className="h-6 bg-border rounded w-20" />
                <div className="h-6 bg-border rounded w-32" />
              </div>
              <div className="h-4 bg-border rounded w-full mb-2" />
              <div className="h-4 bg-border rounded w-2/3" />
            </div>
          </div>
        )}

        {/* Error state (API errors only) */}
        {showContent && error && (
          <div className="p-4 nm-neu-flat border border-danger/30 bg-danger/10 rounded-2xl">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 text-danger mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <div>
                <p className="text-sm font-medium text-danger">Failed to load finding</p>
                <p className="text-sm text-danger/80">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Finding content */}
        {showContent && finding && (
          <div className="space-y-8">
            {/* Hero card */}
            <div className="nm-neu-lg border-none rounded-[2rem] p-10">
              {/* Title */}
              <h1 className="text-2xl font-bold text-text mb-6">
                {finding.title}
              </h1>

              {/* Badges row */}
              <div className="flex flex-wrap items-center gap-3 mb-8">
                {finding.source && (
                  <Badge variant="default" className="nm-neu-flat border-none" title={`Source: ${getSourceLabel(finding.source)}`}>
                    {getSourceLabel(finding.source)}
                  </Badge>
                )}
                <Badge variant={getSeverityBadgeVariant(finding.severity_label)} className="nm-neu-flat border-none px-4">
                  {finding.severity_label}
                </Badge>
                <Badge variant={getStatusBadgeVariant(effectiveStatus)} className="nm-neu-flat border-none">
                  {effectiveStatus || finding.status}
                </Badge>
                {controlLabel && (
                  <Badge variant="info" className="nm-neu-flat border-none px-3">{controlLabel}</Badge>
                )}
                <Badge variant="default" className="nm-neu-flat border-none">{finding.account_id}</Badge>
                <Badge variant="default" className="nm-neu-flat border-none">{finding.region}</Badge>
              </div>

                <div className="flex flex-wrap items-start gap-3 mb-5">
                <div className="flex flex-col items-start gap-1">
                  {remediationState && (
                    <RemediationStateBadge presentation={remediationState} />
                  )}
                  {fixHref ? (
                    <Button size="sm" variant="primary" onClick={() => {
                      if (finding?.remediation_action_id) {
                        setSelectedActionId(finding.remediation_action_id);
                      }
                    }}>
                      {finding?.remediation_action_type === 'pr_only' ? 'Generate PR Bundle' : 'Fix this finding'}
                    </Button>
                  ) : (
                    <span title={fixUnavailableReason}>
                      <Button size="sm" variant="primary" disabled>
                        Fix this finding
                      </Button>
                    </span>
                  )}
                  {!fixHref && (
                    <p className="text-xs text-muted max-w-sm">
                      {remediationState?.description || 'No remediation action available yet.'}{` `}
                      <Link href="/settings" className="text-accent hover:underline">
                        Open settings
                      </Link>
                    </p>
                  )}
                </div>
                {groupHref ? (
                  <Link href={groupHref}>
                    <Button size="sm" variant="secondary">
                      View PR bundle group
                    </Button>
                  </Link>
                ) : (
                  <span title={groupUnavailableReason}>
                    <Button size="sm" variant="secondary" disabled>
                      View PR bundle group
                    </Button>
                  </span>
                )}
              </div>
              {showPendingConfirmation && pendingConfirmationMessage && pendingConfirmationSeverity && (
                  <div className="mb-5">
                    <PendingConfirmationNote
                      message={pendingConfirmationMessage}
                      severity={pendingConfirmationSeverity}
                    />
                  </div>
                )}

              {/* Step 6.4: Exception status */}
              {finding.exception_id && finding.exception_expires_at && (
                <div className="p-4 bg-accent/10 border border-accent/20 rounded-xl mb-5">
                  <div className="flex items-start gap-2">
                    <svg className="w-5 h-5 text-accent mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                    </svg>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-text">
                        This finding is suppressed until {formatDate(finding.exception_expires_at)}
                      </p>
                      <p className="text-xs text-muted mt-1">
                        An exception has been created for this finding.
                      </p>
                    </div>
                  </div>
                </div>
              )}
              {finding.exception_expired && (
                <div className="p-4 bg-danger/10 border border-danger/20 rounded-xl mb-5">
                  <div className="flex items-start gap-2">
                    <svg className="w-5 h-5 text-danger mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                    </svg>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-danger">
                        Exception has expired
                      </p>
                      <p className="text-xs text-muted mt-1">
                        The suppression for this finding has expired and it is now active again.
                      </p>
                    </div>
                  </div>
                </div>
              )}
              {!finding.exception_id && !finding.exception_expired && isAuthenticated && (
                <div className="mb-5">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setShowExceptionModal(true)}
                    leftIcon={
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                      </svg>
                    }
                  >
                    Suppress Finding
                  </Button>
                </div>
              )}

              {/* Description */}
              {finding.description && (
                <div className="nm-neu-pressed border-none rounded-2xl p-6 bg-transparent">
                  <p className="text-muted text-sm leading-relaxed font-medium">
                    {finding.description}
                  </p>
                </div>
              )}
            </div>

            {/* Details grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Resource info */}
              <div className="nm-neu-sm border-none rounded-2xl p-8">
                <h2 className="text-sm font-medium text-muted uppercase tracking-wide mb-3">
                  Resource
                </h2>
                <div className="space-y-3">
                  {finding.resource_id && (
                    <div>
                      <p className="text-xs text-muted mb-1">Resource ID</p>
                      <p className="text-sm text-text font-mono break-all">
                        {finding.resource_id}
                      </p>
                    </div>
                  )}
                  {finding.resource_type && (
                    <div>
                      <p className="text-xs text-muted mb-1">Resource Type</p>
                      <p className="text-sm text-text">{finding.resource_type}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Standard info */}
              <div className="nm-neu-sm border-none rounded-2xl p-8">
                <h2 className="text-sm font-medium text-muted uppercase tracking-wide mb-3">
                  Compliance
                </h2>
                <div className="space-y-3">
                  {finding.source && (
                    <div>
                      <p className="text-xs text-muted mb-1">Source</p>
                      <p className="text-sm text-text">{getSourceLabel(finding.source)}</p>
                    </div>
                  )}
                  {controlLabel && (
                    <div>
                      <p className="text-xs text-muted mb-1">Control ID</p>
                      <p className="text-sm text-text font-mono">{controlLabel}</p>
                      {controlSecondaryLabel && (
                        <p className="mt-1 text-xs text-muted" title={CONTROL_FAMILY_TOOLTIP}>
                          {controlSecondaryLabel}
                        </p>
                      )}
                    </div>
                  )}
                  {finding.standard_name && (
                    <div>
                      <p className="text-xs text-muted mb-1">Standard</p>
                      <p className="text-sm text-text">{finding.standard_name}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Timestamps */}
              <div className="nm-neu-sm border-none rounded-2xl p-8">
                <h2 className="text-sm font-medium text-muted uppercase tracking-wide mb-3">
                  Timeline
                </h2>
                <div className="space-y-3">
                  <div>
                    <p className="text-xs text-muted mb-1">First Observed</p>
                    <p className="text-sm text-text">{formatDate(finding.first_observed_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted mb-1">Last Observed</p>
                    <p className="text-sm text-text">{formatDate(finding.last_observed_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted mb-1">Last Updated</p>
                    <p className="text-sm text-text">{formatDate(finding.updated_at)}</p>
                  </div>
                </div>
              </div>

              {/* Control-plane shadow overlay */}
              {finding.shadow && (
                <div className="nm-neu-sm border-none rounded-2xl p-8">
                  <h2 className="text-sm font-medium text-muted uppercase tracking-wide mb-3">
                    Control Plane
                  </h2>
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-muted mb-1">Shadow Status</p>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={shadowVariant(finding.shadow.status_normalized)}>
                          {finding.shadow.status_raw}
                        </Badge>
                        {finding.shadow.status_reason && (
                          <span className="text-xs text-muted">{finding.shadow.status_reason}</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-muted mb-1">Shadow Event Time</p>
                      <p className="text-sm text-text">{formatDate(finding.shadow.last_observed_event_time ?? null)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted mb-1">Shadow Evaluated At</p>
                      <p className="text-sm text-text">{formatDate(finding.shadow.last_evaluated_at ?? null)}</p>
                    </div>
                    {finding.shadow.fingerprint && (
                      <div>
                        <p className="text-xs text-muted mb-1">Fingerprint</p>
                        <p className="text-xs text-text font-mono break-all">{finding.shadow.fingerprint}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Finding ID */}
              <div className="nm-neu-sm border-none rounded-2xl p-8">
                <h2 className="text-sm font-medium text-muted uppercase tracking-wide mb-3">
                  Identifiers
                </h2>
                <div className="space-y-3">
                  <div>
                    <p className="text-xs text-muted mb-1">Finding ID</p>
                    <div className="flex items-center gap-2">
                      <p className="text-sm text-text font-mono truncate flex-1">
                        {finding.finding_id}
                      </p>
                      <button
                        onClick={handleCopyId}
                        className="p-1 text-muted hover:text-accent transition-colors"
                        title="Copy Finding ID"
                      >
                        {copied ? (
                          <svg className="w-4 h-4 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-muted mb-1">Internal ID</p>
                    <p className="text-sm text-text font-mono">{finding.id}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Raw JSON section */}
            <div className="nm-neu-lg border-none rounded-[2rem] overflow-hidden">
              <button
                onClick={() => setShowRawJson(!showRawJson)}
                className="w-full flex items-center justify-between p-8 text-left hover:bg-bg/40 transition-all"
              >
                <span className="text-sm font-bold text-text uppercase tracking-tight">
                  Raw Security Hub JSON
                </span>
                <svg
                  className={`w-6 h-6 text-muted transition-transform duration-300 ${showRawJson ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                </svg>
              </button>
              {showRawJson && finding.raw_json && (
                <div className="p-8 pt-0">
                  <pre className="nm-neu-pressed bg-transparent p-6 rounded-2xl overflow-x-auto text-xs text-muted font-mono scrollbar-thin scrollbar-thumb-border/20">
                    {JSON.stringify(finding.raw_json, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Exception modal */}
      {finding && (
        <CreateExceptionModal
          isOpen={showExceptionModal}
          onClose={() => setShowExceptionModal(false)}
          entityType="finding"
          entityId={finding.id}
          onSuccess={fetchFinding}
          tenantId={effectiveTenantId}
        />
      )}

      {/* Action detail drawer */}
      <ActionDetailModal
        actionId={selectedActionId}
        isOpen={!!selectedActionId}
        onClose={() => setSelectedActionId(null)}
      />
    </AppShell>
  );
}
