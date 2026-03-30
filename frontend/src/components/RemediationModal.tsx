'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { Modal } from '@/components/ui/Modal';
import { Button, buttonClassName } from '@/components/ui/Button';
import { MajorActionButton } from '@/components/ui/MajorActionButton';
import { AnimatedTooltip } from '@/components/ui/AnimatedTooltip';
import { Badge } from '@/components/ui/Badge';
import { ExplainerHint } from '@/components/ui/ExplainerHint';
import {
  REMEDIATION_EYEBROW_CLASS,
  RemediationCallout,
  RemediationPanel,
  RemediationPromptRow,
  RemediationSection,
  SectionTitleExplainer,
  RemediationStatCard,
  remediationCalloutClass,
  remediationInsetClass,
  remediationPanelClass,
} from '@/components/ui/remediation-surface';
import { RemediationRunProgress } from '@/components/RemediationRunProgress';
import {
  createRemediationRun,
  getErrorMessage,
  getRemediationOptions,
  getRemediationPreview,
  isApiError,
  listManualWorkflowEvidence,
  listRemediationRuns,
  ManualWorkflowEvidenceItem,
  RemediationOption,
  RemediationOptionsResponse,
  RemediationPreview,
  StrategyInputSchemaField,
  triggerActionReevaluation,
  uploadManualWorkflowEvidence,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  buildInitialStrategyInputValues,
  buildStrategyInputs,
  isFieldVisible,
  missingRequiredInputFields,
  parseBooleanInput,
  resolveRawFieldValue,
  resolveSafeDefaultValue,
  selectInitialStrategyForMode,
} from '@/lib/remediationAutoSelection';
import { buildGuidedReviewContent } from '@/lib/remediationGuidedReview';
import { getRemediationOutcomePresentation } from '@/lib/remediationOutcome';

const LEGACY_DIRECT_FIX_ACTION_TYPES = new Set([
  's3_block_public_access',
  'enable_security_hub',
  'enable_guardduty',
  'ebs_default_encryption',
]);
const ROOT_ACCOUNT_REQUIRED_ACTION_TYPE = 'iam_root_access_key_absent';
const ROOT_ACCOUNT_REQUIRED_RUNBOOK =
  'docs/prod-readiness/root-credentials-required-iam-root-access-key-absent.md';
const PR_ONLY_BUNDLE_UNSUPPORTED_MESSAGE =
  "This action is pr_only (unmapped control). Terraform/CloudFormation generation isn't supported yet. Remediate manually in AWS, then click Recompute actions.";
const BLAST_RADIUS_META: Record<
  NonNullable<RemediationOption['blast_radius']>,
  { label: string; badgeClass: string; tooltip: string }
> = {
  account: {
    label: 'Account-wide · Additive',
    badgeClass: 'border-success/30 bg-success/10 text-success',
    tooltip: 'Applies account-level settings and can affect multiple resources in this account.',
  },
  resource: {
    label: 'Resource-specific · Additive',
    badgeClass: 'border-warning/30 bg-warning/10 text-warning',
    tooltip: 'Targets one resource scope and adds guardrails without broad account-level changes.',
  },
  access_changing: {
    label: 'Access-changing · Review first',
    badgeClass: 'border-danger/30 bg-danger/10 text-danger',
    tooltip: 'Can change access paths or remove existing permissions. Verify operational access before apply.',
  },
};
const EXCEPTION_DURATION_OPTIONS = ['7', '14', '30', '90'] as const;
const PREVIEW_DEBOUNCE_MS = 250;
let detectedIpv4Promise: Promise<string | null> | null = null;

export interface ExceptionSelectionPayload {
  strategy: RemediationOption;
  strategyInputs: Record<string, unknown>;
}

interface RemediationBlastRadiusBadge {
  badgeClass: string;
  label: string;
  tooltip: string;
}

export interface RemediationWorkflowChromeState {
  blastRadius: RemediationBlastRadiusBadge | null;
  preventClose: boolean;
  showProgress: boolean;
  title: string;
}

interface RemediationModalProps {
  isOpen: boolean;
  onClose: () => void;
  actionId: string;
  actionTitle: string;
  actionType: string;
  accountId: string;
  region: string | null;
  mode: 'pr_only' | 'direct_fix';
  hasWriteRole: boolean;
  tenantId?: string;
  onChooseException?: (selection: ExceptionSelectionPayload) => void;
}

interface RemediationWorkflowContentProps
  extends Omit<RemediationModalProps, 'isOpen'> {
  isActive?: boolean;
  onChromeStateChange?: (state: RemediationWorkflowChromeState) => void;
}

function createDefaultChromeState(
  mode: RemediationModalProps['mode']
): RemediationWorkflowChromeState {
  return {
    blastRadius: null,
    preventClose: false,
    showProgress: false,
    title: mode === 'direct_fix' ? 'Apply Direct Fix' : 'Generate PR Bundle',
  };
}

function remediationOptionsCacheKey(actionId: string, mode: RemediationModalProps['mode']): string {
  return `${actionId}:${mode}`;
}

function loadDetectedPublicIpv4Cidr(): Promise<string | null> {
  if (!detectedIpv4Promise) {
    detectedIpv4Promise = fetch('https://api.ipify.org?format=json')
      .then(async (response) => {
        if (!response.ok) return null;
        const payload = (await response.json()) as { ip?: unknown };
        const ip = typeof payload.ip === 'string' ? payload.ip.trim() : null;
        return ip && isValidIpv4Address(ip) ? `${ip}/32` : null;
      })
      .catch(() => null);
  }
  return detectedIpv4Promise;
}

function renderBlastRadiusBadge(badge: RemediationBlastRadiusBadge | null) {
  if (!badge) return null;
  return (
    <span
      data-testid="blast-radius-badge"
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${badge.badgeClass}`}
      title={badge.tooltip}
    >
      {badge.label}
    </span>
  );
}

function parseNumberInput(rawValue: string): number | undefined {
  if (!rawValue.trim()) return undefined;
  const parsed = Number(rawValue);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function isValidIpv4Address(value: string): boolean {
  const octets = value.split('.');
  if (octets.length !== 4) return false;
  return octets.every((segment) => {
    if (!/^\d{1,3}$/.test(segment)) return false;
    const numeric = Number(segment);
    return numeric >= 0 && numeric <= 255;
  });
}


function isValidIpv4Cidr(value: string): boolean {
  const match = value.match(/^(\d{1,3}(?:\.\d{1,3}){3})\/(\d{1,2})$/);
  if (!match) return false;
  const octets = match[1].split('.').map((segment) => Number(segment));
  if (octets.some((segment) => Number.isNaN(segment) || segment < 0 || segment > 255)) return false;
  const prefix = Number(match[2]);
  return !Number.isNaN(prefix) && prefix >= 0 && prefix <= 32;
}

function isValidIpv6Cidr(value: string): boolean {
  const match = value.match(/^([0-9a-fA-F:]+)\/(\d{1,3})$/);
  if (!match || !match[1].includes(':')) return false;
  if (match[1].includes(':::')) return false;
  const prefix = Number(match[2]);
  if (Number.isNaN(prefix) || prefix < 0 || prefix > 128) return false;
  const parts = match[1].split('::');
  if (parts.length > 2) return false;
  const head = parts[0] ? parts[0].split(':') : [];
  const tail = parts[1] ? parts[1].split(':') : [];
  if (parts.length === 1 && head.length !== 8) return false;
  if (head.length + tail.length > 8) return false;
  return [...head, ...tail].every(
    (segment) => segment.length > 0 && segment.length <= 4 && /^[0-9a-fA-F]+$/.test(segment)
  );
}

function validateCidrInput(value: string): string | null {
  if (!value) return null;
  if (isValidIpv4Cidr(value) || isValidIpv6Cidr(value)) return null;
  return 'Enter a valid CIDR (for example 203.0.113.10/32).';
}

function remediationStrategyCardClass(selected: boolean, warning = false): string {
  return cn(
    remediationInsetClass(warning ? 'warning' : selected ? 'accent' : 'default'),
    'block w-full cursor-pointer transition-colors',
    selected ? 'border-accent/30 bg-accent/10 dark:bg-accent/15' : 'hover:border-accent/20 hover:bg-bg/80 dark:hover:bg-accent/5',
  );
}

function workflowFieldClass(className?: string): string {
  return cn(
    'w-full rounded-xl border border-border bg-bg/80 px-3 py-2 text-sm text-text shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] dark:shadow-none placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-ring',
    className,
  );
}

export function RemediationWorkflowContent({
  isActive = true,
  onClose,
  actionId,
  actionTitle,
  actionType,
  accountId,
  region,
  mode,
  hasWriteRole,
  tenantId,
  onChooseException,
  onChromeStateChange,
}: RemediationWorkflowContentProps) {
  const requiresRootAccount = actionType === ROOT_ACCOUNT_REQUIRED_ACTION_TYPE;
  const optionsCacheKey = useMemo(() => remediationOptionsCacheKey(actionId, mode), [actionId, mode]);
  const optionsCacheRef = useRef(new Map<string, RemediationOptionsResponse>());
  const [options, setOptions] = useState<RemediationOptionsResponse | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [strategyInputValues, setStrategyInputValues] = useState<Record<string, string>>({});
  const [riskAcknowledged, setRiskAcknowledged] = useState(false);
  const [bucketCreationAcknowledged, setBucketCreationAcknowledged] = useState(false);
  const [manualEvidenceItems, setManualEvidenceItems] = useState<ManualWorkflowEvidenceItem[]>([]);
  const [manualEvidenceFiles, setManualEvidenceFiles] = useState<Record<string, File | null>>({});
  const [manualEvidenceError, setManualEvidenceError] = useState<string | null>(null);
  const [manualEvidenceUploadingKey, setManualEvidenceUploadingKey] = useState<string | null>(null);

  const [preview, setPreview] = useState<RemediationPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [detectedPublicIpv4Cidr, setDetectedPublicIpv4Cidr] = useState<string | null>(null);
  const [rollbackCopyState, setRollbackCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [triggerReevalAfterApply, setTriggerReevalAfterApply] = useState(false);
  const [reevalTriggerNotice, setReevalTriggerNotice] = useState<{ kind: 'success' | 'error'; message: string } | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createdRunId, setCreatedRunId] = useState<string | null>(null);
  const previewRequestSequence = useRef(0);

  const showProgress = createdRunId !== null;
  const strategiesForMode = useMemo(() => {
    return (options?.strategies ?? []).filter((strategy) => strategy.mode === mode);
  }, [options, mode]);
  const nonExceptionStrategiesForMode = useMemo(
    () => strategiesForMode.filter((strategy) => !strategy.exception_only),
    [strategiesForMode]
  );
  const exceptionStrategyForMode = useMemo(
    () => strategiesForMode.find((strategy) => strategy.exception_only) ?? null,
    [strategiesForMode]
  );

  const selectedStrategy = useMemo(() => {
    if (!selectedStrategyId) return null;
    return strategiesForMode.find((strategy) => strategy.strategy_id === selectedStrategyId) ?? null;
  }, [selectedStrategyId, strategiesForMode]);
  const selectedBlastRadius = useMemo(() => {
    const radius = selectedStrategy?.blast_radius;
    if (!radius) return null;
    return BLAST_RADIUS_META[radius] ?? null;
  }, [selectedStrategy?.blast_radius]);
  const shouldUseExceptionFlow = Boolean(
    selectedStrategy?.exception_only || selectedStrategy?.supports_exception_flow
  );
  const exceptionDurationField = useMemo(() => {
    if (!selectedStrategy?.exception_only) return null;
    return selectedStrategy.input_schema?.fields?.find((field) => field.key === 'exception_duration_days') ?? null;
  }, [selectedStrategy]);
  const exceptionReasonField = useMemo(() => {
    if (!selectedStrategy?.exception_only) return null;
    return selectedStrategy.input_schema?.fields?.find((field) => field.key === 'exception_reason') ?? null;
  }, [selectedStrategy]);
  const selectedExceptionDuration = useMemo(() => {
    if (!selectedStrategy?.exception_only || !exceptionDurationField) return '30';
    const resolved = resolveRawFieldValue(exceptionDurationField, strategyInputValues).trim();
    if (EXCEPTION_DURATION_OPTIONS.includes(resolved as (typeof EXCEPTION_DURATION_OPTIONS)[number])) {
      return resolved;
    }
    return '30';
  }, [exceptionDurationField, selectedStrategy?.exception_only, strategyInputValues]);
  const exceptionReasonValue = useMemo(() => {
    if (!selectedStrategy?.exception_only) return '';
    return (strategyInputValues.exception_reason ?? '').trim();
  }, [selectedStrategy?.exception_only, strategyInputValues.exception_reason]);
  const exceptionReasonError = useMemo(() => {
    if (!selectedStrategy?.exception_only) return null;
    if (!exceptionReasonValue) {
      return 'Provide a reason for this exception.';
    }
    if (exceptionReasonValue.length < 10) {
      return 'Reason must be at least 10 characters.';
    }
    return null;
  }, [exceptionReasonValue, selectedStrategy?.exception_only]);

  const hasCatalogStrategies = (options?.strategies?.length ?? 0) > 0;
  const manualWorkflow = options?.manual_workflow ?? null;
  const isManualOnlyWorkflow = Boolean(manualWorkflow?.manual_only);
  // Only block if options have fully loaded and there are genuinely no strategies.
  // Do NOT block based on actionType === 'pr_only' alone — many controls (CloudTrail, GuardDuty, etc.)
  // use pr_only as their action type and DO have registered Terraform/CloudFormation strategies.
  const isPrOnlyBundleUnsupported = !optionsLoading && !optionsError && mode === 'pr_only' && !hasCatalogStrategies && !isManualOnlyWorkflow;
  const receivedEvidenceKeys = useMemo(
    () => new Set(manualWorkflow?.completion_validation?.received_evidence_keys ?? []),
    [manualWorkflow]
  );
  const strategyInputs = useMemo(
    () => buildStrategyInputs(selectedStrategy, strategyInputValues),
    [selectedStrategy, strategyInputValues]
  );
  const missingRequiredFields = useMemo(
    () => missingRequiredInputFields(selectedStrategy, strategyInputValues),
    [selectedStrategy, strategyInputValues]
  );
  const visibleStrategyFields = useMemo(() => {
    if (!selectedStrategy) return [];
    const allFields = selectedStrategy.input_schema?.fields ?? [];
    return allFields.filter((field) => isFieldVisible(field, strategyInputValues, allFields));
  }, [selectedStrategy, strategyInputValues]);
  const groupedStrategyFields = useMemo(() => {
    const groups = new Map<string, { label: string; fields: StrategyInputSchemaField[]; impactTexts: string[] }>();
    for (const field of visibleStrategyFields) {
      const label = field.group?.trim() || 'General';
      if (!groups.has(label)) {
        groups.set(label, { label, fields: [], impactTexts: [] });
      }
      const group = groups.get(label)!;
      group.fields.push(field);
      if (field.impact_text) {
        group.impactTexts.push(field.impact_text);
      }
      if (field.type === 'select') {
        const selectedOption = field.options?.find(
          (option) => option.value === resolveRawFieldValue(field, strategyInputValues).trim()
        );
        if (selectedOption?.impact_text) {
          group.impactTexts.push(selectedOption.impact_text);
        }
      }
    }
    return Array.from(groups.values()).map((group) => ({
      ...group,
      impactTexts: Array.from(new Set(group.impactTexts.map((text) => text.trim()).filter((text) => text.length > 0))),
    }));
  }, [strategyInputValues, visibleStrategyFields]);
  const showGroupHeadings = useMemo(() => {
    return groupedStrategyFields.length > 1 || groupedStrategyFields.some((group) => group.label !== 'General');
  }, [groupedStrategyFields]);
  const previewDiffLines = useMemo(() => {
    if (!preview || !Array.isArray(preview.diff_lines)) return [];
    return preview.diff_lines.filter(
      (line): line is { type: 'add' | 'remove' | 'unchanged'; label: string; value: string } =>
        Boolean(
          line &&
            typeof line.type === 'string' &&
            typeof line.label === 'string' &&
            typeof line.value === 'string'
        )
    );
  }, [preview]);
  const previewResolution = preview?.resolution ?? null;
  const previewSupportTier = getRemediationOutcomePresentation(previewResolution?.support_tier);
  const guidedReview = useMemo(() => {
    return buildGuidedReviewContent(previewResolution, previewSupportTier);
  }, [previewResolution, previewSupportTier]);
  const inputValidationErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    for (const field of visibleStrategyFields) {
      const rawValue = resolveRawFieldValue(field, strategyInputValues).trim();
      if (!rawValue) continue;
      if (field.type === 'cidr') {
        const error = validateCidrInput(rawValue);
        if (error) {
          errors[field.key] = error;
        }
        continue;
      }
      if (field.type === 'number') {
        const parsed = parseNumberInput(rawValue);
        if (parsed === undefined) {
          errors[field.key] = 'Enter a valid number.';
          continue;
        }
        if (typeof field.min === 'number' && parsed < field.min) {
          errors[field.key] = `Value must be at least ${field.min}.`;
          continue;
        }
        if (typeof field.max === 'number' && parsed > field.max) {
          errors[field.key] = `Value must be at most ${field.max}.`;
        }
      }
    }
    return errors;
  }, [strategyInputValues, visibleStrategyFields]);
  const hasInputValidationErrors = Object.keys(inputValidationErrors).length > 0;
  const cloudTrailCreateBucketMode = useMemo(() => {
    if (selectedStrategy?.strategy_id !== 'cloudtrail_enable_guided') return false;
    return parseBooleanInput(strategyInputValues.create_bucket_if_missing) === true;
  }, [selectedStrategy?.strategy_id, strategyInputValues.create_bucket_if_missing]);
  const buildStrategyInitialValues = useCallback(
    (strategy: RemediationOption | null): Record<string, string> => {
      const values = buildInitialStrategyInputValues(strategy, detectedPublicIpv4Cidr);
      if (!strategy || strategy.strategy_id !== 'cloudtrail_enable_guided') return values;

      const nextValues = { ...values };
      const trailBucketMode = strategy.preservation_summary?.trail_bucket_mode;
      if (trailBucketMode === 'existing') {
        nextValues.create_bucket_if_missing = 'false';
      } else if (trailBucketMode === 'create_if_missing') {
        nextValues.create_bucket_if_missing = 'true';
      }

      if (nextValues.trail_bucket_name) return nextValues;
      if (parseBooleanInput(nextValues.create_bucket_if_missing) !== true) return nextValues;

      const bucketField = strategy.input_schema?.fields?.find((field) => field.key === 'trail_bucket_name');
      if (!bucketField) return nextValues;
      const safeDefaultValue = resolveSafeDefaultValue(bucketField, accountId, region, detectedPublicIpv4Cidr);
      if (!safeDefaultValue) return nextValues;
      nextValues.trail_bucket_name = safeDefaultValue;
      return nextValues;
    },
    [accountId, detectedPublicIpv4Cidr, region],
  );

  const requiresRiskAck = useMemo(() => {
    const checks = selectedStrategy?.dependency_checks ?? [];
    return checks.some((check) => check.status === 'warn' || check.status === 'unknown');
  }, [selectedStrategy]);

  const hasFailingChecks = useMemo(() => {
    const checks = selectedStrategy?.dependency_checks ?? [];
    return checks.some((check) => check.status === 'fail');
  }, [selectedStrategy]);
  const failingChecks = useMemo(() => {
    const checks = selectedStrategy?.dependency_checks ?? [];
    return checks.filter((check) => check.status === 'fail');
  }, [selectedStrategy]);

  const canRunDirectFix = useMemo(() => {
    if (isManualOnlyWorkflow) return false;
    if (mode !== 'direct_fix') return true;
    if (!hasWriteRole) return false;
    if (hasCatalogStrategies) {
      return strategiesForMode.length > 0;
    }
    return LEGACY_DIRECT_FIX_ACTION_TYPES.has(actionType);
  }, [mode, hasWriteRole, hasCatalogStrategies, strategiesForMode, actionType, isManualOnlyWorkflow]);

  const resetModalState = () => {
    setOptions(null);
    setOptionsLoading(false);
    setOptionsError(null);
    setSelectedStrategyId(null);
    setStrategyInputValues({});
    setRiskAcknowledged(false);
    setBucketCreationAcknowledged(false);
    setManualEvidenceItems([]);
    setManualEvidenceFiles({});
    setManualEvidenceError(null);
    setManualEvidenceUploadingKey(null);
    setPreview(null);
    setPreviewLoading(false);
    setPreviewError(null);
    setSubmitError(null);
    setCreatedRunId(null);
    setDetectedPublicIpv4Cidr(null);
    setRollbackCopyState('idle');
    setTriggerReevalAfterApply(false);
    setReevalTriggerNotice(null);
  };

  const loadOptions = useCallback(() => {
    let cancelled = false;

    if (isPrOnlyBundleUnsupported) {
      setOptions(null);
      setOptionsError(PR_ONLY_BUNDLE_UNSUPPORTED_MESSAGE);
      setOptionsLoading(false);
      return () => {
        cancelled = true;
      };
    }

    const cachedOptions = optionsCacheRef.current.get(optionsCacheKey);
    if (cachedOptions) {
      setOptions(cachedOptions);
      setOptionsError(null);
      const selected = selectInitialStrategyForMode(cachedOptions.strategies, mode);
      setSelectedStrategyId(selected?.strategy_id ?? null);
      setStrategyInputValues(buildStrategyInitialValues(selected));
      setRiskAcknowledged(false);
      setBucketCreationAcknowledged(false);
      setTriggerReevalAfterApply(false);
      setReevalTriggerNotice(null);
      setOptionsLoading(false);
      return () => {
        cancelled = true;
      };
    }

    setOptionsLoading(true);
    setOptionsError(null);
    getRemediationOptions(actionId, tenantId)
      .then((response) => {
        if (cancelled) return;
        optionsCacheRef.current.set(optionsCacheKey, response);
        setOptions(response);
        const selected = selectInitialStrategyForMode(response.strategies, mode);
        if (!selected) {
          setSelectedStrategyId(null);
          setStrategyInputValues({});
          return;
        }
        setSelectedStrategyId(selected.strategy_id);
        setStrategyInputValues(buildStrategyInitialValues(selected));
        setRiskAcknowledged(false);
        setBucketCreationAcknowledged(false);
        setTriggerReevalAfterApply(false);
        setReevalTriggerNotice(null);
      })
      .catch((error) => {
        if (!cancelled) setOptionsError(getErrorMessage(error));
      })
      .finally(() => {
        if (!cancelled) setOptionsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [actionId, isPrOnlyBundleUnsupported, mode, optionsCacheKey, tenantId]);

  useEffect(() => {
    if (!isActive) return;
    return loadOptions();
  }, [isActive, loadOptions]);

  useEffect(() => {
    if (!isActive) return;
    let cancelled = false;

    loadDetectedPublicIpv4Cidr()
      .then((cidr) => {
        if (cancelled || !cidr) return;
        setDetectedPublicIpv4Cidr(cidr);
      })
      .catch(() => {
        // Best-effort only; CIDR field remains user-supplied when ipify is unavailable.
      });

    return () => {
      cancelled = true;
    };
  }, [isActive]);

  useEffect(() => {
    if (!isActive || !detectedPublicIpv4Cidr) return;
    if (selectedStrategy?.strategy_id !== 'sg_restrict_public_ports_guided') return;
    setStrategyInputValues((prev) => {
      if ((prev.allowed_cidr ?? '').trim()) return prev;
      return { ...prev, allowed_cidr: detectedPublicIpv4Cidr };
    });
  }, [detectedPublicIpv4Cidr, isActive, selectedStrategy?.strategy_id]);

  useEffect(() => {
    setRollbackCopyState('idle');
  }, [selectedStrategy?.strategy_id]);

  const loadManualEvidence = useCallback(() => {
    let cancelled = false;
    setManualEvidenceError(null);
    listManualWorkflowEvidence(actionId, tenantId)
      .then((items) => {
        if (!cancelled) setManualEvidenceItems(items);
      })
      .catch((error) => {
        if (!cancelled) setManualEvidenceError(getErrorMessage(error));
      });
    return () => {
      cancelled = true;
    };
  }, [actionId, tenantId]);

  useEffect(() => {
    if (!isActive || !isManualOnlyWorkflow) return;
    return loadManualEvidence();
  }, [isActive, isManualOnlyWorkflow, loadManualEvidence]);

  const loadPreview = useCallback(() => {
    const requestSequence = previewRequestSequence.current + 1;
    previewRequestSequence.current = requestSequence;
    setPreviewLoading(true);
    setPreviewError(null);

    getRemediationPreview(actionId, tenantId, mode, selectedStrategy?.strategy_id, strategyInputs)
      .then((result) => {
        if (previewRequestSequence.current === requestSequence) {
          setPreview(result);
        }
      })
      .catch((error) => {
        if (previewRequestSequence.current === requestSequence) {
          setPreviewError(getErrorMessage(error));
        }
      })
      .finally(() => {
        if (previewRequestSequence.current === requestSequence) {
          setPreviewLoading(false);
        }
      });
  }, [
    actionId,
    mode,
    tenantId,
    selectedStrategy?.strategy_id,
    strategyInputs,
  ]);

  useEffect(() => {
    if (!isActive || isManualOnlyWorkflow) return;
    if (mode === 'direct_fix' && !canRunDirectFix) return;
    if (mode === 'pr_only' && hasCatalogStrategies && !selectedStrategy) return;
    const timeout = window.setTimeout(() => {
      loadPreview();
    }, PREVIEW_DEBOUNCE_MS);
    return () => window.clearTimeout(timeout);
  }, [isActive, mode, canRunDirectFix, hasCatalogStrategies, isManualOnlyWorkflow, selectedStrategy, loadPreview]);

  const handleUploadManualEvidence = async (evidenceKey: string) => {
    const evidenceFile = manualEvidenceFiles[evidenceKey];
    if (!evidenceFile) {
      setManualEvidenceError(`Select a file for ${evidenceKey} before uploading.`);
      return;
    }
    setManualEvidenceError(null);
    setManualEvidenceUploadingKey(evidenceKey);
    try {
      await uploadManualWorkflowEvidence(actionId, evidenceKey, evidenceFile, undefined, tenantId);
      const [latestOptions, evidenceItems] = await Promise.all([
        getRemediationOptions(actionId, tenantId),
        listManualWorkflowEvidence(actionId, tenantId),
      ]);
      setOptions(latestOptions);
      setManualEvidenceItems(evidenceItems);
      setManualEvidenceFiles((prev) => ({ ...prev, [evidenceKey]: null }));
    } catch (error) {
      setManualEvidenceError(getErrorMessage(error));
    } finally {
      setManualEvidenceUploadingKey(null);
    }
  };

  const handleSubmit = async () => {
    setSubmitError(null);
    setReevalTriggerNotice(null);

    if (isPrOnlyBundleUnsupported) {
      setSubmitError(PR_ONLY_BUNDLE_UNSUPPORTED_MESSAGE);
      return;
    }
    if (isManualOnlyWorkflow) {
      setSubmitError(
        manualWorkflow?.summary ||
          'This remediation is manual-only. Follow the manual workflow steps and collect required evidence.'
      );
      return;
    }

    if (hasCatalogStrategies && !selectedStrategy) {
      setSubmitError('Select a remediation strategy before continuing.');
      return;
    }

    if (missingRequiredFields.length > 0) {
      setSubmitError(`Missing required strategy inputs: ${missingRequiredFields.join(', ')}.`);
      return;
    }
    if (hasInputValidationErrors) {
      setSubmitError('Resolve invalid strategy inputs before continuing.');
      return;
    }

    if (shouldUseExceptionFlow) {
      if (!selectedStrategy) {
        setSubmitError('Select an exception strategy before continuing.');
        return;
      }
      if (
        selectedStrategy.exception_only &&
        !EXCEPTION_DURATION_OPTIONS.includes(selectedExceptionDuration as (typeof EXCEPTION_DURATION_OPTIONS)[number])
      ) {
        setSubmitError('Select an exception duration (7, 14, 30, or 90 days).');
        return;
      }
      if (selectedStrategy.exception_only && exceptionReasonError) {
        setSubmitError(exceptionReasonError);
        return;
      }
      if (!onChooseException) {
        setSubmitError('Exception flow is unavailable for this action.');
        return;
      }
      onChooseException({
        strategy: selectedStrategy,
        strategyInputs,
      });
      return;
    }

    if (!shouldUseExceptionFlow && hasFailingChecks) {
      setSubmitError('Safety gate blocked this remediation strategy. Resolve failing dependency checks first.');
      return;
    }

    if (!shouldUseExceptionFlow && requiresRiskAck && !riskAcknowledged) {
      setSubmitError('You must acknowledge risk warnings before continuing.');
      return;
    }
    if (!shouldUseExceptionFlow && cloudTrailCreateBucketMode && !bucketCreationAcknowledged) {
      setSubmitError('You must explicitly approve CloudTrail bucket creation before continuing.');
      return;
    }

    setIsSubmitting(true);
    try {
      const run = await createRemediationRun(
        actionId,
        mode,
        tenantId,
        selectedStrategy?.strategy_id,
        strategyInputs,
        riskAcknowledged,
        bucketCreationAcknowledged
      );

      if (
        mode === 'direct_fix' &&
        triggerReevalAfterApply &&
        selectedStrategy?.supports_immediate_reeval === true
      ) {
        void triggerActionReevaluation(actionId, tenantId, selectedStrategy.strategy_id)
          .then((response) => {
            setReevalTriggerNotice({
              kind: 'success',
              message: response.message,
            });
          })
          .catch((error) => {
            setReevalTriggerNotice({
              kind: 'error',
              message: `Run started, but re-evaluation could not be queued: ${getErrorMessage(error)}`,
            });
          });
      }

      setCreatedRunId(run.id);
      setIsSubmitting(false);
    } catch (error) {
      if (isApiError(error) && error.status === 409) {
        try {
          const { items } = await listRemediationRuns(
            { action_id: actionId, status: 'pending', limit: 1 },
            tenantId
          );
          if (items.length > 0) {
            setCreatedRunId(items[0].id);
            setIsSubmitting(false);
            return;
          }
        } catch {
          // fall through to normal error handling
        }
      }
      setSubmitError(getErrorMessage(error));
      setIsSubmitting(false);
    }
  };

  const handleCopyRollbackCommand = async () => {
    const rollbackCommand = selectedStrategy?.rollback_command?.trim();
    if (!rollbackCommand) return;
    if (
      typeof navigator === 'undefined' ||
      !navigator.clipboard ||
      typeof navigator.clipboard.writeText !== 'function'
    ) {
      setRollbackCopyState('failed');
      return;
    }
    try {
      await navigator.clipboard.writeText(rollbackCommand);
      setRollbackCopyState('copied');
    } catch {
      setRollbackCopyState('failed');
    }
  };

  const handleUseSafeDefault = (field: StrategyInputSchemaField) => {
    const safeDefaultValue = resolveSafeDefaultValue(field, accountId, region, detectedPublicIpv4Cidr);
    setStrategyInputValues((prev) => {
      if (safeDefaultValue) {
        return { ...prev, [field.key]: safeDefaultValue };
      }
      return prev;
    });
  };

  useEffect(() => {
    if (isActive) return;
    resetModalState();
  }, [isActive]);

  const title = showProgress
    ? 'Bundle progress'
    : shouldUseExceptionFlow
      ? 'Create exception'
      : mode === 'direct_fix'
        ? 'Apply Direct Fix'
        : 'Generate PR Bundle';
  const headerBadge = !showProgress && selectedBlastRadius ? selectedBlastRadius : null;

  useEffect(() => {
    onChromeStateChange?.({
      blastRadius: headerBadge,
      preventClose: isSubmitting,
      showProgress,
      title,
    });
  }, [headerBadge, isSubmitting, onChromeStateChange, showProgress, title]);

  return (
    <div className="min-w-0 space-y-6 overflow-x-hidden">
      {showProgress ? (
        <>
          <RemediationRunProgress runId={createdRunId!} tenantId={tenantId} compact={false} />
          <div className={remediationInsetClass('default', 'flex flex-col gap-3 sm:flex-row')}>
            <Button variant="secondary" onClick={onClose} className="flex-1">
              Close
            </Button>
            <Link href={`/remediation-runs/${createdRunId}`} className="flex-1">
              <MajorActionButton className="w-full">Open bundle details</MajorActionButton>
            </Link>
          </div>
        </>
      ) : (
        <>
          <RemediationPanel className="p-6" tone={mode === 'direct_fix' ? 'accent' : 'info'}>
            <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
              <div className="max-w-3xl space-y-4">
                <p className={cn(REMEDIATION_EYEBROW_CLASS, 'opacity-80')}>
                  {mode === 'direct_fix' ? 'DIRECT FIX CONTEXT' : 'PR BUNDLE CONTEXT'}
                </p>
                <h3 className="text-2xl font-bold leading-tight tracking-tight text-text">
                  {actionTitle}
                </h3>
                <p className="text-sm leading-relaxed text-text/75">
                  Review the strategy, safety gates, and generated guidance before {mode === 'direct_fix' ? 'applying the fix' : 'creating the remediation bundle'}.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="default" className="bg-surface/60 px-3 py-1 font-mono">
                  <span className="opacity-50 mr-1">Account:</span> {accountId}
                </Badge>
                {region && (
                  <Badge variant="default" className="bg-surface/60 px-3 py-1 font-mono">
                    <span className="opacity-50 mr-1">Region:</span> {region}
                  </Badge>
                )}
                <Badge variant="info" className="px-3 py-1">
                  <span className="opacity-50 mr-1">Mode:</span> {mode === 'direct_fix' ? 'Direct fix' : 'PR bundle'}
                </Badge>
              </div>
            </div>
          </RemediationPanel>

          {reevalTriggerNotice && (
            <RemediationCallout
              description={reevalTriggerNotice.message}
              tone={reevalTriggerNotice.kind === 'success' ? 'success' : 'warning'}
              title={reevalTriggerNotice.kind === 'success' ? 'Re-evaluation queued' : 'Re-evaluation warning'}
            />
          )}

          {requiresRootAccount && (
            <RemediationCallout
              tone="warning"
              title="AWS root account required"
              description={
                <>
                  To fix this issue, sign in as the AWS root user for account{' '}
                  <span className="font-mono">{accountId}</span>. IAM users and roles cannot disable or delete root
                  access keys.
                </>
              }
            >
              <p className="text-xs text-text/70">
                Runbook: <span className="font-mono">{options?.runbook_url || ROOT_ACCOUNT_REQUIRED_RUNBOOK}</span>
              </p>
            </RemediationCallout>
          )}

          {optionsLoading && (
            <RemediationCallout
              description="Loading remediation options…"
              title="Preparing workflow"
              tone="info"
            />
          )}
          {optionsError && (
            <RemediationCallout description={optionsError} title="Unable to load options" tone="danger" />
          )}
          {!optionsLoading && !optionsError && options?.pre_execution_notice && (
            <RemediationCallout tone="warning" title="Operator notice">
              <p className="text-sm leading-6 text-text/78">{options.pre_execution_notice}</p>
              {options.runbook_url && (
                <p className="mt-2 text-xs text-text/70">
                  Runbook: <span className="font-mono">{options.runbook_url}</span>
                </p>
              )}
            </RemediationCallout>
          )}

          {!optionsLoading && !optionsError && hasCatalogStrategies && (
            <RemediationSection
              description="Select how this action should be handled in the remediation workflow."
              eyebrow="Workflow"
              title="Choose remediation strategy"
              titleExplainer={<SectionTitleExplainer conceptId="remediation_strategy" context="remediation" label="Choose remediation strategy" />}
            >
              <div className="space-y-3">
                {strategiesForMode.length === 0 && (
                  <p className="text-sm text-muted">
                    No strategy is available for mode <span className="font-mono">{mode}</span>.
                  </p>
                )}
                {nonExceptionStrategiesForMode.map((strategy) => (
                  <label
                    key={strategy.strategy_id}
                    className={remediationStrategyCardClass(selectedStrategyId === strategy.strategy_id)}
                  >
                    <div className="flex items-start gap-3">
                      <input
                        type="radio"
                        name="strategy"
                        value={strategy.strategy_id}
                        checked={selectedStrategyId === strategy.strategy_id}
                        onChange={() => {
                          setSelectedStrategyId(strategy.strategy_id);
                          setStrategyInputValues(buildStrategyInitialValues(strategy));
                          setRiskAcknowledged(false);
                          setBucketCreationAcknowledged(false);
                          setTriggerReevalAfterApply(false);
                          setReevalTriggerNotice(null);
                        }}
                        className="mt-1 h-4 w-4"
                      />
                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-text">{strategy.label}</p>
                          <span className="rounded-full border border-border/40 bg-accent/12 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-[#0F2E9B] dark:text-accent">
                            Risk {strategy.risk_level}
                          </span>
                          {strategy.recommended && (
                            <span className="rounded-full border border-accent/20 bg-accent/8 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-accent">
                              Recommended
                            </span>
                          )}
                        </div>
                        <p className="text-xs leading-6 text-text/68">
                          {strategy.exception_only
                            ? 'This path opens the exception workflow instead of creating a run.'
                            : 'This keeps the current remediation-run creation behavior intact.'}
                        </p>
                      </div>
                    </div>
                  </label>
                ))}
                {exceptionStrategyForMode && (
                  <label
                    className={remediationStrategyCardClass(
                      selectedStrategyId === exceptionStrategyForMode.strategy_id,
                      true,
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <input
                        type="radio"
                        name="strategy"
                        value={exceptionStrategyForMode.strategy_id}
                        checked={selectedStrategyId === exceptionStrategyForMode.strategy_id}
                        onChange={() => {
                          setSelectedStrategyId(exceptionStrategyForMode.strategy_id);
                          setStrategyInputValues(buildStrategyInitialValues(exceptionStrategyForMode));
                          setRiskAcknowledged(false);
                          setBucketCreationAcknowledged(false);
                          setTriggerReevalAfterApply(false);
                          setReevalTriggerNotice(null);
                        }}
                        className="mt-1 h-4 w-4"
                      />
                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold text-text">I need an exception</p>
                          <span className="rounded-full border border-warning/24 bg-warning/12 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-warning">
                            Exception path
                          </span>
                        </div>
                        <p className="text-xs leading-6 text-text/68">
                          I can&apos;t apply this fix right now — create a time-limited exception.
                        </p>
                      </div>
                    </div>
                  </label>
                )}
              </div>
            </RemediationSection>
          )}

          {selectedStrategy?.exception_only && (
            <RemediationSection
              description="This strategy creates an exception record and does not generate a PR bundle."
              eyebrow="Exception path"
              title="Create exception"
              titleExplainer={<SectionTitleExplainer conceptId="exception_path" context="remediation" label="Create exception" />}
              tone="warning"
            >
              <div className="space-y-4">
                <RemediationCallout
                  description="Use Exception workflow instead of PR bundle."
                  title="Routing note"
                  tone="warning"
                />
                <div className={remediationInsetClass('warning')}>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className={REMEDIATION_EYEBROW_CLASS}>
                      {exceptionDurationField?.description ?? 'Exception duration'}
                    </p>
                    <SectionTitleExplainer conceptId="exception_duration" context="remediation" label="Exception duration" />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {EXCEPTION_DURATION_OPTIONS.map((days) => (
                      <button
                        key={days}
                        type="button"
                        onClick={() =>
                          setStrategyInputValues((prev) => ({
                            ...prev,
                            exception_duration_days: days,
                          }))
                        }
                        className={cn(
                          'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                          selectedExceptionDuration === days
                            ? 'border-warning bg-warning/20 text-warning'
                            : 'border-border bg-bg text-muted hover:border-warning/20 hover:text-text',
                        )}
                        aria-pressed={selectedExceptionDuration === days}
                      >
                        {days} days
                      </button>
                    ))}
                  </div>
                </div>
                <div className={remediationInsetClass('warning')}>
                  <div className="flex flex-wrap items-center gap-2">
                    <label className="text-xs text-muted" htmlFor="exception-reason-input">
                      {exceptionReasonField?.description ?? 'Reason'}
                    </label>
                    <SectionTitleExplainer conceptId="exception_reason" context="remediation" label="Reason" />
                  </div>
                  <textarea
                    id="exception-reason-input"
                    value={strategyInputValues.exception_reason ?? ''}
                    onChange={(event) =>
                      setStrategyInputValues((prev) => ({ ...prev, exception_reason: event.target.value }))
                    }
                    rows={3}
                    className={workflowFieldClass('mt-3')}
                    placeholder={
                      exceptionReasonField?.placeholder || 'Describe why this exception is needed right now.'
                    }
                  />
                  {exceptionReasonError && <p className="mt-2 text-xs text-danger">{exceptionReasonError}</p>}
                </div>
              </div>
            </RemediationSection>
          )}

          {!optionsLoading && !optionsError && isManualOnlyWorkflow && manualWorkflow && (
            <RemediationSection
              description={manualWorkflow.summary}
              eyebrow="Manual workflow"
              title={manualWorkflow.title}
              titleExplainer={<SectionTitleExplainer conceptId="evidence_status" context="remediation" label={manualWorkflow.title} />}
            >
              <div className="space-y-5">
                <div className={remediationInsetClass('default')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Steps</p>
                  <div className="mt-3 space-y-2">
                    {manualWorkflow.steps.map((step, index) => (
                      <p key={step.id} className="text-sm leading-7 text-text/78">
                        {index + 1}. <span className="font-semibold text-text">{step.title}</span>: {step.instructions}
                      </p>
                    ))}
                  </div>
                </div>
                <div className={remediationInsetClass('default')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Required evidence</p>
                  <div className="mt-3 space-y-3">
                    {manualWorkflow.required_evidence.map((item) => (
                      <div key={item.key} className={remediationInsetClass('default', 'space-y-3')}>
                        <div>
                          <p className="text-sm text-text">
                            <span className="font-mono">{item.key}</span>: {item.description}
                          </p>
                          <p className="mt-1 text-xs text-muted">
                            Status:{' '}
                            {receivedEvidenceKeys.has(item.key) ? (
                              <span className="text-success">uploaded</span>
                            ) : (
                              <span className="text-warning">missing</span>
                            )}
                          </p>
                        </div>
                        <div className="flex flex-col gap-2 md:flex-row md:items-center">
                          <input
                            type="file"
                            className="text-xs text-text"
                            onChange={(event) =>
                              setManualEvidenceFiles((prev) => ({
                                ...prev,
                                [item.key]: event.target.files?.[0] ?? null,
                              }))
                            }
                          />
                          <Button
                            type="button"
                            variant="secondary"
                            disabled={manualEvidenceUploadingKey === item.key || !manualEvidenceFiles[item.key]}
                            onClick={() => handleUploadManualEvidence(item.key)}
                          >
                            {manualEvidenceUploadingKey === item.key ? 'Uploading…' : 'Upload evidence'}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                {manualEvidenceItems.length > 0 && (
                  <div className={remediationInsetClass('default')}>
                    <p className={REMEDIATION_EYEBROW_CLASS}>Uploaded artifacts</p>
                    <div className="mt-3 space-y-2">
                      {manualEvidenceItems.map((item) => (
                        <p key={item.id} className="text-sm leading-7 text-text/78">
                          - <span className="font-mono">{item.evidence_key}</span>: {item.filename}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.85fr)]">
                  <div className={remediationInsetClass('default')}>
                    <p className={REMEDIATION_EYEBROW_CLASS}>Verification criteria</p>
                    <div className="mt-3 space-y-2">
                      {manualWorkflow.verification_criteria.map((criterion) => (
                        <p key={criterion.id} className="text-sm leading-7 text-text/78">
                          - {criterion.description}
                        </p>
                      ))}
                    </div>
                  </div>
                  <RemediationCallout
                    description={manualWorkflow.completion_validation.detail}
                    title="Evidence status"
                    tone="warning"
                  />
                </div>
                {manualEvidenceError && (
                  <RemediationCallout description={manualEvidenceError} title="Upload failed" tone="danger" />
                )}
              </div>
            </RemediationSection>
          )}

          {selectedStrategy && visibleStrategyFields.length > 0 && !selectedStrategy.exception_only && (
            <RemediationSection
              description="Provide any strategy-specific inputs before the remediation run is created."
              eyebrow="Configuration"
              title="Strategy inputs"
              titleExplainer={<SectionTitleExplainer conceptId="strategy_inputs" context="remediation" label="Strategy inputs" />}
            >
              <div className="space-y-4">
                {groupedStrategyFields.map((group) => (
                  <div key={group.label} className={remediationInsetClass('default', 'space-y-4')}>
                    {showGroupHeadings && (
                      <h4 className={REMEDIATION_EYEBROW_CLASS}>{group.label}</h4>
                    )}
                    {group.fields.map((field) => {
                      const inputId = `strategy-input-${field.key}`;
                      const rawValue = resolveRawFieldValue(field, strategyInputValues);
                      const selectedOption =
                        field.type === 'select'
                          ? field.options?.find((option) => option.value === rawValue.trim())
                          : undefined;
                      const numberRangeHint =
                        field.type === 'number'
                          ? [
                              typeof field.min === 'number' ? `min ${field.min}` : null,
                              typeof field.max === 'number' ? `max ${field.max}` : null,
                            ]
                              .filter((value): value is string => value !== null)
                              .join(', ')
                          : '';
                      const booleanValue = parseBooleanInput(rawValue) ?? false;
                      return (
                        <div key={field.key} className="space-y-2">
                          <div className="flex items-center gap-2">
                            <label
                              className="text-xs text-muted"
                              htmlFor={field.type === 'boolean' ? undefined : inputId}
                              id={`${inputId}-label`}
                            >
                              {field.description}
                              {field.required ? ' *' : ''}
                            </label>
                            <ExplainerHint
                              content={{ conceptId: 'strategy_inputs', context: 'remediation' }}
                              label={field.description}
                              iconOnly
                            />
                            {field.help_text && (
                              <AnimatedTooltip content={field.help_text}>
                                <button
                                  type="button"
                                  aria-label={`Help for ${field.description}`}
                                  className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-border text-[10px] text-muted"
                                >
                                  i
                                </button>
                              </AnimatedTooltip>
                            )}
                          </div>

                          {field.type === 'string_array' && (
                            <textarea
                              id={inputId}
                              className={workflowFieldClass()}
                              rows={3}
                              placeholder={field.placeholder || 'Enter one value per line or comma-separated'}
                              value={rawValue}
                              onChange={(event) =>
                                setStrategyInputValues((prev) => ({ ...prev, [field.key]: event.target.value }))
                              }
                            />
                          )}

                          {field.type === 'select' && (
                            <>
                              <select
                                id={inputId}
                                className={workflowFieldClass()}
                                value={rawValue}
                                onChange={(event) =>
                                  setStrategyInputValues((prev) => ({ ...prev, [field.key]: event.target.value }))
                                }
                              >
                                {(field.options ?? []).map((option) => (
                                  <option key={option.value} value={option.value}>
                                    {option.label || option.value}
                                  </option>
                                ))}
                              </select>
                              {selectedOption?.description && (
                                <p className="text-xs text-muted">{selectedOption.description}</p>
                              )}
                            </>
                          )}

                          {field.type === 'boolean' && (
                            <div className="flex items-center gap-3">
                              <button
                                id={inputId}
                                type="button"
                                role="switch"
                                aria-checked={booleanValue}
                                aria-labelledby={`${inputId}-label`}
                                onClick={() =>
                                  setStrategyInputValues((prev) => {
                                    const nextValue = booleanValue ? 'false' : 'true';
                                    if (field.key === 'create_bucket_if_missing') {
                                      setBucketCreationAcknowledged(false);
                                    }
                                    return {
                                      ...prev,
                                      [field.key]: nextValue,
                                    };
                                  })
                                }
                                className={cn(
                                  'relative inline-flex h-6 w-11 items-center rounded-full transition',
                                  booleanValue ? 'bg-accent' : 'bg-border',
                                )}
                              >
                                <span
                                  className={cn(
                                    'inline-block h-5 w-5 transform rounded-full bg-accent transition shadow-sm',
                                    booleanValue ? 'translate-x-5' : 'translate-x-1',
                                  )}
                                />
                              </button>
                              <span className="text-xs text-muted">{booleanValue ? 'Enabled' : 'Disabled'}</span>
                            </div>
                          )}

                          {field.type === 'number' && (
                            <input
                              id={inputId}
                              type="number"
                              className={workflowFieldClass()}
                              value={rawValue}
                              min={field.min}
                              max={field.max}
                              onChange={(event) =>
                                setStrategyInputValues((prev) => ({ ...prev, [field.key]: event.target.value }))
                              }
                            />
                          )}

                          {(field.type === 'string' || field.type === 'cidr') && (
                            <input
                              id={inputId}
                              type="text"
                              className={workflowFieldClass()}
                              value={rawValue}
                              placeholder={field.placeholder || (field.type === 'cidr' ? '203.0.113.10/32' : '')}
                              onChange={(event) =>
                                setStrategyInputValues((prev) => ({ ...prev, [field.key]: event.target.value }))
                              }
                            />
                          )}

                          {field.type === 'number' && numberRangeHint && (
                            <p className="text-xs text-muted">Allowed range: {numberRangeHint}</p>
                          )}
                          {selectedStrategy?.strategy_id === 'cloudtrail_enable_guided' &&
                            field.key === 'trail_bucket_name' && (
                              <p className="text-xs text-muted">
                                {cloudTrailCreateBucketMode
                                  ? 'This is the exact S3 bucket name to create and use for CloudTrail log delivery.'
                                  : 'This must be the existing S3 bucket CloudTrail should use for log delivery.'}
                              </p>
                            )}
                          {field.type === 'cidr' && !inputValidationErrors[field.key] && (
                            <p className="text-xs text-muted">Use CIDR format like 203.0.113.10/32.</p>
                          )}
                          {inputValidationErrors[field.key] && (
                            <p className="text-xs text-danger">{inputValidationErrors[field.key]}</p>
                          )}
                          {field.safe_default_value !== undefined && (
                            <button
                              type="button"
                              className="text-xs text-accent hover:underline"
                              onClick={() => handleUseSafeDefault(field)}
                            >
                              Not sure? Use safe default
                              {field.safe_default_label ? `: ${field.safe_default_label}` : ' →'}
                            </button>
                          )}
                        </div>
                      );
                    })}

                    {group.impactTexts.length > 0 && (
                      <RemediationCallout title="Impact preview" tone="warning">
                        {group.impactTexts.map((impactText, index) => (
                          <p key={`${group.label}-impact-${index}`} className="mt-1 text-sm text-text">
                            {impactText}
                          </p>
                        ))}
                      </RemediationCallout>
                    )}
                  </div>
                ))}

                {missingRequiredFields.length > 0 && (
                  <p className="text-xs text-danger">Required: {missingRequiredFields.join(', ')}</p>
                )}
                {hasInputValidationErrors && (
                  <p className="text-xs text-danger">Resolve validation errors in strategy inputs.</p>
                )}
              </div>
            </RemediationSection>
          )}

          {selectedStrategy?.rollback_command && (
            <details className={remediationPanelClass('default')}>
              <summary className="cursor-pointer px-6 py-5 text-sm font-semibold text-text">
                How to undo this
              </summary>
              <div className="space-y-3 border-t border-border/35 px-6 py-5">
                <p className="text-xs text-muted">Run this AWS CLI command to rollback the change if needed:</p>
                <pre className={remediationInsetClass('default', 'overflow-x-auto text-xs text-text')}>
                  <code>{selectedStrategy.rollback_command}</code>
                </pre>
                <div className="flex items-center justify-end gap-2">
                  {rollbackCopyState === 'failed' && (
                    <p className="text-xs text-danger">Copy failed. Copy the command manually.</p>
                  )}
                  <Button type="button" variant="ghost" size="sm" onClick={handleCopyRollbackCommand}>
                    {rollbackCopyState === 'copied' ? 'Copied' : 'Copy command'}
                  </Button>
                </div>
              </div>
            </details>
          )}

          {selectedStrategy && (
            <RemediationSection
              description="Review dependency checks and warnings before creating the remediation run."
              eyebrow="Safety"
              title="Dependency checks"
              titleExplainer={<SectionTitleExplainer conceptId="dependency_checks" context="remediation" label="Dependency checks" />}
              tone={hasFailingChecks ? 'warning' : 'default'}
            >
              <div className="space-y-3">
                {selectedStrategy.dependency_checks.map((check) => (
                  <div key={check.code} className={remediationInsetClass('default')}>
                    <p className="text-sm text-text">
                      [{check.status}] <span className="font-mono">{check.code}</span>
                    </p>
                    <p className="mt-1 text-xs text-muted">{check.message}</p>
                  </div>
                ))}
                {failingChecks.length > 0 && (
                  <RemediationCallout title="Safety gate blocked" tone="danger">
                    {failingChecks.map((check) => (
                      <p key={`${check.code}-gate`} className="mt-1 text-sm text-danger">
                        {check.message}
                      </p>
                    ))}
                  </RemediationCallout>
                )}
                {selectedStrategy.warnings.map((warning, index) => (
                  <p key={`${selectedStrategy.strategy_id}-warning-${index}`} className="text-xs text-muted">
                    {warning}
                  </p>
                ))}
              </div>
            </RemediationSection>
          )}

          {mode === 'direct_fix' && (
            <RemediationSection
              description="Validate current state before approving the direct fix."
              eyebrow="Readiness"
              title="Pre-check result"
              titleExplainer={<SectionTitleExplainer conceptId="precheck_result" context="remediation" label="Pre-check result" />}
            >
              {!canRunDirectFix && (
                <p className="text-sm text-danger">
                  {isManualOnlyWorkflow
                    ? 'Direct fix is disabled for manual-only remediation.'
                    : 'Direct fix unavailable. Configure WriteRole or choose PR bundle mode.'}
                </p>
              )}
              {previewLoading && <p className="text-sm text-muted">Checking current state…</p>}
              {previewError && <p className="text-sm text-danger">{previewError}</p>}
              {preview && !previewLoading && <p className="text-sm text-text">{preview.message}</p>}
            </RemediationSection>
          )}

          {(previewDiffLines.length > 0 || (mode === 'pr_only' && (previewLoading || Boolean(previewError)))) && (
            <RemediationSection
              description="Preview the expected state transition before the run is created."
              eyebrow="Preview"
              title="Before / After simulation"
              titleExplainer={<SectionTitleExplainer conceptId="before_after_simulation" context="remediation" label="Before / After simulation" />}
            >
              {previewLoading && <p className="text-sm text-muted">Building state simulation…</p>}
              {previewError && <p className="text-sm text-danger">{previewError}</p>}
              {!previewLoading && !previewError && previewDiffLines.length > 0 && (
                <div className="space-y-2">
                  <div className="grid grid-cols-3 gap-2 text-[11px] uppercase tracking-wide text-muted">
                    <p>Change</p>
                    <p>Before</p>
                    <p>After</p>
                  </div>
                  {previewDiffLines.map((line, index) => {
                    const beforeValue = line.type === 'add' ? '—' : line.value;
                    const afterValue = line.type === 'remove' ? '—' : line.value;
                    const beforeClass =
                      line.type === 'remove'
                        ? 'text-danger'
                        : line.type === 'unchanged'
                          ? 'text-text'
                          : 'text-muted';
                    const afterClass =
                      line.type === 'add'
                        ? 'text-success'
                        : line.type === 'unchanged'
                          ? 'text-text'
                          : 'text-muted';
                    return (
                      <div
                        key={`${line.label}-${index}`}
                        className={remediationInsetClass('default', 'grid grid-cols-3 gap-2 text-xs')}
                      >
                        <p className="text-text">{line.label}</p>
                        <p className={beforeClass}>{beforeValue}</p>
                        <p className={afterClass}>{afterValue}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </RemediationSection>
          )}

          {selectedStrategy && previewResolution && !previewLoading && !previewError && (
            <RemediationSection
              description="This is the canonical resolver outcome for the current strategy, defaults, and runtime evidence."
              eyebrow="Resolver"
              title="Execution decision"
              titleExplainer={<SectionTitleExplainer conceptId="dependency_checks" context="remediation" label="Execution decision" />}
              tone={previewSupportTier?.tone === 'warning' ? 'warning' : 'default'}
            >
              <div className="space-y-4">
                <div className={remediationInsetClass('default', 'flex flex-wrap items-start justify-between gap-3')}>
                  <div className="space-y-2">
                    <p className="text-sm font-semibold text-text">Current support tier</p>
                    {previewSupportTier ? (
                      <>
                        <Badge variant={previewSupportTier.tone} className="w-fit">
                          {previewSupportTier.label}
                        </Badge>
                        <p className="text-xs text-muted">{previewSupportTier.description}</p>
                      </>
                    ) : (
                      <p className="text-xs font-mono text-text">{previewResolution.support_tier}</p>
                    )}
                  </div>
                  <div className="space-y-1 text-right">
                    <p className="text-xs text-muted">Profile</p>
                    <p className="text-xs font-mono text-text">{previewResolution.profile_id}</p>
                    <p className="pt-2 text-xs text-muted">
                      {previewSupportTier?.canonicalLabel || 'Support tier'}
                    </p>
                    <p className="text-xs font-mono text-text">{previewResolution.support_tier}</p>
                  </div>
                </div>

                <div className={remediationInsetClass(previewSupportTier?.tone === 'warning' ? 'warning' : 'info')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>Why the system chose this path</p>
                  <p className="mt-3 text-sm leading-7 text-text/78">{guidedReview.whyThisPath}</p>
                </div>

                <div className={remediationInsetClass('default')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>What must be preserved</p>
                  {guidedReview.preservationGroups.length > 0 ? (
                    <div className="mt-4 space-y-4">
                      {guidedReview.preservationGroups.map((group) => (
                        <div key={group.id} className="space-y-3">
                          <p className="text-sm font-semibold text-text">{group.title}</p>
                          <div className="grid gap-3 sm:grid-cols-2">
                            {group.entries.map((entry) => (
                              <div key={entry.key} className={remediationInsetClass('default', 'space-y-1')}>
                                <p className="text-xs text-muted">{entry.label}</p>
                                <p className="text-sm text-text break-words">{entry.value}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm leading-7 text-text/72">
                      No additional preservation constraints were recorded for this preview.
                    </p>
                  )}
                </div>

                <div className={remediationInsetClass('default')}>
                  <p className={REMEDIATION_EYEBROW_CLASS}>What you should check next</p>
                  <div className="mt-4 space-y-3">
                    {guidedReview.nextSteps.map((prompt) => (
                      <RemediationPromptRow
                        key={prompt.id}
                        title={prompt.label}
                        description={prompt.detail}
                        tone={prompt.tone}
                        action={prompt.settingsLink ? (
                          <Link
                            href={prompt.settingsLink.href}
                            className={buttonClassName({ variant: 'secondary', size: 'sm' })}
                          >
                            {prompt.settingsLink.label}
                          </Link>
                        ) : null}
                      />
                    ))}
                  </div>

                  {guidedReview.reviewChecklist.length > 0 && (
                    <div className="mt-5 space-y-3">
                      <p className="text-sm font-semibold text-text">Review checklist</p>
                      <div className="space-y-3">
                        {guidedReview.reviewChecklist.map((prompt) => (
                          <RemediationPromptRow
                            key={`checklist-${prompt.id}`}
                            title={prompt.label}
                            description={prompt.detail}
                            tone={prompt.tone}
                            action={prompt.settingsLink ? (
                              <Link
                                href={prompt.settingsLink.href}
                                className={buttonClassName({ variant: 'secondary', size: 'sm' })}
                              >
                                {prompt.settingsLink.label}
                              </Link>
                            ) : null}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </RemediationSection>
          )}

          {requiresRiskAck && !shouldUseExceptionFlow && (
            <label className={remediationCalloutClass('warning', 'flex cursor-pointer items-start gap-3')}>
              <input
                type="checkbox"
                checked={riskAcknowledged}
                onChange={(event) => setRiskAcknowledged(event.target.checked)}
                className="mt-0.5 h-4 w-4"
              />
              <span className="text-sm text-text">
                I reviewed dependency warnings/unknowns and accept remediation risk for this strategy.
              </span>
            </label>
          )}

          {cloudTrailCreateBucketMode && !shouldUseExceptionFlow && (
            <label className={remediationCalloutClass('warning', 'flex cursor-pointer items-start gap-3')}>
              <input
                type="checkbox"
                checked={bucketCreationAcknowledged}
                onChange={(event) => setBucketCreationAcknowledged(event.target.checked)}
                className="mt-0.5 h-4 w-4"
              />
              <span className="text-sm text-text">
                I approve creating a new S3 bucket and bucket policy for CloudTrail log delivery if the named bucket is missing.
              </span>
            </label>
          )}

          {selectedStrategy && !shouldUseExceptionFlow && (
            <RemediationCallout tone="info" title="Execution timing">
              <div className="flex flex-wrap items-center gap-2 text-sm text-text">
                <span className="inline-flex align-middle">
                  <SectionTitleExplainer conceptId="execution_timing" context="remediation" label="Execution timing" />
                </span>
                <span>Estimated time to Security Hub PASSED:{' '}</span>
                <span className="font-medium">{selectedStrategy.estimated_resolution_time || '12-24 hours'}</span>
              </div>
              {mode === 'direct_fix' &&
                canRunDirectFix &&
                selectedStrategy.supports_immediate_reeval === true && (
                  <label className="mt-3 flex cursor-pointer items-start gap-2 text-sm text-text">
                    <input
                      type="checkbox"
                      checked={triggerReevalAfterApply}
                      onChange={(event) => setTriggerReevalAfterApply(event.target.checked)}
                      className="mt-0.5 h-4 w-4"
                    />
                    <span>Trigger re-evaluation after apply</span>
                  </label>
                )}
            </RemediationCallout>
          )}

          {submitError && (
            <RemediationCallout description={submitError} title="Unable to continue" tone="danger" />
          )}

          <div className={remediationInsetClass('default', 'flex flex-col gap-3 sm:flex-row')}>
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              disabled={isSubmitting}
              className="flex-1"
            >
              Cancel
            </Button>
            <MajorActionButton
              type="button"
              onClick={handleSubmit}
              isLoading={isSubmitting}
              disabled={
                optionsLoading ||
                isPrOnlyBundleUnsupported ||
                isManualOnlyWorkflow ||
                (hasCatalogStrategies && !selectedStrategy) ||
                missingRequiredFields.length > 0 ||
                hasInputValidationErrors ||
                (selectedStrategy?.exception_only && exceptionReasonError !== null) ||
                (!shouldUseExceptionFlow && hasFailingChecks) ||
                (!shouldUseExceptionFlow && requiresRiskAck && !riskAcknowledged) ||
                (!shouldUseExceptionFlow && cloudTrailCreateBucketMode && !bucketCreationAcknowledged) ||
                (mode === 'direct_fix' && !canRunDirectFix)
              }
              className="flex-1"
            >
              {shouldUseExceptionFlow
                ? 'Create exception'
                : isSubmitting
                  ? 'Creating run…'
                  : isManualOnlyWorkflow
                    ? 'Manual remediation required'
                  : mode === 'direct_fix'
                    ? 'Approve & run'
                    : 'Generate PR bundle'}
            </MajorActionButton>
          </div>
        </>
      )}
    </div>
  );
}

export function RemediationModal({
  isOpen,
  onClose,
  actionId,
  actionTitle,
  actionType,
  accountId,
  region,
  mode,
  hasWriteRole,
  tenantId,
  onChooseException,
}: RemediationModalProps) {
  const [chromeState, setChromeState] = useState<RemediationWorkflowChromeState>(
    () => createDefaultChromeState(mode)
  );

  const handleClose = useCallback(() => {
    if (chromeState.preventClose) return;
    setChromeState(createDefaultChromeState(mode));
    onClose();
  }, [chromeState.preventClose, mode, onClose]);

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={chromeState.title}
      headerContent={chromeState.showProgress ? null : renderBlastRadiusBadge(chromeState.blastRadius)}
      size="xl"
      variant="dashboard"
    >
      <RemediationWorkflowContent
        isActive={isOpen}
        onClose={handleClose}
        actionId={actionId}
        actionTitle={actionTitle}
        actionType={actionType}
        accountId={accountId}
        region={region}
        mode={mode}
        hasWriteRole={hasWriteRole}
        tenantId={tenantId}
        onChooseException={onChooseException}
        onChromeStateChange={setChromeState}
      />
    </Modal>
  );
}
