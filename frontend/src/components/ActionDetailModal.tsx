"use client";

import {
  startTransition,
  useEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import { Button, buttonClassName } from "@/components/ui/Button";
import { MajorActionButton } from "@/components/ui/MajorActionButton";
import { AnimatedTooltip } from "@/components/ui/AnimatedTooltip";
import {
  REMEDIATION_DIALOG_BODY_CLASS,
  REMEDIATION_DIALOG_CLASS,
  REMEDIATION_DIALOG_HEADER_CLASS,
  REMEDIATION_EYEBROW_CLASS,
  RemediationPanel,
  remediationInsetClass,
  remediationPanelClass,
} from "@/components/ui/remediation-surface";
import {
  buildBusinessCriticalExplainer,
  buildBusinessImpactBadgeExplainer,
  buildRiskScoreExplainer,
  getBoundedDecisionViewExplainer,
} from "@/components/actionDetailExplainers";
import {
  Badge,
  getActionStatusBadgeVariant,
} from "@/components/ui/Badge";
import { ActionDetailAttackPathNodeCard } from "@/components/ActionDetailAttackPathNodeCard";
import { CreateExceptionWorkflowContent } from "@/components/CreateExceptionModal";
import {
  RemediationModal,
  RemediationWorkflowContent,
  type ExceptionSelectionPayload,
  type RemediationWorkflowChromeState,
} from "@/components/RemediationModal";
import { RemediationRunProgress } from "@/components/RemediationRunProgress";
import {
  buildAttackPathSummaryContext,
  type AttackPathSummaryContext,
} from "@/components/actionDetailAttackPath";
import { ActionDetailPriorityStoryboard } from "@/components/ActionDetailPriorityStoryboard";
import {
  getAction,
  getAccounts,
  createRootKeyRemediationRun,
  getRemediationOptions,
  listRemediationRuns,
  triggerActionReevaluation,
  triggerIngest,
  ActionAttackPathView,
  ActionDetail,
  ActionBusinessImpact,
  ActionImplementationArtifact,
  ActionThreatSignal,
  RemediationRunListItem,
  getErrorMessage,
  isApiError,
} from "@/lib/api";
import {
  CONTROL_FAMILY_TOOLTIP,
  getActionControlSummary,
  getReportedRulesLabel,
} from "@/lib/controlFamily";
import { useTenantId } from "@/lib/tenant";
import { useAuth } from "@/contexts/AuthContext";
import { useBackgroundJobs } from "@/contexts/BackgroundJobsContext";
import { cn } from "@/lib/utils";

const LEGACY_DIRECT_FIX_ACTION_TYPES = new Set([
  "s3_block_public_access",
  "enable_security_hub",
  "enable_guardduty",
  "ebs_default_encryption",
]);
const ROOT_ACCOUNT_REQUIRED_ACTION_TYPE = "iam_root_access_key_absent";
const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 20;
const ROOT_KEY_UI_FLAG =
  process.env.NEXT_PUBLIC_ROOT_KEY_REMEDIATION_UI_ENABLED;
const EXCEPTION_DURATION_OPTIONS = new Set([7, 14, 30, 90]);
const actionDetailCache = new Map<string, ActionDetail>();
const actionRunsCache = new Map<string, RemediationRunListItem[]>();
const directFixSupportCache = new Map<string, boolean>();
let cachedWriteRoleAccounts:
  | { account_id: string; role_write_arn: string | null }[]
  | null = null;

function isRootKeyUiEnabled(): boolean {
  const value = (ROOT_KEY_UI_FLAG ?? "").toLowerCase();
  return value === "true" || value === "1";
}

interface ActionDetailModalProps {
  actionId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

interface ActionDetailSuppressDefaults {
  initialExpiryDate?: string;
  initialReason?: string;
  introText?: string;
}

type ActionDetailSubview = "detail" | "pr_bundle" | "suppress";

function createDefaultPrBundleChrome(): RemediationWorkflowChromeState {
  return {
    blastRadius: null,
    preventClose: false,
    showProgress: false,
    title: "Generate PR Bundle",
  };
}

function createDefaultSuppressDefaults(): ActionDetailSuppressDefaults {
  return {
    initialExpiryDate: undefined,
    initialReason: undefined,
    introText: undefined,
  };
}

const overlayTransition = { duration: 0.4, ease: [0.32, 0.72, 0, 1] as const };
const modalTransition = {
  duration: 0.5,
  ease: [0.16, 1, 0.3, 1] as const, // Custom "out-quint" for a smooth pop-in
  scale: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const },
};

const HELP_BADGE_TRIGGER_CLASS =
  "cursor-help items-center gap-1 rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-info/40 after:inline-flex after:h-4 after:min-w-4 after:items-center after:justify-center after:rounded-full after:border after:border-info/35 after:px-1 after:text-[10px] after:font-semibold after:leading-none after:text-info/75 after:content-['?']";

const HELP_TEXT_TRIGGER_CLASS =
  "cursor-help items-center gap-1 rounded-md text-info/90 underline decoration-dotted decoration-info/55 underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-info/40 after:inline-flex after:h-4 after:min-w-4 after:items-center after:justify-center after:rounded-full after:border after:border-info/35 after:px-1 after:text-[10px] after:font-semibold after:leading-none after:text-info/75 after:content-['?']";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((element) => {
    if (element.getAttribute("aria-hidden") === "true") return false;
    if (element.tabIndex < 0) return false;
    if (
      element.offsetParent === null &&
      getComputedStyle(element).position !== "fixed"
    )
      return false;
    return true;
  });
}

function formatDate(dateString: string | null) {
  if (!dateString) return "—";
  return new Date(dateString).toLocaleString();
}

function formatSyncValue(value: string | null | undefined): string {
  if (!value) return "Not available";
  return value.replace(/_/g, " ");
}

function getExternalSyncBadgeVariant(
  status: string | null | undefined,
): "default" | "success" | "warning" | "danger" | "info" {
  if (status === "in_sync") return "success";
  if (status === "drifted") return "warning";
  if (status === "failed") return "danger";
  if (status) return "info";
  return "default";
}

function getAssigneeSyncBadgeVariant(
  status: string,
): "default" | "success" | "warning" | "danger" | "info" {
  if (status === "verified") return "success";
  if (status === "unverified") return "warning";
  if (status === "unsupported") return "default";
  return "info";
}

function formatSyncEventLabel(eventType: string): string {
  return eventType.replace(/_/g, " ");
}

function attackPathLinkClassName(): string {
  return buttonClassName({
    variant: "accent",
    size: "md",
    className:
      "group min-h-11 border-danger/28 bg-danger/12 text-danger shadow-[0_18px_36px_-24px_rgba(184,48,72,0.75)] hover:bg-danger/18 hover:text-danger",
  });
}

function withTenantQuery(path: string, tenantId?: string): string {
  if (!tenantId || !path.startsWith("/")) return path;
  const [pathname, hash] = path.split("#", 2);
  const params = new URLSearchParams();
  params.set("tenant_id", tenantId);
  return `${pathname}?${params.toString()}${hash ? `#${hash}` : ""}`;
}

function getArtifactMetaSummary(
  artifact: ActionImplementationArtifact,
): string | null {
  const metadata = artifact.metadata ?? {};
  if (artifact.kind === "bundle") {
    const formatName =
      typeof metadata.format === "string" ? metadata.format : null;
    const fileCount =
      typeof metadata.file_count === "number" &&
      Number.isFinite(metadata.file_count)
        ? metadata.file_count
        : null;
    if (formatName && fileCount !== null) {
      return `${formatName} · ${fileCount} file${fileCount === 1 ? "" : "s"}`;
    }
  }
  if (artifact.kind === "change_summary") {
    const changeCount =
      typeof metadata.change_count === "number" &&
      Number.isFinite(metadata.change_count)
        ? metadata.change_count
        : null;
    const appliedBy =
      typeof metadata.applied_by === "string" ? metadata.applied_by : null;
    if (changeCount !== null && appliedBy) {
      return `${changeCount} change${changeCount === 1 ? "" : "s"} · ${appliedBy}`;
    }
  }
  if (artifact.kind === "direct_fix") {
    const postCheckPassed = metadata.post_check_passed === true;
    const logCount =
      typeof metadata.log_count === "number" &&
      Number.isFinite(metadata.log_count)
        ? metadata.log_count
        : null;
    if (logCount !== null) {
      return `${postCheckPassed ? "post-check passed" : "post-check pending"} · ${logCount} log line${logCount === 1 ? "" : "s"}`;
    }
  }
  return null;
}

function getGraphAvailabilityMessage(reason?: string | null): string {
  if (reason === "relationship_context_unavailable") {
    return "Relationship context is missing or low-confidence for this action.";
  }
  return "Persisted graph inputs are not available for this action yet.";
}

function getGraphRelationshipLabel(relationship: string): string {
  if (relationship === "anchor") return "Anchor";
  if (relationship === "linked_resource") return "Linked resource";
  if (relationship === "account_support") return "Account support";
  if (relationship === "inventory_support") return "Inventory support";
  return relationship.replace(/_/g, " ");
}

function isImmediateReevaluationUnsupported(error: unknown): boolean {
  if (!isApiError(error) || error.status !== 400) return false;
  if (typeof error.detail === "string") {
    return error.detail.includes("Immediate re-evaluation not supported");
  }
  if (typeof error.detail === "object" && error.detail !== null) {
    const detail = error.detail as Record<string, unknown>;
    return detail.error === "Immediate re-evaluation not supported";
  }
  return false;
}

function getAttackPathStatusVariant(
  status: ActionAttackPathView["status"],
): "success" | "warning" | "info" {
  if (status === "available") return "success";
  if (status === "partial") return "warning";
  return "info";
}

function getAttackPathStatusTooltip(
  view: ActionAttackPathView,
): string | undefined {
  if (view.status !== "partial") return undefined;
  if (view.availability_reason === "bounded_context_truncated") {
    return "Take care: Extra graph context was capped to keep this view bounded.";
  }
  if (view.availability_reason === "entry_point_unresolved") {
    return "Take care: A concrete entry point could not be fully resolved.";
  }
  if (view.availability_reason === "target_assets_unresolved") {
    return "Take care: The target asset could not be fully resolved.";
  }
  return "Take care: This attack story is not fully resolved yet.";
}

function getAttackPathAvailabilityMessage(view: ActionAttackPathView): string {
  if (view.status === "context_incomplete") {
    return "Relationship context is incomplete, so this story stays fail-closed and bounded.";
  }
  if (
    view.status === "partial" &&
    view.availability_reason === "bounded_context_truncated"
  ) {
    return "This view was intentionally truncated to keep traversal bounded.";
  }
  if (
    view.status === "partial" &&
    view.availability_reason === "entry_point_unresolved"
  ) {
    return "A concrete entry point could not be resolved from the bounded context.";
  }
  if (
    view.status === "partial" &&
    view.availability_reason === "target_assets_unresolved"
  ) {
    return "Target reachability could not be fully resolved from the bounded context.";
  }
  if (view.availability_reason === "relationship_context_unavailable") {
    return "Relationship context is missing or low-confidence for this action.";
  }
  return "Attack-path context is not fully available for this action yet.";
}

interface AttackPathSummaryToken {
  className: string;
  value: string;
}

interface AttackPathSummarySegment {
  className?: string;
  text: string;
}

function buildAttackPathSummaryTokens(
  context: AttackPathSummaryContext | null,
): AttackPathSummaryToken[] {
  if (!context) return [];
  return [
    context.targetLabel
      ? {
          value: context.targetLabel,
          className:
            "rounded-lg border border-danger/10 bg-danger/5 px-2 py-0.5 font-mono text-[0.95em] text-text",
        }
      : null,
    context.impactLabel
      ? { value: context.impactLabel, className: "font-semibold text-text" }
      : null,
    context.nextStepLabel
      ? {
          value: `Safest next step: ${context.nextStepLabel}`,
          className: "font-semibold text-danger/90",
        }
      : null,
  ].filter((token): token is AttackPathSummaryToken => Boolean(token));
}

function splitAttackPathSummary(
  summary: string,
  tokens: AttackPathSummaryToken[],
): AttackPathSummarySegment[] {
  const segments: AttackPathSummarySegment[] = [];
  let cursor = 0;
  for (const token of tokens) {
    const index = summary.indexOf(token.value, cursor);
    if (index < 0) continue;
    if (index > cursor) segments.push({ text: summary.slice(cursor, index) });
    segments.push({ text: token.value, className: token.className });
    cursor = index + token.value.length;
  }
  if (cursor < summary.length) segments.push({ text: summary.slice(cursor) });
  return segments.length ? segments : [{ text: summary }];
}

function renderAttackPathSummary(
  summary: string,
  context: AttackPathSummaryContext | null,
): ReactNode {
  const tokens = buildAttackPathSummaryTokens(context);
  return splitAttackPathSummary(summary, tokens).map((segment, index) => (
    <span key={`${segment.text}-${index}`} className={segment.className}>
      {segment.text}
    </span>
  ));
}

function titleCaseToken(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatBusinessImpactLabel(impact: ActionBusinessImpact): string {
  const risk = titleCaseToken(impact.technical_risk_tier);
  const criticality = titleCaseToken(impact.criticality.tier);
  return `${risk} risk x ${criticality} criticality`;
}

function businessImpactBadgeVariant(
  impact: ActionBusinessImpact,
): "danger" | "warning" | "info" {
  if (
    impact.technical_risk_tier === "critical" ||
    impact.technical_risk_tier === "high"
  ) {
    return impact.criticality.status === "unknown" ? "warning" : "danger";
  }
  return "info";
}

function getThreatSignals(action: ActionDetail | null): ActionThreatSignal[] {
  const signals =
    action?.score_components?.exploit_signals?.applied_threat_signals;
  return Array.isArray(signals) ? signals : [];
}

function formatThreatSource(signal: ActionThreatSignal): string {
  const sourceLabel =
    typeof signal.source_label === "string" ? signal.source_label.trim() : "";
  return sourceLabel || titleCaseToken(signal.source);
}

function formatThreatMetric(
  label: string,
  value: string | number | null | undefined,
): string | null {
  if (value === null || value === undefined || value === "") return null;
  return `${label} ${value}`;
}

function parseExceptionDurationDays(value: unknown): number | undefined {
  if (
    typeof value === "number" &&
    Number.isFinite(value) &&
    EXCEPTION_DURATION_OPTIONS.has(value)
  ) {
    return value;
  }
  if (typeof value === "string") {
    const cleaned = value.trim();
    if (!cleaned) return undefined;
    const parsed = Number(cleaned);
    if (Number.isFinite(parsed) && EXCEPTION_DURATION_OPTIONS.has(parsed)) {
      return parsed;
    }
  }
  return undefined;
}

function expiryDateFromDurationDays(days: number): string {
  const next = new Date();
  next.setDate(next.getDate() + days);
  return next.toISOString().split("T")[0];
}

export function ActionDetailModal({
  actionId,
  isOpen,
  onClose,
}: ActionDetailModalProps) {
  const router = useRouter();
  const modalRef = useRef<HTMLDivElement | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  const { tenantId } = useTenantId();
  const { isAuthenticated, user } = useAuth();
  const { addJob, updateJob, completeJob, failJob } = useBackgroundJobs();

  const [action, setAction] = useState<ActionDetail | null>(null);
  const [accounts, setAccounts] = useState<
    { account_id: string; role_write_arn: string | null }[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recomputeLoading, setRecomputeLoading] = useState(false);
  const [recomputeSuccess, setRecomputeSuccess] = useState<string | null>(null);
  const [actionSubview, setActionSubview] =
    useState<ActionDetailSubview>("detail");
  const [prBundleChrome, setPrBundleChrome] =
    useState<RemediationWorkflowChromeState>(createDefaultPrBundleChrome);
  const [suppressDefaults, setSuppressDefaults] =
    useState<ActionDetailSuppressDefaults>(createDefaultSuppressDefaults);
  const [suppressPreventClose, setSuppressPreventClose] = useState(false);
  const [remediationModalMode, setRemediationModalMode] = useState<
    "direct_fix" | null
  >(null);
  const [portalContainer, setPortalContainer] = useState<HTMLElement | null>(
    null,
  );
  const [runs, setRuns] = useState<RemediationRunListItem[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [supportsDirectFixMode, setSupportsDirectFixMode] = useState(false);
  const [hasVisitedSuppressView, setHasVisitedSuppressView] = useState(false);
  const [rootLifecycleStarting, setRootLifecycleStarting] = useState(false);
  const [rootLifecycleError, setRootLifecycleError] = useState<string | null>(
    null,
  );

  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const showContent = isAuthenticated || tenantId;

  const hasWriteRole = useMemo(
    () =>
      Boolean(
        action &&
          accounts.some(
            (a) => a.account_id === action.account_id && a.role_write_arn,
          ),
      ),
    [accounts, action],
  );
  const canRunDirectFix = useMemo(
    () =>
      Boolean(
        action &&
          (supportsDirectFixMode ||
            LEGACY_DIRECT_FIX_ACTION_TYPES.has(action.action_type)),
      ),
    [action, supportsDirectFixMode],
  );
  const hasLinkedFindings = action ? action.findings.length > 0 : false;
  const isPrOnlyAction = action?.action_type === "pr_only";
  const showMissingWriteRoleHelper = Boolean(canRunDirectFix && !hasWriteRole);
  const requiresRootAccount =
    action?.action_type === ROOT_ACCOUNT_REQUIRED_ACTION_TYPE;
  const isAdminUser = user?.role === "admin";
  const rootKeyUiEnabled = isRootKeyUiEnabled();
  const implementationArtifacts = action?.implementation_artifacts ?? [];
  const jiraExternalSync = useMemo(
    () => (action?.external_sync ?? []).filter((item) => item.provider === "jira"),
    [action?.external_sync],
  );
  const graphContext = action?.graph_context;
  const attackPathView = action?.attack_path_view;
  const controlSummary = getActionControlSummary(
    action?.control_family,
    action?.control_id,
  );
  const reportedRulesLabel = getReportedRulesLabel(
    action?.control_family,
    action?.control_id,
  );
  const remediationFamilyLabel =
    action?.control_family?.canonical_control_id ?? action?.control_id ?? "N/A";
  const attackPathSummaryContext = useMemo(
    () =>
      action && attackPathView
        ? buildAttackPathSummaryContext(action, attackPathView, graphContext)
        : null,
    [action, attackPathView, graphContext],
  );
  const summaryMentionsNextStep = Boolean(
    attackPathView &&
    attackPathSummaryContext?.nextStepLabel &&
    attackPathView.summary.includes(attackPathSummaryContext.nextStepLabel),
  );
  const summaryMentionsImpact = Boolean(
    attackPathView &&
    attackPathSummaryContext?.impactLabel &&
    attackPathView.summary.includes(attackPathSummaryContext.impactLabel),
  );
  const showAttackPathCautionLine = Boolean(
    attackPathSummaryContext?.cautionDetail &&
    attackPathView?.status !== "partial",
  );
  const showAttackPathNextStepLine = Boolean(
    attackPathSummaryContext?.nextStepLabel && !summaryMentionsNextStep,
  );
  const showAttackPathImpactLine = Boolean(
    attackPathSummaryContext?.impactLabel && !summaryMentionsImpact,
  );
  const scoreFactors = useMemo(() => action?.score_factors ?? [], [action]);
  const threatSignals = useMemo(() => getThreatSignals(action), [action]);
  const hasActiveThreatSignals = useMemo(
    () => threatSignals.some((signal) => (signal.applied_points ?? 0) > 0),
    [threatSignals],
  );
  const isBusinessCriticalAction =
    action?.business_impact.criticality.tier === "critical" ||
    action?.business_impact.criticality.tier === "high";
  const showContextIncompleteBadge =
    attackPathView?.status === "context_incomplete" ||
    action?.context_incomplete;
  const activeSubviewPreventClose =
    actionSubview === "pr_bundle"
      ? prBundleChrome.preventClose
      : actionSubview === "suppress"
        ? suppressPreventClose
        : false;
  const activeSubviewTitle =
    actionSubview === "pr_bundle"
      ? prBundleChrome.title
      : actionSubview === "suppress"
        ? "Suppress Action"
        : "Action Detail";

  const handleActionDetailClose = useCallback(() => {
    if (activeSubviewPreventClose) return;
    onClose();
  }, [activeSubviewPreventClose, onClose]);

  // --- Keyboard Accessibility & Focus Lock ---
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleActionDetailClose();
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "";
    };
  }, [handleActionDetailClose, isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const frame = window.requestAnimationFrame(() => {
      const modalElement = modalRef.current;
      if (!modalElement) return;

      const focusableElements = getFocusableElements(modalElement);
      const firstNonCloseFocusable = focusableElements.find(
        (element) => element !== closeButtonRef.current,
      );
      const initialFocusTarget =
        firstNonCloseFocusable ??
        closeButtonRef.current ??
        focusableElements[0] ??
        modalElement;
      initialFocusTarget.focus();
    });

    return () => window.cancelAnimationFrame(frame);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;

    const modalElement = modalRef.current;
    if (!modalElement) return;

    const handleTabKey = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;

      const focusableElements = getFocusableElements(modalElement);
      if (focusableElements.length === 0) {
        event.preventDefault();
        modalElement.focus();
        return;
      }

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement as HTMLElement | null;

      if (!activeElement || !modalElement.contains(activeElement)) {
        event.preventDefault();
        firstElement.focus();
        return;
      }

      if (event.shiftKey && activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
        return;
      }

      if (!event.shiftKey && activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    };

    modalElement.addEventListener("keydown", handleTabKey);
    return () => {
      modalElement.removeEventListener("keydown", handleTabKey);
    };
  }, [isOpen]);

  useEffect(() => {
    setPortalContainer(document.body);
    return () => setPortalContainer(null);
  }, []);

  const openSuppressView = (opts?: {
    initialReason?: string;
    introText?: string;
    initialExpiryDate?: string;
  }) => {
    setSuppressDefaults({
      initialExpiryDate: opts?.initialExpiryDate,
      initialReason: opts?.initialReason,
      introText: opts?.introText,
    });
    setHasVisitedSuppressView(true);
    setSuppressPreventClose(false);
    startTransition(() => {
      setActionSubview("suppress");
    });
  };

  const fetchAction = useCallback(async (opts?: { background?: boolean }) => {
    if (!actionId || (!isAuthenticated && !tenantId)) {
      setAction(null);
      return;
    }
    const cached = actionDetailCache.get(actionId);
    if (cached) {
      setAction(cached);
    }
    if (!opts?.background || !cached) {
      setIsLoading(!cached);
    }
    setError(null);
    try {
      const response = await getAction(actionId, effectiveTenantId);
      actionDetailCache.set(actionId, response);
      setAction(response);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [actionId, effectiveTenantId, isAuthenticated, tenantId]);

  useEffect(() => {
    if (isOpen) {
      void fetchAction();
    } else {
      // Keep state until animation finishes
      const timeout = setTimeout(() => {
        setAction(null);
        setError(null);
        setRecomputeSuccess(null);
        setActionSubview("detail");
        setPrBundleChrome(createDefaultPrBundleChrome());
        setSuppressDefaults(createDefaultSuppressDefaults());
        setSuppressPreventClose(false);
        setHasVisitedSuppressView(false);
      }, 500);
      return () => clearTimeout(timeout);
    }
  }, [isOpen, fetchAction]);

  useEffect(() => {
    if (!isOpen) return;
    const cachedAction = actionId ? actionDetailCache.get(actionId) ?? null : null;
    setAction(cachedAction);
    setRuns(cachedAction ? actionRunsCache.get(cachedAction.id) ?? [] : []);
    setActionSubview("detail");
    setPrBundleChrome(createDefaultPrBundleChrome());
    setSuppressDefaults(createDefaultSuppressDefaults());
    setSuppressPreventClose(false);
    setHasVisitedSuppressView(false);
  }, [actionId, isOpen]);

  useEffect(() => {
    if (!showContent || !isOpen) return;
    if (!canRunDirectFix) return;
    if (cachedWriteRoleAccounts) {
      setAccounts(cachedWriteRoleAccounts);
      return;
    }
    getAccounts(effectiveTenantId)
      .then((list) => {
        const normalized = list.map((a) => ({
          account_id: a.account_id,
          role_write_arn: a.role_write_arn,
        }));
        cachedWriteRoleAccounts = normalized;
        setAccounts(normalized);
      })
      .catch(() => setAccounts([]));
  }, [canRunDirectFix, effectiveTenantId, isOpen, showContent]);

  const fetchRuns = useCallback(() => {
    if (!action?.id || !showContent || !isOpen) return;
    const cachedRuns = actionRunsCache.get(action.id);
    if (cachedRuns) {
      setRuns(cachedRuns);
    }
    setRunsLoading(!cachedRuns);
    listRemediationRuns(
      { action_id: action.id, include_group_related: true, limit: 10 },
      effectiveTenantId,
    )
      .then((res) => {
        actionRunsCache.set(action.id, res.items);
        setRuns(res.items);
      })
      .catch(() => setRuns([]))
      .finally(() => setRunsLoading(false));
  }, [action?.id, showContent, effectiveTenantId, isOpen]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const handleExitPrBundleView = useCallback(() => {
    if (prBundleChrome.preventClose) return;
    startTransition(() => {
      setActionSubview("detail");
    });
    setPrBundleChrome(createDefaultPrBundleChrome());
    fetchRuns();
  }, [fetchRuns, prBundleChrome.preventClose]);

  const handleExitSuppressView = useCallback(() => {
    if (suppressPreventClose) return;
    startTransition(() => {
      setActionSubview("detail");
    });
    setSuppressPreventClose(false);
  }, [suppressPreventClose]);

  useEffect(() => {
    if (!action || !showContent || !isOpen) {
      setSupportsDirectFixMode(false);
      return;
    }

    const cachedSupport = directFixSupportCache.get(action.id);
    if (cachedSupport !== undefined) {
      setSupportsDirectFixMode(cachedSupport);
      return;
    }

    let cancelled = false;
    getRemediationOptions(action.id, effectiveTenantId)
      .then((options) => {
        if (cancelled) return;
        const supportsDirectFix = options.mode_options.includes("direct_fix");
        directFixSupportCache.set(action.id, supportsDirectFix);
        setSupportsDirectFixMode(supportsDirectFix);
      })
      .catch(() => {
        if (cancelled) return;
        const supportsDirectFix = LEGACY_DIRECT_FIX_ACTION_TYPES.has(
          action.action_type,
        );
        directFixSupportCache.set(action.id, supportsDirectFix);
        setSupportsDirectFixMode(supportsDirectFix);
      });

    return () => {
      cancelled = true;
    };
  }, [action, showContent, effectiveTenantId, isOpen]);

  useEffect(() => {
    if (!recomputeSuccess) return;
    const timeout = setTimeout(() => setRecomputeSuccess(null), 5000);
    return () => clearTimeout(timeout);
  }, [recomputeSuccess]);

  const monitorActionDetailRecomputeJob = async (
    jobId: string,
    baselineStatus: string,
    baselineUpdatedAt: string,
  ) => {
    if (!actionId) return;
    try {
      let changed = false;
      for (let attempt = 1; attempt <= MAX_POLL_ATTEMPTS; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
        const current = await getAction(actionId, effectiveTenantId);
        actionDetailCache.set(actionId, current);
        setAction(current);
        if (
          current.status !== baselineStatus ||
          (current.updated_at ?? "") !== baselineUpdatedAt
        ) {
          changed = true;
          break;
        }
        updateJob(jobId, {
          progress: Math.min(
            92,
            30 + Math.floor((attempt / MAX_POLL_ATTEMPTS) * 62),
          ),
          message: "Waiting for updated action details…",
        });
      }

      if (changed) {
        completeJob(
          jobId,
          "Action details updated.",
          "Latest action refresh results are now visible.",
        );
      } else {
        completeJob(
          jobId,
          "Action refresh completed.",
          "No visible changes yet. Downstream refresh processing may still be finishing.",
        );
      }
      setRecomputeSuccess(
        "Refresh complete — check the finding status below to confirm resolution.",
      );
    } catch (err) {
      failJob(jobId, "Action refresh failed.", getErrorMessage(err));
    }
  };

  const handleRecompute = async () => {
    if (!actionId || !action) return;
    setRecomputeLoading(true);
    setRecomputeSuccess(null);
    setError(null);
    const jobId = addJob({
      type: "actions",
      title: `Refreshing action state (${actionId})`,
      message: "Queuing targeted action refresh…",
      progress: 10,
      dedupeKey: `action-refresh:${effectiveTenantId ?? "session"}:${actionId}`,
      resourceId: actionId,
      actorId: effectiveTenantId ?? "session",
    });
    try {
      const baselineStatus = action?.status ?? "";
      const baselineUpdatedAt = action?.updated_at ?? "";
      try {
        await triggerActionReevaluation(actionId, effectiveTenantId);
        updateJob(jobId, {
          progress: 30,
          message: "Waiting for updated action details…",
        });
      } catch (err) {
        if (!isImmediateReevaluationUnsupported(err)) {
          throw err;
        }
        await triggerIngest(
          action.account_id,
          effectiveTenantId,
          action.region ? [action.region] : undefined,
        );
        updateJob(jobId, {
          progress: 30,
          message: "Waiting for updated action details…",
        });
      }
      void monitorActionDetailRecomputeJob(
        jobId,
        baselineStatus,
        baselineUpdatedAt,
      );
    } catch (err) {
      const message = getErrorMessage(err);
      setError(message);
      failJob(jobId, "Action recompute failed.", message);
    } finally {
      setRecomputeLoading(false);
    }
  };

  const exceptionDefaultsForStrategy = (
    strategyId: string,
  ): { initialReason: string; introText: string } => {
    if (strategyId === "s3_keep_public_exception") {
      return {
        initialReason:
          "Bucket is intentionally public for an approved use-case. Risk accepted with compensating controls and periodic review.",
        introText:
          "This bucket is intentionally public. Create an exception and document approval, compensating controls, and review cadence.",
      };
    }
    if (strategyId === "s3_keep_non_ssl_exception") {
      return {
        initialReason:
          "Non-SSL S3 access is temporarily required for a legacy integration. Risk accepted with migration plan and review date.",
        introText:
          "This strategy keeps non-SSL S3 access. Create an exception with owner, migration timeline, and compensating controls.",
      };
    }
    if (strategyId === "config_keep_exception") {
      return {
        initialReason:
          "AWS Config remains disabled due approved operational constraints. Risk accepted with temporary compensating controls.",
        introText:
          "This strategy keeps AWS Config disabled. Create an exception and include approval, impact, and target remediation date.",
      };
    }
    if (strategyId === "ssm_keep_public_sharing_exception") {
      return {
        initialReason:
          "Public SSM document sharing is temporarily required for approved operational needs. Risk accepted with controls.",
        introText:
          "This strategy keeps public SSM document sharing enabled. Create an exception with business approval and expiration date.",
      };
    }
    if (strategyId === "snapshot_keep_sharing_exception") {
      return {
        initialReason:
          "Public snapshot sharing is required for a validated use-case. Risk accepted with monitoring and expiration date.",
        introText:
          "This strategy keeps snapshot sharing public. Create an exception with explicit approval and rollback plan.",
      };
    }
    if (strategyId === "iam_root_key_keep_exception") {
      return {
        initialReason:
          "Root access key is temporarily retained for controlled break-glass use. Risk accepted with strict compensating controls.",
        introText:
          "This strategy retains an IAM root access key. Create an exception with owner, safeguards, and review deadline.",
      };
    }
    return {
      initialReason: `Exception approved for remediation strategy ${strategyId} on action "${action?.title ?? "selected action"}".`,
      introText: `This strategy keeps the current risk posture for "${action?.title ?? "selected action"}". Record approval, controls, and expiry.`,
    };
  };

  const exceptionDefaultsForSelection = (
    selection: ExceptionSelectionPayload,
  ): {
    initialReason: string;
    introText: string;
    initialExpiryDate?: string;
  } => {
    const defaults = exceptionDefaultsForStrategy(
      selection.strategy.strategy_id,
    );
    const rawReason = selection.strategyInputs.exception_reason;
    const reason = typeof rawReason === "string" ? rawReason.trim() : "";
    const durationDays = parseExceptionDurationDays(
      selection.strategyInputs.exception_duration_days,
    );
    return {
      initialReason: reason || defaults.initialReason,
      introText: defaults.introText,
      initialExpiryDate: durationDays
        ? expiryDateFromDurationDays(durationDays)
        : undefined,
    };
  };

  const handleStartRootLifecycle = async () => {
    if (!action || !isAuthenticated) return;
    setRootLifecycleError(null);
    setRootLifecycleStarting(true);
    try {
      const firstFindingId = action.findings[0]?.id;
      const response = await createRootKeyRemediationRun(
        {
          action_id: action.id,
          finding_id: firstFindingId ?? undefined,
          mode: "manual",
          strategy_id: "iam_root_key_disable",
        },
        { tenantId: effectiveTenantId },
      );
      onClose();
      router.push(`/root-key-remediation-runs/${response.run.id}`);
    } catch (err) {
      setRootLifecycleError(getErrorMessage(err));
    } finally {
      setRootLifecycleStarting(false);
    }
  };

  const modalContent = (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 lg:p-8">
          <motion.div
            className="absolute inset-0 bg-black/60 backdrop-blur-md"
            onClick={handleActionDetailClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={overlayTransition}
          />

          <motion.div
            ref={modalRef}
            className={cn(
              "relative flex w-full max-w-[88rem] max-h-[90vh] flex-col overflow-hidden",
              REMEDIATION_DIALOG_CLASS,
            )}
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            tabIndex={-1}
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={modalTransition}
            style={{
              boxShadow:
                "0 25px 50px -12px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1)",
              }}
            >
            {/* Header */}
            <div
              className={cn(
                "sticky top-0 z-10 shrink-0 flex items-center justify-between",
                REMEDIATION_DIALOG_HEADER_CLASS,
              )}
            >
              <div className="flex min-w-0 flex-1 items-center gap-4">
                {actionSubview !== "detail" && (
                  <button
                    type="button"
                    onClick={
                      actionSubview === "pr_bundle"
                        ? handleExitPrBundleView
                        : handleExitSuppressView
                    }
                    disabled={activeSubviewPreventClose}
                    className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-border/55 bg-bg/70 text-text transition-all hover:border-accent/25 hover:bg-bg disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label="Back to action detail"
                  >
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M15.75 19.5L8.25 12l7.5-7.5"
                      />
                    </svg>
                  </button>
                )}
                <div className="flex min-w-0 flex-1 flex-col">
                  <div className="flex min-w-0 flex-wrap items-center gap-3">
                    <h2
                      id="modal-title"
                      className="text-xl font-bold text-text leading-tight tracking-tight"
                    >
                      {activeSubviewTitle}
                    </h2>
                    {actionSubview === "pr_bundle" &&
                      !prBundleChrome.showProgress &&
                      prBundleChrome.blastRadius && (
                        <span
                          data-testid="action-detail-pr-bundle-badge"
                          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${prBundleChrome.blastRadius.badgeClass}`}
                          title={prBundleChrome.blastRadius.tooltip}
                        >
                          {prBundleChrome.blastRadius.label}
                        </span>
                      )}
                  </div>
                  {action && (
                    <p
                      className="mt-1 truncate text-sm text-muted opacity-70"
                      title={action.title}
                    >
                      {action.title}
                    </p>
                  )}
                </div>
              </div>
              <button
                ref={closeButtonRef}
                onClick={handleActionDetailClose}
                className="ml-4 shrink-0 rounded-2xl border border-border/55 bg-bg/70 p-2 text-muted transition-all hover:border-accent/25 hover:bg-bg hover:text-text"
                aria-label="Close modal"
                disabled={activeSubviewPreventClose}
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Scrollable Content */}
            <div className={cn("custom-scrollbar flex-1", REMEDIATION_DIALOG_BODY_CLASS)}>
              {!action && isLoading && (
                <div className="space-y-6 pt-2">
                  <div className={remediationPanelClass("default", "animate-pulse p-8")}>
                    <div className="mb-6 h-10 w-3/4 rounded-xl bg-bg/70" />
                    <div className="flex gap-3 mb-6">
                      <div className="h-8 w-24 rounded-full bg-bg/70" />
                      <div className="h-8 w-24 rounded-full bg-bg/70" />
                      <div className="h-8 w-24 rounded-full bg-bg/70" />
                    </div>
                    <div className="space-y-3">
                      <div className="h-4 w-full rounded-full bg-bg/70" />
                      <div className="h-4 w-5/6 rounded-full bg-bg/70" />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-6">
                    <div className={remediationPanelClass("default", "h-32 animate-pulse")} />
                    <div className={remediationPanelClass("default", "h-32 animate-pulse")} />
                  </div>
                </div>
              )}

              {error && (
                <div className="p-6 bg-danger/10 border border-danger/20 rounded-3xl mb-8 flex flex-col items-center text-center">
                  <svg
                    className="w-12 h-12 text-danger mb-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                    />
                  </svg>
                  <h3 className="text-lg font-semibold text-danger mb-2">
                    Failed to load action
                  </h3>
                  <p className="text-sm text-danger/80 mb-6">{error}</p>
                  <Button
                    variant="secondary"
                    onClick={() => void fetchAction()}
                    className="nm-neu-sm"
                  >
                    Retry Connection
                  </Button>
                </div>
              )}

              {recomputeSuccess && (
                <div className="p-4 bg-success/20 border border-success/30 rounded-2xl mb-8 flex items-center gap-3">
                  <svg
                    className="w-5 h-5 text-success shrink-0"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <p className="text-sm font-medium text-success">
                    {recomputeSuccess}
                  </p>
                </div>
              )}

              {action && actionSubview === "pr_bundle" && (
                <div className="pb-4" data-testid="action-detail-pr-bundle-view">
                  <RemediationWorkflowContent
                    isActive={true}
                    onClose={handleExitPrBundleView}
                    actionId={action.id}
                    actionTitle={action.title}
                    actionType={action.action_type}
                    accountId={action.account_id}
                    region={action.region}
                    mode="pr_only"
                    hasWriteRole={!!hasWriteRole}
                    tenantId={effectiveTenantId}
                    onChooseException={(selection) => {
                      setPrBundleChrome(createDefaultPrBundleChrome());
                      openSuppressView(exceptionDefaultsForSelection(selection));
                    }}
                    onChromeStateChange={setPrBundleChrome}
                  />
                </div>
              )}

              {action && hasVisitedSuppressView && (
                <div
                  className={cn(
                    "mx-auto w-full max-w-3xl pb-4",
                    actionSubview === "suppress" ? "block" : "hidden",
                  )}
                  data-testid={
                    actionSubview === "suppress"
                      ? "action-detail-suppress-view"
                      : undefined
                  }
                >
                  <CreateExceptionWorkflowContent
                    key={`${action.id}-${suppressDefaults.initialReason ?? ""}-${suppressDefaults.initialExpiryDate ?? ""}`}
                    onClose={handleExitSuppressView}
                    entityType="action"
                    entityId={action.id}
                    onSuccess={(payload) => {
                      setAction((current) =>
                        current
                          ? {
                              ...current,
                              exception_id: current.exception_id ?? "pending-exception",
                              exception_expires_at: payload.expires_at,
                              exception_expired: false,
                            }
                          : current,
                      );
                      void fetchAction({ background: true });
                    }}
                    tenantId={effectiveTenantId}
                    initialReason={suppressDefaults.initialReason}
                    introText={suppressDefaults.introText}
                    initialExpiryDate={suppressDefaults.initialExpiryDate}
                    onBusyChange={setSuppressPreventClose}
                  />
                </div>
              )}

              {action && actionSubview === "detail" && (
                <div className="space-y-8 pb-4">
                  {/* Main Info Card */}
                  <RemediationPanel className="p-8" tone="accent">
                    <div className="mb-8 flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
                      <div className="flex-1 space-y-5">
                        <div className="space-y-3">
                          <p className={REMEDIATION_EYEBROW_CLASS}>Action detail</p>
                          <h1 className="text-2xl font-bold leading-tight text-text xl:text-[2rem]">
                            {action.title}
                          </h1>
                          {action.description && (
                            <p className="max-w-3xl text-sm leading-7 text-text/74">
                              {action.description}
                            </p>
                          )}
                        </div>

                        <div
                          className={remediationInsetClass(
                            "default",
                            "inline-flex flex-wrap items-center gap-2 px-3 py-3",
                          )}
                        >
                          <Badge
                            variant={getActionStatusBadgeVariant(action.status)}
                            className="bg-[var(--card)]/88"
                          >
                            {action.status.replace("_", " ")}
                          </Badge>
                          <AnimatedTooltip
                            content={buildRiskScoreExplainer(action.score)}
                            autoFlip
                            focusable
                            maxWidth="420px"
                            placement="bottom"
                            tapToToggle
                            triggerClassName={HELP_BADGE_TRIGGER_CLASS}
                          >
                            <Badge
                              variant="info"
                              className="bg-[var(--card)]/88 text-info"
                            >
                              Risk {action.score}
                            </Badge>
                          </AnimatedTooltip>
                          <AnimatedTooltip
                            content={buildBusinessImpactBadgeExplainer(
                              action.business_impact,
                            )}
                            autoFlip
                            focusable
                            maxWidth="420px"
                            placement="bottom"
                            tapToToggle
                            triggerClassName={HELP_BADGE_TRIGGER_CLASS}
                          >
                            <Badge
                              variant={businessImpactBadgeVariant(
                                action.business_impact,
                              )}
                              className="bg-[var(--card)]/88"
                            >
                              {formatBusinessImpactLabel(action.business_impact)}
                            </Badge>
                          </AnimatedTooltip>
                          {attackPathView && (
                            <Badge
                              variant={getAttackPathStatusVariant(
                                attackPathView.status,
                              )}
                              className="bg-[var(--card)]/88"
                            >
                              Attack path {attackPathView.status.replace("_", " ")}
                            </Badge>
                          )}
                        </div>
                      </div>

                      <div className="flex w-full flex-col gap-3 xl:w-auto xl:min-w-[15rem]">
                        <div className={remediationInsetClass("default", "flex items-center justify-between px-4 py-3")}>
                          <div className="space-y-1">
                            <p className={REMEDIATION_EYEBROW_CLASS}>Live state</p>
                            <p className="text-sm font-medium text-text/78">
                              Refresh computed status and remediation readiness.
                            </p>
                          </div>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={handleRecompute}
                            disabled={recomputeLoading}
                            className="shrink-0"
                          >
                            {recomputeLoading ? "Refreshing..." : "Refresh State"}
                          </Button>
                        </div>

                        {attackPathView && (
                          <div className={remediationInsetClass("danger", "space-y-3 px-4 py-4")}>
                            <div className="space-y-1">
                              <p className={REMEDIATION_EYEBROW_CLASS}>Attack path view</p>
                              <p className="text-sm leading-7 text-text/78">
                                Review the bounded path story before changing state or routing this action.
                              </p>
                            </div>
                            <Link
                              href={`/attack-paths?path_id=${encodeURIComponent(action.path_id ?? action.id)}`}
                              className={attackPathLinkClassName()}
                            >
                              <span>Open Attack Paths</span>
                              <svg
                                className="h-4 w-4 transition-transform duration-150 group-hover:translate-x-0.5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth={2}
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M13.5 4.5l6 6m0 0l-6 6m6-6h-15"
                                />
                              </svg>
                            </Link>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="mb-8 grid grid-cols-1 gap-4 text-sm md:grid-cols-2 lg:grid-cols-3">
                      <div className={remediationInsetClass("default", "flex flex-col gap-1")}>
                        <span className={REMEDIATION_EYEBROW_CLASS}>
                          {action.control_family?.is_mapped ? "Reported rule(s)" : "Control ID"}
                        </span>
                        <span className="truncate font-mono text-text">
                          {action.control_family?.is_mapped ? reportedRulesLabel : controlSummary || "N/A"}
                        </span>
                        {action.control_family?.is_mapped && (
                          <span className="text-xs leading-6 text-muted" title={CONTROL_FAMILY_TOOLTIP}>
                            AWS-reported rule IDs stay visible here.
                          </span>
                        )}
                      </div>
                      {action.control_family?.is_mapped && (
                        <div className={remediationInsetClass("default", "flex flex-col gap-1")}>
                          <span className={REMEDIATION_EYEBROW_CLASS}>
                            Remediation family
                          </span>
                          <span className="truncate font-mono text-text">
                            {remediationFamilyLabel}
                          </span>
                          <span className="text-xs leading-6 text-muted" title={CONTROL_FAMILY_TOOLTIP}>
                            {controlSummary || remediationFamilyLabel}
                          </span>
                        </div>
                      )}
                      <div className={remediationInsetClass("default", "flex flex-col gap-1")}>
                        <span className={REMEDIATION_EYEBROW_CLASS}>
                          Account
                        </span>
                        <span className="truncate font-mono text-text">
                          {action.account_id}
                        </span>
                      </div>
                      <div className={remediationInsetClass("default", "flex flex-col gap-1")}>
                        <span className={REMEDIATION_EYEBROW_CLASS}>
                          Region
                        </span>
                        <span className="font-mono text-text">
                          {action.region || "Global"}
                        </span>
                      </div>
                    </div>

                    {isAuthenticated && (
                      <div
                        className={remediationInsetClass(
                          "default",
                          "flex flex-col gap-4 border-t border-border/35 px-5 py-5 xl:flex-row xl:items-center xl:justify-between",
                        )}
                      >
                        <div className="space-y-1">
                          <p className={REMEDIATION_EYEBROW_CLASS}>Action workflow</p>
                          <p className="text-sm leading-7 text-text/74">
                            Keep remediation, suppression, and review actions in one consistent control rail.
                          </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-3">
                          {canRunDirectFix && (
                            <div className="flex flex-col gap-2">
                              <AnimatedTooltip
                                content={
                                  !hasWriteRole
                                    ? "WriteRole not configured; add WriteRole in account settings."
                                    : undefined
                                }
                              >
                                <MajorActionButton
                                  onClick={() =>
                                    setRemediationModalMode("direct_fix")
                                  }
                                  disabled={!hasWriteRole || !hasLinkedFindings}
                                  className="px-6"
                                >
                                  Run fix
                                </MajorActionButton>
                              </AnimatedTooltip>
                              {showMissingWriteRoleHelper && (
                                <Link
                                  href="/settings"
                                  className="text-center text-[10px] text-accent hover:underline"
                                  onClick={onClose}
                                >
                                  Configure Write Role
                                </Link>
                              )}
                            </div>
                          )}
                          <MajorActionButton
                            onClick={() => {
                              setPrBundleChrome(createDefaultPrBundleChrome());
                              startTransition(() => {
                                setActionSubview("pr_bundle");
                              });
                            }}
                            disabled={!hasLinkedFindings}
                            className="px-6"
                          >
                            Generate PR bundle
                          </MajorActionButton>

                          {!action.exception_id && !action.exception_expired && (
                            <Button
                              variant="secondary"
                              onClick={() => openSuppressView()}
                              disabled={!hasLinkedFindings}
                              leftIcon={
                                <svg
                                  className="h-4 w-4"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                  strokeWidth={2}
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
                                  />
                                </svg>
                              }
                            >
                              Suppress
                            </Button>
                          )}
                        </div>
                      </div>
                    )}
                  </RemediationPanel>

                  {/* Summary Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className={remediationInsetClass("default", "p-6")}>
                      <h3 className={cn(REMEDIATION_EYEBROW_CLASS, "mb-3")}>
                        What is wrong
                      </h3>
                      <p className="text-sm text-text/90 leading-relaxed font-medium">
                        {action.what_is_wrong}
                      </p>
                    </div>
                    <div className={remediationInsetClass("default", "p-6")}>
                      <h3 className={cn(REMEDIATION_EYEBROW_CLASS, "mb-3")}>
                        What the fix does
                      </h3>
                      <p className="text-sm text-text/90 leading-relaxed font-medium">
                        {action.what_the_fix_does}
                      </p>
                    </div>
                  </div>

                  {/* Attack Path */}
                  {attackPathView && (
                    <RemediationPanel className="p-8" tone="danger">
                      <div className="relative">
                        <div className="mb-6 flex items-center justify-between gap-4 border-b border-border/35 pb-5">
                          <div className="flex items-center gap-3">
                            <div className={remediationInsetClass("danger", "w-fit p-2 text-danger")}>
                              <svg
                                className="w-5 h-5"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                                strokeWidth={2}
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M11.412 15.655L9.75 21.75l3.745-4.012M9.257 13.5H3.75l2.659-2.849m2.048-2.151L14.25 2.25l-1.662 6.095m-4.64 0a1.5 1.5 0 011.173-.494h10.842A1.5 1.5 0 0121 9.35l-2.007 7.359a1.5 1.5 0 01-1.447 1.104h-4.32a1.5 1.5 0 01-1.282-.724l-3.238-5.361a1.5 1.5 0 01-.223-.74z"
                                />
                              </svg>
                            </div>
                            <div>
                              <h3 className="text-sm font-bold uppercase tracking-widest text-text">
                                Attack Path
                              </h3>
                              <AnimatedTooltip
                                content={getBoundedDecisionViewExplainer()}
                                autoFlip
                                focusable
                                maxWidth="420px"
                                placement="bottom"
                                tapToToggle
                                triggerClassName={HELP_TEXT_TRIGGER_CLASS}
                              >
                                <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted/70">
                                  Bounded decision view
                                </p>
                              </AnimatedTooltip>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <AnimatedTooltip
                              content={getAttackPathStatusTooltip(
                                attackPathView,
                              )}
                              autoFlip
                              maxWidth="360px"
                              placement="left"
                            >
                              <Badge
                                variant={getAttackPathStatusVariant(
                                  attackPathView.status,
                                )}
                                className="bg-[var(--card)]/82"
                              >
                                {attackPathView.status.replace("_", " ")}
                              </Badge>
                            </AnimatedTooltip>
                            {isBusinessCriticalAction && (
                              <AnimatedTooltip
                                content={buildBusinessCriticalExplainer(
                                  action.business_impact,
                                )}
                                autoFlip
                                focusable
                                maxWidth="420px"
                                placement="bottom"
                                tapToToggle
                                triggerClassName={HELP_BADGE_TRIGGER_CLASS}
                              >
                                <Badge
                                  variant="warning"
                                  className="bg-[var(--card)]/82"
                                >
                                  Business critical
                                </Badge>
                              </AnimatedTooltip>
                            )}
                          </div>
                        </div>

                        <div className="mb-8 max-w-5xl space-y-4 pt-2">
                          <p className="text-[15px] font-medium leading-9 text-text/90">
                            {renderAttackPathSummary(
                              attackPathView.summary,
                              attackPathSummaryContext,
                            )}
                          </p>

                          {attackPathSummaryContext &&
                            (showAttackPathCautionLine ||
                              showAttackPathNextStepLine ||
                              showAttackPathImpactLine) && (
                              <p className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm leading-7 text-text/70">
                                {showAttackPathCautionLine && (
                                  <>
                                    <span className="font-semibold text-warning/95">
                                      {attackPathSummaryContext.cautionLabel}:
                                    </span>
                                    <span className="text-text/78">
                                      {attackPathSummaryContext.cautionDetail}
                                    </span>
                                  </>
                                )}
                                {showAttackPathNextStepLine && (
                                  <>
                                    {showAttackPathCautionLine && (
                                      <span className="text-white/15">•</span>
                                    )}
                                    <span className="font-semibold text-text/88">
                                      Next:
                                    </span>
                                    <span className="font-medium text-danger/90">
                                      {attackPathSummaryContext.nextStepLabel}
                                    </span>
                                  </>
                                )}
                                {showAttackPathImpactLine && (
                                  <>
                                    {(showAttackPathCautionLine ||
                                      showAttackPathNextStepLine) && (
                                      <span className="text-white/15">•</span>
                                    )}
                                    <span className="text-muted/80">
                                      Impact
                                    </span>
                                    <span className="text-text/78">
                                      {attackPathSummaryContext.impactLabel}
                                    </span>
                                  </>
                                )}
                              </p>
                            )}
                        </div>

                        {(attackPathView.status === "available" ||
                          attackPathView.status === "partial") &&
                        attackPathView.path_nodes.length > 0 ? (
                          <div className="overflow-x-auto pb-4 custom-scrollbar">
                            <div className="flex min-w-max items-stretch gap-4">
                              {attackPathView.path_nodes.map((node, index) => (
                                <div
                                  key={node.node_id}
                                  className="flex items-stretch"
                                >
                                  <ActionDetailAttackPathNodeCard node={node} />
                                  {index < attackPathView.path_edges.length && (
                                    <div className="flex flex-col items-center justify-center gap-2 px-4">
                                      <span className="text-danger/50">→</span>
                                      <span className="whitespace-nowrap text-[10px] font-semibold uppercase tracking-[0.16em] text-muted/60">
                                        {attackPathView.path_edges[index].label}
                                      </span>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <div className={remediationInsetClass("default", "p-6 text-sm italic text-muted")}>
                            {getAttackPathAvailabilityMessage(attackPathView)}
                          </div>
                        )}
                      </div>
                    </RemediationPanel>
                  )}

                  {action && (
                    <ActionDetailPriorityStoryboard
                      actionType={action.action_type}
                      businessImpact={action.business_impact}
                      scoreFactors={scoreFactors}
                    />
                  )}

                  {jiraExternalSync.length > 0 && (
                    <RemediationPanel className="p-8" tone="default">
                      <div className="flex items-center justify-between gap-4 border-b border-border/35 pb-5">
                        <div>
                          <h3 className="text-sm font-bold uppercase tracking-widest text-text">
                            External Sync
                          </h3>
                          <p className="mt-1 text-sm text-text/72">
                            Jira linkage, drift state, reconciliation activity, and assignee mapping health.
                          </p>
                        </div>
                        <Badge variant="info">Jira</Badge>
                      </div>

                      <div className="mt-6 space-y-5">
                        {jiraExternalSync.map((sync) => (
                          <div
                            key={`${sync.provider}:${sync.external_id ?? sync.external_key ?? "unlinked"}`}
                            className={remediationInsetClass(
                              sync.sync_status === "drifted" ? "danger" : "default",
                              "space-y-5 p-5",
                            )}
                          >
                            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                              <div className="space-y-2">
                                <div className="flex flex-wrap items-center gap-2">
                                  <Badge variant={getExternalSyncBadgeVariant(sync.sync_status)}>
                                    {sync.sync_status ? formatSyncValue(sync.sync_status) : "Link pending"}
                                  </Badge>
                                  <Badge variant="default">
                                    External status: {formatSyncValue(sync.external_status)}
                                  </Badge>
                                  <Badge variant={getAssigneeSyncBadgeVariant(sync.assignee_sync_state)}>
                                    Assignee: {formatSyncValue(sync.assignee_sync_state)}
                                  </Badge>
                                </div>
                                <div className="text-sm text-text/86">
                                  {sync.external_url ? (
                                    <a
                                      href={sync.external_url}
                                      target="_blank"
                                      rel="noreferrer"
                                      className="font-semibold text-accent hover:underline"
                                    >
                                      {sync.external_key ?? sync.external_id ?? "Open Jira issue"}
                                    </a>
                                  ) : (
                                    <span className="font-semibold text-text">
                                      {sync.external_key ?? sync.external_id ?? "Jira link pending"}
                                    </span>
                                  )}
                                </div>
                              </div>

                              <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[26rem]">
                                <div className={remediationInsetClass("default", "space-y-1 px-3 py-3")}>
                                  <p className={REMEDIATION_EYEBROW_CLASS}>Preferred status</p>
                                  <p className="text-sm font-medium text-text">
                                    {formatSyncValue(sync.preferred_external_status)}
                                  </p>
                                </div>
                                <div className={remediationInsetClass("default", "space-y-1 px-3 py-3")}>
                                  <p className={REMEDIATION_EYEBROW_CLASS}>Canonical action</p>
                                  <p className="text-sm font-medium text-text">
                                    {formatSyncValue(sync.canonical_internal_status)}
                                  </p>
                                </div>
                                <div className={remediationInsetClass("default", "space-y-1 px-3 py-3")}>
                                  <p className={REMEDIATION_EYEBROW_CLASS}>Last inbound</p>
                                  <p className="text-sm font-medium text-text">
                                    {formatDate(sync.last_inbound_at ?? null)}
                                  </p>
                                </div>
                                <div className={remediationInsetClass("default", "space-y-1 px-3 py-3")}>
                                  <p className={REMEDIATION_EYEBROW_CLASS}>Last outbound</p>
                                  <p className="text-sm font-medium text-text">
                                    {formatDate(sync.last_outbound_at ?? null)}
                                  </p>
                                </div>
                                <div className={remediationInsetClass("default", "space-y-1 px-3 py-3")}>
                                  <p className={REMEDIATION_EYEBROW_CLASS}>Last reconcile</p>
                                  <p className="text-sm font-medium text-text">
                                    {formatDate(sync.last_reconciled_at ?? null)}
                                  </p>
                                </div>
                                <div className={remediationInsetClass("default", "space-y-1 px-3 py-3")}>
                                  <p className={REMEDIATION_EYEBROW_CLASS}>Resolution</p>
                                  <p className="text-sm font-medium text-text">
                                    {formatSyncValue(sync.resolution_decision)}
                                  </p>
                                </div>
                              </div>
                            </div>

                            {sync.assignee_sync_detail && (
                              <p className="text-sm leading-7 text-text/74">{sync.assignee_sync_detail}</p>
                            )}

                            {sync.conflict_reason && (
                              <div className={remediationInsetClass("danger", "p-4 text-sm text-text/82")}>
                                <span className="font-semibold text-danger">Conflict reason:</span>{" "}
                                {sync.conflict_reason}
                              </div>
                            )}

                            <div className="space-y-3">
                              <div className="flex items-center justify-between">
                                <h4 className="text-xs font-bold uppercase tracking-[0.2em] text-muted/72">
                                  Recent sync events
                                </h4>
                                <span className="text-xs text-muted/72">
                                  {sync.recent_events?.length ?? 0} recorded
                                </span>
                              </div>
                              {sync.recent_events && sync.recent_events.length > 0 ? (
                                <div className="space-y-3">
                                  {sync.recent_events.map((event) => (
                                    <div
                                      key={event.id}
                                      className={remediationInsetClass("default", "grid gap-2 px-4 py-3 lg:grid-cols-[12rem_1fr]")}
                                    >
                                      <div className="space-y-1">
                                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted/68">
                                          {formatSyncEventLabel(event.event_type)}
                                        </p>
                                        <p className="text-xs text-muted/78">
                                          {formatDate(event.created_at ?? null)}
                                        </p>
                                      </div>
                                      <div className="space-y-1">
                                        <p className="text-sm font-medium text-text">
                                          {event.decision_detail ?? "No detail recorded."}
                                        </p>
                                        <p className="text-xs text-text/70">
                                          Source {formatSyncValue(event.source)} · external {formatSyncValue(event.external_status)} · preferred{" "}
                                          {formatSyncValue(event.preferred_external_status)}
                                        </p>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <div className={remediationInsetClass("default", "p-4 text-sm text-muted")}>
                                  No sync events recorded yet for this Jira link.
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </RemediationPanel>
                  )}

                  {/* Action History / Runs */}
                  <div className={remediationPanelClass("default", "overflow-hidden")}>
                    <div className="flex items-center justify-between border-b border-border/35 px-8 py-6">
                      <h3 className="text-sm font-bold text-muted uppercase tracking-widest">
                        Remediation History
                      </h3>
                      <span className="rounded-full border border-border/55 bg-bg/70 px-2 py-0.5 text-[10px] font-bold uppercase text-muted">
                        {runs.length} runs found
                      </span>
                    </div>
                    {runsLoading ? (
                      <div className="p-8 space-y-4 animate-pulse">
                        <div className="h-12 w-full rounded-2xl bg-bg/70" />
                        <div className="h-12 w-full rounded-2xl bg-bg/70" />
                      </div>
                    ) : runs.length === 0 ? (
                      <div className="p-12 text-center">
                        <p className="text-sm text-muted opacity-60">
                          No activity recorded yet.
                        </p>
                      </div>
                    ) : (
                      <div className="divide-y divide-border/35">
                        {runs.map((run) => (
                          <div
                            key={run.id}
                            className="group px-8 py-6 transition-colors hover:bg-bg/40"
                          >
                            {run.status === "pending" ||
                            run.status === "running" ? (
                              <RemediationRunProgress
                                runId={run.id}
                                tenantId={effectiveTenantId}
                                onComplete={fetchRuns}
                                compact={true}
                              />
                            ) : (
                              <Link
                                href={`/remediation-runs/${run.id}`}
                                className="flex items-center gap-4"
                                onClick={onClose}
                              >
                                <Badge
                                  variant={
                                    run.status === "success"
                                      ? "success"
                                      : run.status === "failed" ||
                                          run.status === "cancelled"
                                        ? "danger"
                                        : "default"
                                  }
                                >
                                  {run.status}
                                </Badge>
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-bold text-text group-hover:text-accent transition-colors">
                                    {run.mode.replace("_", " ")} Fix
                                  </p>
                                  {run.outcome && (
                                    <p className="text-xs text-muted truncate mt-0.5">
                                      {run.outcome}
                                    </p>
                                  )}
                                </div>
                                <span className="text-xs text-muted font-mono opacity-50">
                                  {formatDate(run.created_at)}
                                </span>
                                <svg
                                  className="w-4 h-4 text-muted group-hover:text-accent group-hover:translate-x-1 transition-all"
                                  fill="none"
                                  viewBox="0 0 24 24"
                                  stroke="currentColor"
                                  strokeWidth={2}
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    d="M8.25 4.5l7.5 7.5-7.5 7.5"
                                  />
                                </svg>
                              </Link>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );

  const portals = (
    <>
      {action && remediationModalMode === "direct_fix" && (
        <RemediationModal
          isOpen={!!remediationModalMode}
          onClose={() => {
            setRemediationModalMode(null);
            fetchRuns();
          }}
          actionId={action.id}
          actionTitle={action.title}
          actionType={action.action_type}
          accountId={action.account_id}
          region={action.region}
          mode={remediationModalMode}
          hasWriteRole={!!hasWriteRole}
          tenantId={effectiveTenantId}
          onChooseException={(selection) => {
            setRemediationModalMode(null);
            openSuppressView(exceptionDefaultsForSelection(selection));
          }}
        />
      )}
    </>
  );

  return (
    <>
      {portalContainer ? createPortal(modalContent, portalContainer) : modalContent}
      {portals}
    </>
  );
}
