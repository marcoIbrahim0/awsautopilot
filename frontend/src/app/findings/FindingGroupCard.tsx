'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Badge, getSeverityBadgeVariant } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { PendingConfirmationNote } from '@/components/ui/PendingConfirmationNote';
import { RemediationStateBadge } from '@/components/ui/RemediationStateBadge';
import {
    applyFindingGroupAction,
    Finding,
    FindingGroup,
    FindingGroupActionResponse,
    FindingGroupActionType,
    FindingGroupsFilters,
    getErrorMessage,
    getFindings,
} from '@/lib/api';
import {
    getNoRemediationActionPresentationForReason,
    getRemediationStatePresentation,
} from '@/lib/remediationState';
import {
    CONTROL_FAMILY_TOOLTIP,
    getFindingControlLabel,
    getFindingControlSecondaryLabel,
} from '@/lib/controlFamily';
import { FindingCard } from './FindingCard';

// ---------------------------------------------------------------------------
// Severity pill
// ---------------------------------------------------------------------------

const SEVERITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFORMATIONAL'] as const;

function SeverityPills({ distribution }: { distribution: Record<string, number> }) {
    const pills = SEVERITY_ORDER.filter((s) => (distribution[s] ?? 0) > 0);
    if (pills.length === 0) return null;
    return (
        <div className="flex flex-wrap gap-1.5">
            {pills.map((sev) => (
                <Badge key={sev} variant={getSeverityBadgeVariant(sev)}>
                    {distribution[sev]} {sev.charAt(0) + sev.slice(1).toLowerCase()}
                </Badge>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Chip: small read-only label
// ---------------------------------------------------------------------------

function Chip({ children }: { children: React.ReactNode }) {
    return (
        <span className="inline-flex items-center px-2 py-0.5 text-xs rounded-lg bg-border/40 text-muted font-mono">
            {children}
        </span>
    );
}

function GroupActionButtons({
    disabled,
    onActionSelect,
}: {
    disabled: boolean;
    onActionSelect: (action: FindingGroupActionType) => void;
}) {
    const actions: Array<{ action: FindingGroupActionType; label: string; variant: 'secondary' | 'ghost' }> = [
        { action: 'suppress', label: 'Suppress Group', variant: 'secondary' },
        { action: 'acknowledge_risk', label: 'Acknowledge Risk', variant: 'ghost' },
        { action: 'false_positive', label: 'Mark False Positive', variant: 'ghost' },
    ];
    return actions.map(({ action, label, variant }) => (
        <Button key={action} size="sm" variant={variant} disabled={disabled} onClick={() => onActionSelect(action)}>
            {label}
        </Button>
    ));
}

// ---------------------------------------------------------------------------
// Expanded individual findings (B2)
// ---------------------------------------------------------------------------

function ExpandedFindings({
    group,
    effectiveTenantId,
    status,
}: {
    group: FindingGroup;
    effectiveTenantId?: string;
    status?: string;
}) {
    const [findings, setFindings] = useState<Finding[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const controlId = group.control_id || undefined;
    const resourceType = group.resource_type || undefined;
    const accountId = group.account_ids.length === 1 ? group.account_ids[0] : undefined;
    const region = group.regions.length === 1 ? group.regions[0] : undefined;

    useEffect(() => {
        let cancelled = false;
        queueMicrotask(() => {
            setIsLoading(true);
        });
        const filters: Record<string, string | number> = {
            limit: 50,
            offset: 0,
        };
        if (controlId) filters.control_id = controlId;
        if (resourceType) filters.resource_type = resourceType;
        if (accountId) filters.account_id = accountId;
        if (region) filters.region = region;
        if (status) filters.status = status;
        getFindings(
            filters,
            effectiveTenantId
        )
            .then((res) => {
                if (!cancelled) setFindings(res.items);
            })
            .catch(() => { })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });
        return () => { cancelled = true; };
    }, [accountId, controlId, effectiveTenantId, region, resourceType, status]);

    if (isLoading) {
        return (
            <div className="mt-4 space-y-3 animate-pulse">
                {[1, 2].map((i) => (
                    <div key={i} className="h-20 rounded-xl bg-border/30" />
                ))}
            </div>
        );
    }

    if (findings.length === 0) {
        return <p className="mt-4 text-sm text-muted">No individual findings found.</p>;
    }

    return (
        <div className="mt-4 space-y-3">
            {findings.map((f) => (
                <FindingCard key={f.id} finding={f} />
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// FindingGroupCard (B1 + B2 + B3 + B4 + B5)
// ---------------------------------------------------------------------------

interface FindingGroupCardProps {
    group: FindingGroup;
    effectiveTenantId?: string;
    onActionSelect?: (actionId: string) => void;
    groupActionFilters?: FindingGroupsFilters;
    onGroupActionComplete?: (result: FindingGroupActionResponse) => void;
    groupActionsEnabled?: boolean;
}

export function FindingGroupCard({
    group,
    effectiveTenantId,
    onActionSelect,
    groupActionFilters,
    onGroupActionComplete,
    groupActionsEnabled = true,
}: FindingGroupCardProps) {
    const router = useRouter();
    const [isExpanded, setIsExpanded] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [generateError, setGenerateError] = useState<string | null>(null);
    const [groupActionError, setGroupActionError] = useState<string | null>(null);
    const [isApplyingGroupAction, setIsApplyingGroupAction] = useState(false);
    const [showSharedWarning, setShowSharedWarning] = useState(false);

    const actionHref = group.remediation_action_id
        ? `/actions/${group.remediation_action_id}`
        : null;
    const actionGroupHref = group.remediation_action_group_id
        ? `/actions/group?group_id=${encodeURIComponent(group.remediation_action_group_id)}`
        : null;
    const isMetadataOnly = group.remediation_action_group_status_bucket === 'run_finished_metadata_only';
    const remediationState = actionHref
        ? getRemediationStatePresentation(
            group.remediation_action_group_status_bucket,
            true,
            group.remediation_action_status,
            group.status_message
        )
        : getNoRemediationActionPresentationForReason(
            group.remediation_visibility_reason,
            group.remediation_scope_message
        );

    const handleGeneratePr = useCallback(() => {
        if (!actionHref) return;
        // B5: if shared resource, show confirmation modal first
        if (group.is_shared_resource) {
            setShowSharedWarning(true);
            return;
        }
        proceedGeneratePr();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [actionHref, group.is_shared_resource]);

    const proceedGeneratePr = useCallback(() => {
        setShowSharedWarning(false);
        setGenerateError(null);
        if (actionHref && group.remediation_action_id) {
            if (onActionSelect) {
                onActionSelect(group.remediation_action_id);
            } else {
                window.location.href = actionHref;
            }
        } else {
            setGenerateError('No remediation action available for this group.');
        }
    }, [actionHref, group.remediation_action_id, onActionSelect]);

    // Resource type display
    const resourceLabel = group.resource_type
        ? group.resource_type.replace('AWS::', '').replace('::', ' › ')
        : null;

    // Action availability
    const normalizedActionStatus = (group.remediation_action_status || '').trim().toLowerCase();
    const actionStatusLabel = normalizedActionStatus && !['open', 'resolved'].includes(normalizedActionStatus)
        ? group.remediation_action_status?.replace(/_/g, ' ') ?? null
        : null;
    const controlLabel = getFindingControlLabel(group.control_family, group.control_id);
    const controlSecondaryLabel = getFindingControlSecondaryLabel(group.control_family, group.control_id);

    const isPendingOrResolved =
        normalizedActionStatus === 'open' ? false
            : !!normalizedActionStatus;

    const suppressHref = (() => {
        const scopedAccountId = group.account_ids.length === 1 ? group.account_ids[0] : undefined;
        const scopedRegion = group.regions.length === 1 ? group.regions[0] : undefined;
        const params = new URLSearchParams({
            group_action: 'suppress',
            group_key: group.group_key,
        });
        if (group.control_id) params.set('control_id', group.control_id);
        if (group.resource_type) params.set('resource_type', group.resource_type);
        if (scopedAccountId) params.set('account_id', scopedAccountId);
        if (scopedRegion) params.set('region', scopedRegion);
        if (groupActionFilters?.severity) params.set('severity', groupActionFilters.severity);
        if (groupActionFilters?.source) params.set('source', groupActionFilters.source);
        if (groupActionFilters?.status) params.set('status', groupActionFilters.status);
        if (groupActionFilters?.resource_id) params.set('resource_id', groupActionFilters.resource_id);
        return `/exceptions?${params.toString()}`;
    })();

    const handleGroupAction = useCallback(async (action: FindingGroupActionType) => {
        if (!groupActionsEnabled) return;
        if (action === 'suppress') {
            router.push(suppressHref);
            return;
        }
        setGroupActionError(null);
        setIsApplyingGroupAction(true);
        try {
            const result = await applyFindingGroupAction({
                action,
                group_key: group.group_key,
                account_id: groupActionFilters?.account_id,
                region: groupActionFilters?.region,
                severity: groupActionFilters?.severity,
                source: groupActionFilters?.source,
                status: groupActionFilters?.status,
                control_id: groupActionFilters?.control_id,
                resource_id: groupActionFilters?.resource_id,
            });
            onGroupActionComplete?.(result);
        } catch (err) {
            setGroupActionError(getErrorMessage(err));
        } finally {
            setIsApplyingGroupAction(false);
        }
    }, [group.group_key, groupActionFilters, groupActionsEnabled, onGroupActionComplete, router, suppressHref]);

    return (
        <>
            <article className="nm-neu-sm rounded-[2.5rem] p-6 md:p-8 flex flex-col relative transition-all duration-300">

                {/* Header: title + shared-resource badge + expand toggle */}
                <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                            <h3 className="text-text font-semibold leading-snug">{group.rule_title}</h3>
                            {group.is_shared_resource && (
                                <Badge variant="warning" title="This resource is shared across multiple scope boundaries. Take care when remediating.">
                                    <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                                    </svg>
                                    Shared Resource
                                </Badge>
                            )}
                        </div>

                        {/* Control ID + resource type */}
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                            <span className="font-mono text-accent">{controlLabel || 'Unknown'}</span>
                            {resourceLabel && <span className="text-muted">·</span>}
                            {resourceLabel && <span className="text-muted">{resourceLabel}</span>}
                        </div>
                        {controlSecondaryLabel && (
                            <p className="mt-1 text-[11px] text-muted" title={CONTROL_FAMILY_TOOLTIP}>
                                {controlSecondaryLabel}
                            </p>
                        )}
                    </div>

                    {/* Expand / collapse */}
                    <button
                        onClick={() => setIsExpanded((v) => !v)}
                        className="shrink-0 flex items-center gap-1.5 text-xs text-muted hover:text-text transition-colors px-2 py-1 rounded-lg hover:bg-border/30"
                        aria-expanded={isExpanded}
                        aria-label={isExpanded ? 'Collapse findings' : 'Expand findings'}
                    >
                        <span>{isExpanded ? 'Collapse' : 'Expand'}</span>
                        <svg
                            className={`w-4 h-4 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                        </svg>
                    </button>
                </div>

                {/* Severity distribution pills */}
                <div className="mb-3">
                    <SeverityPills distribution={group.severity_distribution} />
                </div>

                {/* Finding count + accounts + regions */}
                <div className="flex flex-wrap items-center gap-2 mb-4 text-xs text-muted">
                    <span className="font-medium text-text">{group.finding_count} finding{group.finding_count !== 1 ? 's' : ''}</span>
                    {group.risk_acknowledged_count > 0 && (
                        <Badge
                            variant="default"
                            title="Manual risk acknowledgement is persisted for these findings."
                            className="font-medium"
                        >
                            {group.risk_acknowledged_count} acknowledged
                        </Badge>
                    )}
                    {resourceLabel && <span>across {resourceLabel}</span>}
                    <span className="text-border">·</span>
                    {group.account_ids.slice(0, 3).map((id) => (
                        <Chip key={id}>{id}</Chip>
                    ))}
                    {group.account_ids.length > 3 && (
                        <Chip>+{group.account_ids.length - 3} more</Chip>
                    )}
                    <span className="text-border">·</span>
                    {group.regions.slice(0, 3).map((r) => (
                        <Chip key={r}>{r}</Chip>
                    ))}
                    {group.regions.length > 3 && (
                        <Chip>+{group.regions.length - 3}</Chip>
                    )}
                </div>

                {remediationState && (
                    <div className="mb-4">
                        <RemediationStateBadge presentation={remediationState} />
                    </div>
                )}

                {/* Action row */}
                <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-border/60">
                    {actionHref ? (
                        isPendingOrResolved ? (
                            <>
                                <Button size="sm" variant="accent" onClick={() => {
                                    if (onActionSelect && group.remediation_action_id) {
                                        onActionSelect(group.remediation_action_id);
                                    } else {
                                        window.location.href = actionHref;
                                    }
                                }}>
                                    {actionStatusLabel ?? 'View action'}
                                </Button>
                                <Button size="sm" variant="secondary" onClick={() => {
                                    if (onActionSelect && group.remediation_action_id) {
                                        onActionSelect(group.remediation_action_id);
                                    } else {
                                        window.location.href = actionHref;
                                    }
                                }}>
                                    View details
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button
                                    size="sm"
                                    variant="primary"
                                    isLoading={isGenerating}
                                    onClick={handleGeneratePr}
                                    className="nm-neu-sm"
                                >
                                    {isGenerating ? 'Generating PR…' : 'Generate PR Bundle'}
                                </Button>
                                <Button size="sm" variant="secondary" onClick={() => {
                                    if (onActionSelect && group.remediation_action_id) {
                                        onActionSelect(group.remediation_action_id);
                                    } else {
                                        window.location.href = actionHref;
                                    }
                                }}>
                                    View details
                                </Button>
                            </>
                        )
                    ) : (
                        <div className="flex flex-col gap-1">
                            <span title={remediationState?.description || 'No remediation action is available for this group yet.'}>
                                <Button size="sm" variant="primary" disabled>
                                    Generate PR Bundle
                                </Button>
                            </span>
                            <p className="text-xs text-muted max-w-sm">
                                {remediationState?.description || 'No remediation action available yet.'}
                            </p>
                        </div>
                    )}
                    {actionGroupHref && (
                        <Link href={actionGroupHref}>
                            <Button size="sm" variant="secondary">
                                View PR bundle group
                            </Button>
                        </Link>
                    )}
                    <GroupActionButtons
                        onActionSelect={handleGroupAction}
                        disabled={isApplyingGroupAction || !groupActionsEnabled}
                    />

                    {generateError && (
                        <p className="text-xs text-danger ml-auto">{generateError}</p>
                    )}
                </div>

                {/* Inline error */}
                {generateError && !isGenerating && (
                    <p className="mt-2 text-xs text-danger">{generateError}</p>
                )}
                {groupActionError && (
                    <p className="mt-2 text-xs text-danger">{groupActionError}</p>
                )}
                {isApplyingGroupAction && (
                    <p className="mt-2 text-xs text-muted">Applying group action...</p>
                )}
                {!isMetadataOnly &&
                    group.status_message &&
                    group.status_severity && (
                        <div className="mt-4">
                            <PendingConfirmationNote
                                message={group.status_message}
                                severity={group.status_severity}
                                compact
                            />
                        </div>
                    )}

                {/* Expanded individual findings (B2) */}
                {isExpanded && (
                    <ExpandedFindings
                        group={group}
                        effectiveTenantId={effectiveTenantId}
                        status={groupActionFilters?.status}
                    />
                )}
            </article>

            {/* B5: Shared resource confirmation modal */}
            <Modal
                isOpen={showSharedWarning}
                onClose={() => setShowSharedWarning(false)}
                title="Shared Resource — Confirm Action"
                size="sm"
            >
                <div className="space-y-4">
                    <p className="text-sm text-text leading-relaxed">
                        <strong>Warning:</strong> This resource is shared across multiple scope boundaries.
                        Modifying it may affect applications or services outside your current project scope.
                    </p>
                    <p className="text-sm text-muted">Do you want to proceed with generating the PR?</p>
                    <div className="flex justify-end gap-3 pt-2">
                        <Button variant="secondary" size="sm" onClick={() => setShowSharedWarning(false)}>
                            Cancel
                        </Button>
                        <Button variant="danger" size="sm" onClick={proceedGeneratePr}>
                            Proceed anyway
                        </Button>
                    </div>
                </div>
            </Modal>
        </>
    );
}
