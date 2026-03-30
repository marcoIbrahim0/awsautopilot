'use client';

import { type ButtonHTMLAttributes, type ReactNode, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { useAuth } from '@/contexts/AuthContext';
import { useBackgroundJobs } from '@/contexts/BackgroundJobsContext';
import { NeedHelpLink } from '@/components/help/NeedHelpLink';
import { ThemeToggle } from '@/components/ui';
import { SelectDropdown } from '@/components/ui/SelectDropdown';
import {
  buildOnboardingAccountMutation,
  resolveOnboardingConnectedAccount,
  upsertAwsAccount,
} from '@/app/onboarding/account-connection';
import {
  AwsAccount,
  AccountServiceReadiness,
  AccountControlPlaneReadiness,
  OnboardingFastPathResponse,
  checkAccountControlPlaneReadiness,
  checkAccountServiceReadiness,
  getAccounts,
  getErrorMessage,
  registerAccount,
  sendSyntheticControlPlaneEvent,
  sendSyntheticControlPlaneEventForAccount,
  triggerOnboardingFastPath,
  triggerComputeActions,
  triggerIngest,
  updateAccount,
} from '@/lib/api';
import { AWS_REGIONS, DEFAULT_REGION, MAX_REGIONS } from '@/lib/aws-regions';

function CopyButton({ text, title }: { text: string; title: string }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (copied) {
      const timeout = setTimeout(() => setCopied(false), 2000);
      return () => clearTimeout(timeout);
    }
  }, [copied]);

  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
      }}
      className="flex items-center justify-center p-1 text-[var(--onboarding-text-muted)] hover:text-[#0B71FF] transition-colors rounded-md relative"
      title={title}
    >
      <div className={`transition-all duration-200 absolute inset-0 flex items-center justify-center ${copied ? 'opacity-100 scale-100 text-[#00E676]' : 'opacity-0 scale-50'}`}>
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <div className={`transition-all duration-200 flex items-center justify-center ${copied ? 'opacity-0 scale-50' : 'opacity-100 scale-100'}`}>
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      </div>
    </button>
  );
}

type StepId =
  | 'welcome'
  | 'integration-role'
  | 'inspector'
  | 'security-hub-config'
  | 'control-plane'
  | 'final-checks'
  | 'processing';

const STEP_ORDER: StepId[] = [
  'welcome',
  'integration-role',
  'inspector',
  'security-hub-config',
  'control-plane',
  'final-checks',
  'processing',
];

const SIDEBAR_STEP_LABELS: Array<{ title: string; subtitle?: string }> = [
  { title: 'Welcome', subtitle: 'Start here' },
  { title: 'Integration Role' },
  { title: 'Inspector' },
  { title: 'Security Hub + Config' },
  { title: 'Control-plane' },
  { title: 'Final Checks' },
  { title: 'Processing' },
];

const OPTIONAL_STEPS = new Set<StepId>();

const DRAFT_STORAGE_KEY = 'onboarding_v2_draft';
const FIRST_RUN_STORAGE_KEY = 'first_login_processing_v1';
const ONBOARDING_TTV_METRICS_STORAGE_KEY = 'onboarding_ttv_metrics_v1';
const DRAFT_TTL_MS = 30 * 24 * 60 * 60 * 1000;
const CHECK_QUICK_REVALIDATE_MS = 15 * 60 * 1000;
const CHECK_FULL_REVALIDATE_MS = 24 * 60 * 60 * 1000;
const CONTROL_PLANE_POLL_INTERVAL_MS = 10_000;
const CONTROL_PLANE_POLL_MAX_WAIT_MS = 90_000;
const CONTROL_PLANE_VERIFY_PROGRESS_INTERVAL_MS = 1_400;

interface OnboardingDraft {
  version: 2;
  updatedAt: number;
  step: StepId;
  accountId: string;
  integrationRoleArn: string;
  regions: string[];
  controlPlaneRegion: string;
  controlPlaneStackName: string;
  connectedAccountId: string | null;
  inspectorVerified: boolean;
  securityHubConfigVerified: boolean;
  controlPlaneVerified: boolean;
  fastPathTriggered: boolean;
  fastPathComputeQueued: boolean;
  fastPathLastAttemptAt: number | null;
  firstIngestQueuedAt: number | null;
  firstIngestQueueMode: 'fast_path' | 'processing' | null;
  integrationValidatedAt: number | null;
  lastServiceCheckAt: number | null;
  lastControlPlaneCheckAt: number | null;
}

interface OnboardingTimeToValueMetric {
  account_id: string;
  tenant_id: string;
  connected_at: string;
  first_ingest_queued_at: string;
  first_ingest_queue_mode: 'fast_path' | 'processing';
  time_to_first_ingest_ms: number;
  captured_at: string;
}

interface SyntheticControlPlaneAttempt {
  sent: boolean;
  fallbackReason: string | null;
}

type ControlPlaneVerifyPhase = 'idle' | 'sending' | 'polling';

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function nextControlPlaneVerifyProgress(progress: number, phase: ControlPlaneVerifyPhase): number {
  if (phase === 'sending') return Math.min(28, Math.max(progress, 14) + 10);
  if (phase === 'polling') return Math.min(94, progress >= 78 ? progress + 3 : Math.max(progress, 38) + 6);
  return 0;
}

function controlPlaneVerifyHeadline(phase: ControlPlaneVerifyPhase, region: string): string {
  if (phase === 'sending') return `Sending verification event for ${region}...`;
  if (phase === 'polling') return `Checking for recent intake in ${region}...`;
  return 'Preparing automated verification...';
}

function controlPlaneVerifyDetail(phase: ControlPlaneVerifyPhase): string {
  if (phase === 'sending') return 'Starting the synthetic intake check now.';
  if (phase === 'polling') return 'Estimated progress stays active while readiness polling runs for up to 90 seconds.';
  return 'Preparing automated verification.';
}

function formatDropReasons(dropReasons: Record<string, number>): string {
  return Object.entries(dropReasons)
    .map(([reason, count]) => `${reason} (${count})`)
    .join(', ');
}

function buildControlPlaneFailureMessage(
  missingRegions: string,
  synthetic: SyntheticControlPlaneAttempt
): string {
  if (synthetic.sent) {
    return `Readiness is still stale after automated verification (missing: ${missingRegions}).`;
  }
  return (
    `${synthetic.fallbackReason || 'Automated verification did not run.'} ` +
    `Forwarder may not be deployed or delivering events for: ${missingRegions}. ` +
    'Manual fallback: deploy/update the forwarder stack, perform a supported SG or S3 change, then verify again.'
  );
}

function controlPlaneSuccessMessage(syntheticSent: boolean): string {
  if (syntheticSent) return 'Control-plane verification passed via automated event and readiness poll.';
  return 'Control-plane readiness is recent. Automated verification path was unavailable, but verification passed.';
}

function parseAccountIdFromRoleArn(roleArn: string): string {
  const match = /arn:aws:iam::(\d{12}):role\//.exec(roleArn.trim());
  return match ? match[1] : '';
}

function isValidRoleArn(value: string): boolean {
  return /^arn:aws[a-z-]*:iam::\d{12}:role\/[A-Za-z0-9+=,.@_\/-]{1,512}$/.test(value.trim());
}

function getDefaultDraft(): OnboardingDraft {
  return {
    version: 2,
    updatedAt: Date.now(),
    step: 'welcome',
    accountId: '',
    integrationRoleArn: '',
    regions: [DEFAULT_REGION],
    controlPlaneRegion: DEFAULT_REGION,
    controlPlaneStackName: '',
    connectedAccountId: null,
    inspectorVerified: false,
    securityHubConfigVerified: false,
    controlPlaneVerified: false,
    fastPathTriggered: false,
    fastPathComputeQueued: false,
    fastPathLastAttemptAt: null,
    firstIngestQueuedAt: null,
    firstIngestQueueMode: null,
    integrationValidatedAt: null,
    lastServiceCheckAt: null,
    lastControlPlaneCheckAt: null,
  };
}

function loadDraft(): OnboardingDraft {
  if (typeof window === 'undefined') return getDefaultDraft();
  try {
    const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) return getDefaultDraft();
    const parsedRaw = JSON.parse(raw) as Record<string, unknown>;
    if (parsedRaw.version !== 2) return getDefaultDraft();
    const updatedAt = typeof parsedRaw.updatedAt === 'number' ? parsedRaw.updatedAt : 0;
    if (!updatedAt || Date.now() - updatedAt > DRAFT_TTL_MS) return getDefaultDraft();
    const parsed = parsedRaw as Partial<OnboardingDraft>;
    const stepRaw = typeof parsedRaw.step === 'string' ? parsedRaw.step : undefined;
    const step =
      stepRaw === 'read-role' || stepRaw === 'access-analyzer' ? 'final-checks' : stepRaw;
    return {
      ...getDefaultDraft(),
      ...parsed,
      version: 2,
      updatedAt,
      step: STEP_ORDER.includes(step as StepId) ? (step as StepId) : 'welcome',
      regions: parsed.regions?.length ? parsed.regions : [DEFAULT_REGION],
    };
  } catch {
    return getDefaultDraft();
  }
}

function sanitizeStackName(value: string): string {
  return (value || '').trim().replace(/[^a-zA-Z0-9-]/g, '-').slice(0, 128);
}

function appendOnboardingMetricSample(sample: OnboardingTimeToValueMetric): void {
  if (typeof window === 'undefined') return;
  try {
    const raw = localStorage.getItem(ONBOARDING_TTV_METRICS_STORAGE_KEY);
    const existing = raw ? (JSON.parse(raw) as OnboardingTimeToValueMetric[]) : [];
    const next = [sample, ...existing].slice(0, 30);
    localStorage.setItem(ONBOARDING_TTV_METRICS_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Non-blocking telemetry persistence.
  }
}

function sectionTitle(step: StepId): string {
  if (step === 'welcome') return 'Welcome';
  if (step === 'integration-role') return 'Connect Core Integration Role';
  if (step === 'inspector') return 'Enable Inspector (Required)';
  if (step === 'security-hub-config') return 'Enable Security Hub + AWS Config (Required)';
  if (step === 'control-plane') return 'Deploy Control-Plane Forwarder (Required)';
  if (step === 'final-checks') return 'Final Connection Checks';
  return 'Initial Processing';
}

function stepDescription(step: StepId): string {
  if (step === 'welcome') return 'Follow these guided steps to connect your AWS account safely with minimal required permissions.';
  if (step === 'integration-role') return 'Deploy the core integration role, paste the ARN, and validate account access before continuing.';
  if (step === 'inspector') return 'Inspector is mandatory before this account can be marked connected.';
  if (step === 'security-hub-config') return 'Security Hub and AWS Config must both be enabled in monitored regions.';
  if (step === 'control-plane')
    return 'Required real-time updates. Deploy the forwarder in this customer account for all monitored regions.';
  if (step === 'final-checks') return 'Run all required checks. Required checks run only during onboarding.';
  return 'Loading findings and computing actions. You will continue on the Findings page with live status.';
}

type ActionTone = 'primary' | 'secondary' | 'ghost';

function ActionButton({
  tone = 'primary',
  loading = false,
  className = '',
  disabled,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean; tone?: ActionTone }) {
  const toneClass =
    tone === 'primary'
      ? 'bg-[#0B71FF] text-white shadow-[0_0_16px_rgba(11,113,255,0.4)] hover:-translate-y-0.5 hover:shadow-[0_0_24px_rgba(11,113,255,0.6)]'
      : tone === 'secondary'
        ? 'onboarding-button-secondary'
        : 'onboarding-button-ghost border border-transparent';

  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-[14px] px-5 py-2.5 text-sm font-semibold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${toneClass} ${className}`}
      type={props.type ?? 'button'}
    >
      {loading ? <span className="onboarding-spinner h-4 w-4 rounded-full border-2 border-current/25 border-t-current" /> : null}
      <span>{children}</span>
    </button>
  );
}

function FormField({
  label,
  helperText,
  children,
}: {
  label: string;
  helperText?: string;
  children: ReactNode;
}) {
  return (
    <label className="block space-y-2">
      <span className="onboarding-display block text-sm font-semibold tracking-[0.18em] text-[var(--onboarding-text-soft)] uppercase">
        {label}
      </span>
      {children}
      {helperText ? <span className="block text-[13px] leading-5 text-[var(--onboarding-text-muted)]">{helperText}</span> : null}
    </label>
  );
}

function StatusPill({
  children,
  tone = 'default',
}: {
  children: ReactNode;
  tone?: 'default' | 'info' | 'success';
}) {
  const toneClass =
    tone === 'info'
      ? 'border-[#0B71FF]/30 bg-[#0B71FF]/15 text-[var(--onboarding-info-text)]'
      : tone === 'success'
        ? 'border-[#00E676]/25 bg-[#00E676]/10 text-[#7FF5B3]'
        : 'onboarding-status-default';

  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] ${toneClass}`}>
      {children}
    </span>
  );
}

type WelcomeIconKind = 'shield' | 'hash' | 'globe';

function WelcomeIcon({ kind }: { kind: WelcomeIconKind }) {
  if (kind === 'shield') {
    return (
      <svg aria-hidden className="h-7 w-7" fill="none" viewBox="0 0 24 24">
        <path
          d="M12 3l6 2.5v5.9c0 4.2-2.6 8-6 9.6-3.4-1.6-6-5.4-6-9.6V5.5L12 3z"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
        <path
          d="M12 10.3a2.3 2.3 0 100 4.6 2.3 2.3 0 000-4.6zm0 4.7v2.2"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  if (kind === 'hash') {
    return (
      <svg aria-hidden className="h-7 w-7" fill="none" viewBox="0 0 24 24">
        <path
          d="M9 4L7 20M17 4l-2 16M4 9h16M3 15h16"
          stroke="currentColor"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="1.8"
        />
      </svg>
    );
  }

  return (
    <svg aria-hidden className="h-7 w-7" fill="none" viewBox="0 0 24 24">
      <path
        d="M12 3a9 9 0 100 18 9 9 0 000-18z"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="M3.7 9h16.6M3.7 15h16.6M12 3c2.5 2.4 3.9 5.5 3.9 9S14.5 18.6 12 21M12 3C9.5 5.4 8.1 8.5 8.1 12S9.5 18.6 12 21"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

const PANEL_CLASS_LARGE = 'onboarding-panel rounded-[24px] p-6';
const INSET_PANEL_CLASS_LARGE = 'onboarding-inset rounded-[24px] p-6';
const STICKY_ACTIONS_CLASS =
  'onboarding-footer z-10 px-6 py-4 backdrop-blur-xl sm:px-8 lg:px-10 border-t border-[var(--onboarding-divider)]';
const INPUT_CLASS =
  'onboarding-field onboarding-input w-full rounded-[16px] px-4 py-3 text-base placeholder:opacity-100';
const SELECT_CONTENT_CLASS = 'onboarding-select-content !rounded-[16px]';

export default function OnboardingPage() {
  const router = useRouter();
  const {
    user,
    tenant,
    saas_account_id,
    read_role_launch_stack_url,
    read_role_default_stack_name,
    buildReadRoleLaunchStackUrl,
    control_plane_token,
    control_plane_token_active,
    control_plane_ingest_url,
    control_plane_forwarder_default_stack_name,
    buildControlPlaneForwarderLaunchStackUrl,
    rotateControlPlaneToken,
    revokeControlPlaneToken,
    isAuthenticated,
    isLoading: authLoading,
    markOnboardingComplete,
  } = useAuth();

  const { addJob, updateJob, completeJob, failJob, timeoutJob } = useBackgroundJobs();

  const [draft, setDraft] = useState<OnboardingDraft>(() => loadDraft());
  const [connectedAccount, setConnectedAccount] = useState<AwsAccount | null>(null);
  const [existingAccounts, setExistingAccounts] = useState<AwsAccount[]>([]);
  const [serviceReadiness, setServiceReadiness] = useState<AccountServiceReadiness | null>(null);
  const [controlPlaneReadiness, setControlPlaneReadiness] = useState<AccountControlPlaneReadiness | null>(null);
  const [fastPathResult, setFastPathResult] = useState<OnboardingFastPathResponse | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [resumeNotice, setResumeNotice] = useState<string | null>(null);

  const [isCheckingInspector, setIsCheckingInspector] = useState(false);
  const [isCheckingSecurityHub, setIsCheckingSecurityHub] = useState(false);
  const [isCheckingControlPlane, setIsCheckingControlPlane] = useState(false);
  const [isLaunchingControlPlane, setIsLaunchingControlPlane] = useState(false);
  const [controlPlaneVerifyPhase, setControlPlaneVerifyPhase] = useState<ControlPlaneVerifyPhase>('idle');
  const [controlPlaneVerifyProgress, setControlPlaneVerifyProgress] = useState(0);
  const [isRunningFinalChecks, setIsRunningFinalChecks] = useState(false);
  const [isStartingFastPath, setIsStartingFastPath] = useState(false);
  const [isRotatingControlPlaneToken, setIsRotatingControlPlaneToken] = useState(false);
  const [revealedControlPlaneToken, setRevealedControlPlaneToken] = useState<string | null>(control_plane_token);

  const parsedAccountId = draft.accountId.trim() || parseAccountIdFromRoleArn(draft.integrationRoleArn);
  const canValidateIntegrationRole =
    parsedAccountId.length === 12 &&
    isValidRoleArn(draft.integrationRoleArn) &&
    draft.regions.length >= 1 &&
    draft.regions.length <= MAX_REGIONS;

  const currentStepIndex = STEP_ORDER.indexOf(draft.step);
  const canGoBack = currentStepIndex > 0;

  const shouldQuickRevalidateRequiredChecks = useMemo(() => {
    if (!draft.lastServiceCheckAt) return true;
    const age = Date.now() - draft.lastServiceCheckAt;
    return age >= CHECK_QUICK_REVALIDATE_MS;
  }, [draft.lastServiceCheckAt]);

  const shouldFullRevalidateRequiredChecks = useMemo(() => {
    if (!draft.lastServiceCheckAt) return true;
    const now = Date.now();
    return now - draft.lastServiceCheckAt >= CHECK_FULL_REVALIDATE_MS;
  }, [draft.lastServiceCheckAt]);

  const availableRegions = AWS_REGIONS.filter((region) => !draft.regions.includes(region.value));
  const effectiveControlPlaneToken = revealedControlPlaneToken ?? control_plane_token;
  const canManageControlPlaneToken = user?.role === 'admin';

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const persisted: OnboardingDraft = {
      ...draft,
      updatedAt: Date.now(),
      controlPlaneStackName: sanitizeStackName(draft.controlPlaneStackName),
    };
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(persisted));
  }, [draft]);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (!authLoading && user?.onboarding_completed_at) {
      router.replace('/findings');
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!isAuthenticated || authLoading) return;

    let cancelled = false;
    getAccounts()
      .then((accounts) => {
        if (cancelled) return;
        setExistingAccounts(accounts);
        const matchedAccount = resolveOnboardingConnectedAccount({
          accounts,
          connectedAccountId: draft.connectedAccountId,
          parsedAccountId,
        });
        setConnectedAccount(matchedAccount);
        if (matchedAccount && draft.connectedAccountId !== matchedAccount.id) {
          setDraft((prev) => ({ ...prev, connectedAccountId: matchedAccount.id }));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setExistingAccounts([]);
          setConnectedAccount(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, draft.connectedAccountId, isAuthenticated, parsedAccountId]);

  useEffect(() => {
    if (draft.step !== 'control-plane') return;
    if (!draft.regions.includes(draft.controlPlaneRegion)) {
      setDraft((prev) => ({ ...prev, controlPlaneRegion: prev.regions[0] ?? DEFAULT_REGION }));
    }
  }, [draft.step, draft.controlPlaneRegion, draft.regions]);

  useEffect(() => {
    if (control_plane_token) {
      setRevealedControlPlaneToken(control_plane_token);
    }
  }, [control_plane_token]);

  useEffect(() => {
    if (!isCheckingControlPlane || controlPlaneVerifyPhase === 'idle') return;
    const timer = window.setInterval(() => {
      setControlPlaneVerifyProgress((prev) => nextControlPlaneVerifyProgress(prev, controlPlaneVerifyPhase));
    }, CONTROL_PLANE_VERIFY_PROGRESS_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [controlPlaneVerifyPhase, isCheckingControlPlane]);

  useEffect(() => {
    if (draft.step !== 'processing') return;
    void startInitialProcessing();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.step]);

  function updateDraft(patch: Partial<OnboardingDraft>) {
    setDraft((prev) => ({ ...prev, ...patch }));
  }

  function syncConnectedAccountState(account: AwsAccount) {
    setConnectedAccount(account);
    setExistingAccounts((prev) => upsertAwsAccount(prev, account));
  }

  function clearNotices() {
    setError(null);
    setInfo(null);
  }

  async function runTrackedOperation<T>(opts: {
    type: 'onboarding' | 'account';
    title: string;
    runningMessage: string;
    successMessage: string;
    dedupeKey: string;
    task: () => Promise<T>;
    timeoutMs?: number;
  }): Promise<T> {
    const timeoutMs = opts.timeoutMs ?? 300_000;
    const actorId = user?.id ?? 'anonymous';
    const jobId = addJob({
      type: opts.type,
      title: opts.title,
      message: opts.runningMessage,
      progress: 20,
      dedupeKey: opts.dedupeKey,
      actorId,
      status: 'running',
    });

    let timeoutHandle: ReturnType<typeof setTimeout> | null = null;
    const timeoutPromise = new Promise<never>((_, reject) => {
      timeoutHandle = setTimeout(() => {
        const timeoutError = new Error('operation_timeout');
        timeoutError.name = 'OperationTimeout';
        reject(timeoutError);
      }, timeoutMs);
    });

    try {
      const result = await Promise.race([opts.task(), timeoutPromise]);
      if (timeoutHandle) {
        clearTimeout(timeoutHandle);
      }
      completeJob(jobId, opts.successMessage);
      return result;
    } catch (trackedError) {
      if (timeoutHandle) {
        clearTimeout(timeoutHandle);
      }
      const timedOut = trackedError instanceof Error && trackedError.name === 'OperationTimeout';
      if (timedOut) {
        timeoutJob(
          jobId,
          `${opts.title} timed out.`,
          `No response was received after ${Math.round(timeoutMs / 1000)}s. Retry the check.`
        );
        throw new Error(`${opts.title} timed out. Please retry.`);
      }
      failJob(jobId, `${opts.title} failed.`, getErrorMessage(trackedError));
      throw trackedError;
    }
  }

  function jumpTo(step: StepId) {
    clearNotices();
    setDraft((prev) => ({ ...prev, step }));
  }

  function nextStep() {
    const next = STEP_ORDER[currentStepIndex + 1];
    if (next) jumpTo(next);
  }

  function prevStep() {
    const prev = STEP_ORDER[currentStepIndex - 1];
    if (prev) jumpTo(prev);
  }

  function addRegion(value: string) {
    if (!value || draft.regions.includes(value) || draft.regions.length >= MAX_REGIONS) return;
    updateDraft({ regions: [...draft.regions, value].sort() });
  }

  function removeRegion(value: string) {
    if (draft.regions.length <= 1) return;
    updateDraft({ regions: draft.regions.filter((region) => region !== value) });
  }

  function recordFirstIngestQueue(mode: 'fast_path' | 'processing', queuedAtMs: number, accountId: string) {
    setDraft((prev) => {
      if (prev.firstIngestQueuedAt) return prev;
      return {
        ...prev,
        firstIngestQueuedAt: queuedAtMs,
        firstIngestQueueMode: mode,
      };
    });

    if (!tenant?.id || !draft.integrationValidatedAt) return;
    appendOnboardingMetricSample({
      account_id: accountId,
      tenant_id: tenant.id,
      connected_at: new Date(draft.integrationValidatedAt).toISOString(),
      first_ingest_queued_at: new Date(queuedAtMs).toISOString(),
      first_ingest_queue_mode: mode,
      time_to_first_ingest_ms: Math.max(0, queuedAtMs - draft.integrationValidatedAt),
      captured_at: new Date().toISOString(),
    });
  }

  async function runFirstValueFastPath(accountId: string, silentWhenDeferred: boolean = false) {
    if (draft.fastPathTriggered || isStartingFastPath) return;
    setIsStartingFastPath(true);
    try {
      const result = await triggerOnboardingFastPath(accountId);
      setFastPathResult(result);
      setDraft((prev) => ({
        ...prev,
        fastPathLastAttemptAt: Date.now(),
        fastPathTriggered: result.fast_path_triggered || prev.fastPathTriggered,
        fastPathComputeQueued: result.compute_actions_queued || prev.fastPathComputeQueued,
      }));

      if (result.fast_path_triggered) {
        recordFirstIngestQueue('fast_path', Date.now(), accountId);
        setInfo(result.message);
      } else if (!silentWhenDeferred) {
        setInfo(result.message);
      }
    } catch (err) {
      if (!silentWhenDeferred) {
        setError(getErrorMessage(err));
      }
    } finally {
      setIsStartingFastPath(false);
    }
  }

  async function handleValidateIntegrationRole() {
    if (!tenant) {
      setError('Missing tenant context. Please sign in again.');
      return;
    }
    if (!canValidateIntegrationRole) {
      setError('Enter a valid role ARN, account ID, and at least one region before validation.');
      return;
    }

    clearNotices();
    setIsSubmitting(true);

    try {
      const existingAccount = resolveOnboardingConnectedAccount({
        accounts: existingAccounts,
        connectedAccountId: draft.connectedAccountId,
        parsedAccountId,
        fallbackAccount: connectedAccount,
      });
      const mutation = buildOnboardingAccountMutation({
        existingAccount,
        parsedAccountId,
        regions: draft.regions,
        roleReadArn: draft.integrationRoleArn.trim(),
        tenantId: tenant.id,
      });
      const account = await runTrackedOperation({
        type: 'onboarding',
        title: 'Validate integration role',
        runningMessage: `Validating role access for account ${parsedAccountId}...`,
        successMessage: 'Integration role validated.',
        dedupeKey: `onboarding-validate-role:${parsedAccountId}:${user?.id ?? 'anonymous'}`,
        task: () =>
          mutation.kind === 'update'
            ? updateAccount(mutation.accountId, mutation.payload, tenant.id)
            : registerAccount(mutation.payload),
      });

      syncConnectedAccountState(account);
      setFastPathResult(null);
      const integrationValidatedAt = Date.now();
      setDraft((prev) => ({
        ...prev,
        accountId: parsedAccountId,
        connectedAccountId: account.id,
        integrationValidatedAt,
        firstIngestQueuedAt: null,
        firstIngestQueueMode: null,
        fastPathTriggered: false,
        fastPathComputeQueued: false,
        fastPathLastAttemptAt: null,
      }));
      setInfo(
        mutation.kind === 'update'
          ? 'Integration role revalidated. Updated regions will be used for the remaining onboarding checks.'
          : 'Integration role validated. Fast-path ingestion will start as soon as required data services are ready.'
      );
      void runFirstValueFastPath(account.account_id, true);
      nextStep();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function runServiceReadiness(): Promise<AccountServiceReadiness> {
    if (!connectedAccount) throw new Error('Connect your account first.');
    const result = await runTrackedOperation({
      type: 'onboarding',
      title: 'Run service readiness check',
      runningMessage: `Checking Inspector, Security Hub, and Config for ${connectedAccount.account_id}...`,
      successMessage: 'Service readiness check completed.',
      dedupeKey: `onboarding-service-readiness:${connectedAccount.account_id}:${user?.id ?? 'anonymous'}`,
      task: () => checkAccountServiceReadiness(connectedAccount.account_id),
      timeoutMs: 300_000,
    });
    setServiceReadiness(result);
    setDraft((prev) => ({ ...prev, lastServiceCheckAt: Date.now() }));
    return result;
  }

  async function runControlPlaneReadiness(): Promise<AccountControlPlaneReadiness> {
    if (!connectedAccount) throw new Error('Connect your account first.');
    const result = await runTrackedOperation({
      type: 'onboarding',
      title: 'Run control-plane readiness check',
      runningMessage: `Checking control-plane intake for ${connectedAccount.account_id}...`,
      successMessage: 'Control-plane readiness check completed.',
      dedupeKey: `onboarding-control-plane-readiness:${connectedAccount.account_id}:${user?.id ?? 'anonymous'}`,
      task: () => checkAccountControlPlaneReadiness(connectedAccount.account_id, 30),
      timeoutMs: 300_000,
    });
    setControlPlaneReadiness(result);
    setDraft((prev) => ({ ...prev, lastControlPlaneCheckAt: Date.now() }));
    return result;
  }

  async function pollControlPlaneReadiness(accountId: string): Promise<AccountControlPlaneReadiness> {
    const deadline = Date.now() + CONTROL_PLANE_POLL_MAX_WAIT_MS;
    let latest = await checkAccountControlPlaneReadiness(accountId, 30);
    while (!latest.overall_ready && Date.now() < deadline) {
      await sleep(CONTROL_PLANE_POLL_INTERVAL_MS);
      latest = await checkAccountControlPlaneReadiness(accountId, 30);
    }
    return latest;
  }

  async function runControlPlaneReadinessWithPolling(accountId: string): Promise<AccountControlPlaneReadiness> {
    const result = await runTrackedOperation({
      type: 'onboarding',
      title: 'Run control-plane readiness check',
      runningMessage: `Checking control-plane intake for ${accountId} (polling up to 90s)...`,
      successMessage: 'Control-plane readiness check completed.',
      dedupeKey: `onboarding-control-plane-readiness:${accountId}:${user?.id ?? 'anonymous'}`,
      task: () => pollControlPlaneReadiness(accountId),
      timeoutMs: CONTROL_PLANE_POLL_MAX_WAIT_MS + 30_000,
    });
    setControlPlaneReadiness(result);
    setDraft((prev) => ({ ...prev, lastControlPlaneCheckAt: Date.now() }));
    return result;
  }

  function missingSyntheticTokenReason(): string {
    if (canManageControlPlaneToken) {
      return 'Automated verification unavailable: no active revealed control-plane token in this session. Rotate and reveal a token first.';
    }
    return 'Automated verification unavailable: this user cannot access a revealed control-plane token. Ask a tenant admin to rotate and share one.';
  }

  async function trySyntheticControlPlaneEvent(
    accountId: string,
    region: string
  ): Promise<SyntheticControlPlaneAttempt> {
    const token = (effectiveControlPlaneToken || '').trim();
    if (!token) {
      try {
        const result = await runTrackedOperation({
          type: 'onboarding',
          title: 'Send control-plane verification event',
          runningMessage: `Sending control-plane verification event for ${accountId} (${region})...`,
          successMessage: 'Control-plane verification event sent.',
          dedupeKey: `onboarding-control-plane-synthetic:${accountId}:${region}:${user?.id ?? 'anonymous'}`,
          task: () => sendSyntheticControlPlaneEventForAccount(accountId, region),
          timeoutMs: 30_000,
        });
        if (result.enqueued > 0) return { sent: true, fallbackReason: null };
        const reasons = formatDropReasons(result.drop_reasons || {});
        const detail = reasons ? ` (${reasons})` : '';
        return { sent: false, fallbackReason: `Verification event was dropped by intake${detail}.` };
      } catch (err) {
        return {
          sent: false,
          fallbackReason: `${missingSyntheticTokenReason()} Account-scoped verification failed: ${getErrorMessage(err)}.`,
        };
      }
    }
    try {
      const result = await runTrackedOperation({
        type: 'onboarding',
        title: 'Send control-plane verification event',
        runningMessage: `Sending control-plane verification event for ${accountId} (${region})...`,
        successMessage: 'Control-plane verification event sent.',
        dedupeKey: `onboarding-control-plane-synthetic:${accountId}:${region}:${user?.id ?? 'anonymous'}`,
        task: async () => {
          try {
            const directResult = await sendSyntheticControlPlaneEvent(accountId, region, token);
            if (directResult.enqueued > 0 || directResult.dropped === 0) {
              return directResult;
            }
            const reasons = formatDropReasons(directResult.drop_reasons || {});
            try {
              return await sendSyntheticControlPlaneEventForAccount(accountId, region);
            } catch (proxyErr) {
              throw new Error(
                `Direct verification-event intake dropped the event${reasons ? ` (${reasons})` : ''}. ` +
                  `Fallback account-path failed (${getErrorMessage(proxyErr)}).`
              );
            }
          } catch (err) {
            try {
              return await sendSyntheticControlPlaneEventForAccount(accountId, region);
            } catch (proxyErr) {
              throw new Error(
                `Direct verification-event intake failed (${getErrorMessage(err)}). ` +
                  `Fallback account-path failed (${getErrorMessage(proxyErr)}).`
              );
            }
          }
        },
        timeoutMs: 30_000,
      });
      if (result.enqueued > 0) return { sent: true, fallbackReason: null };
      const reasons = formatDropReasons(result.drop_reasons || {});
      const detail = reasons ? ` (${reasons})` : '';
      return { sent: false, fallbackReason: `Verification event was dropped by intake${detail}.` };
    } catch (err) {
      return { sent: false, fallbackReason: `Automated verification failed: ${getErrorMessage(err)}.` };
    }
  }

  async function handleVerifyInspector() {
    clearNotices();
    setIsCheckingInspector(true);
    try {
      const result = await runServiceReadiness();
      if (result.missing_inspector_regions.length > 0) {
        setError(`Inspector is still missing in: ${result.missing_inspector_regions.join(', ')}.`);
        return;
      }
      setDraft((prev) => ({ ...prev, inspectorVerified: true }));
      setInfo('Inspector verification passed.');
      nextStep();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsCheckingInspector(false);
    }
  }

  function openControlPlaneLaunchUrl(url: string) {
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  async function handleLaunchControlPlaneStack() {
    if (controlPlaneLaunchUrl) return openControlPlaneLaunchUrl(controlPlaneLaunchUrl);
    if (!canManageControlPlaneToken) {
      setError('Launch Stack needs a revealed control-plane token. Ask a tenant admin to rotate and reveal one.');
      return;
    }
    setError('Token is hidden. Use Rotate Token explicitly, then relaunch CloudFormation and update the deployed forwarder stack.');
  }

  async function handleVerifySecurityHubAndConfig() {
    clearNotices();
    setIsCheckingSecurityHub(true);
    try {
      if (!connectedAccount) {
        setError('Connect your account first.');
        return;
      }
      const accountId = connectedAccount.account_id;
      const result = await runServiceReadiness();
      const missing: string[] = [];
      if (result.missing_security_hub_regions.length > 0) {
        missing.push(`Security Hub: ${result.missing_security_hub_regions.join(', ')}`);
      }
      if (result.missing_aws_config_regions.length > 0) {
        missing.push(`AWS Config: ${result.missing_aws_config_regions.join(', ')}`);
      }
      if (missing.length > 0) {
        setError(`Required services still missing -> ${missing.join(' | ')}`);
        return;
      }
      setDraft((prev) => ({ ...prev, securityHubConfigVerified: true }));
      await runFirstValueFastPath(accountId);
      setInfo('Security Hub and AWS Config verification passed. First-value ingest was queued early when safe.');
      nextStep();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsCheckingSecurityHub(false);
    }
  }

  async function handleVerifyControlPlane() {
    clearNotices();
    setIsCheckingControlPlane(true);
    setControlPlaneVerifyPhase('sending');
    setControlPlaneVerifyProgress(14);
    try {
      if (!connectedAccount) {
        setError('Connect your account first.');
        return;
      }
      const accountId = connectedAccount.account_id;
      const region = draft.controlPlaneRegion || draft.regions[0] || DEFAULT_REGION;
      const synthetic = await trySyntheticControlPlaneEvent(accountId, region);
      setControlPlaneVerifyPhase('polling');
      setControlPlaneVerifyProgress((prev) => Math.max(prev, 38));
      const result = await runControlPlaneReadinessWithPolling(accountId);
      if (!result.overall_ready) {
        const missing = result.missing_regions.join(', ') || 'unknown regions';
        setError(buildControlPlaneFailureMessage(missing, synthetic));
        return;
      }
      setDraft((prev) => ({ ...prev, controlPlaneVerified: true }));
      setInfo(controlPlaneSuccessMessage(synthetic.sent));
      nextStep();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsCheckingControlPlane(false);
      setControlPlaneVerifyPhase('idle');
      setControlPlaneVerifyProgress(0);
    }
  }

  async function handleRotateControlPlaneToken() {
    clearNotices();
    setIsRotatingControlPlaneToken(true);
    try {
      const token = await rotateControlPlaneToken();
      setRevealedControlPlaneToken(token);
      setInfo('Rotated control-plane token. Update any deployed forwarder stack before the previous token grace window expires.');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsRotatingControlPlaneToken(false);
    }
  }

  async function handleRevokeControlPlaneToken() {
    clearNotices();
    try {
      await revokeControlPlaneToken();
      setRevealedControlPlaneToken(null);
      setInfo('Control-plane token revoked. Rotate to generate a new token before launching or updating forwarders.');
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function handleRunFinalChecks() {
    if (!connectedAccount) {
      setError('Connect and validate an account before final checks.');
      return;
    }

    clearNotices();
    setIsRunningFinalChecks(true);

    try {
      if (shouldFullRevalidateRequiredChecks) {
        setResumeNotice('Saved checks are older than 24 hours. Running full re-validation now.');
      } else if (shouldQuickRevalidateRequiredChecks) {
        setResumeNotice('Saved checks are older than 15 minutes. Running quick re-validation now.');
      } else {
        setResumeNotice(null);
      }

      const service = await runServiceReadiness();

      const requiredMissing: string[] = [];
      if (service.missing_inspector_regions.length > 0) {
        requiredMissing.push(`Inspector: ${service.missing_inspector_regions.join(', ')}`);
      }
      if (service.missing_security_hub_regions.length > 0) {
        requiredMissing.push(`Security Hub: ${service.missing_security_hub_regions.join(', ')}`);
      }
      if (service.missing_aws_config_regions.length > 0) {
        requiredMissing.push(`AWS Config: ${service.missing_aws_config_regions.join(', ')}`);
      }
      if (requiredMissing.length > 0) {
        setError(`Final checks failed -> ${requiredMissing.join(' | ')}`);
        return;
      }

      const controlPlane = await runControlPlaneReadiness();
      if (!controlPlane.overall_ready) {
        setError(
          `Final checks failed -> Control-plane intake missing for: ${controlPlane.missing_regions.join(', ') || 'unknown regions'}`
        );
        return;
      }

      setDraft((prev) => ({
        ...prev,
        inspectorVerified: true,
        securityHubConfigVerified: true,
        controlPlaneVerified: true,
      }));
      if (!draft.fastPathTriggered) {
        await runFirstValueFastPath(connectedAccount.account_id, true);
      }
      setInfo('All required checks passed. Starting initial processing.');
      nextStep();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsRunningFinalChecks(false);
    }
  }

  async function startInitialProcessing() {
    if (!connectedAccount || !user) return;

    clearNotices();
    setIsSubmitting(true);

    const accountId = connectedAccount.account_id;
    const findingsJobId = addJob({
      type: 'findings',
      title: 'Loading findings',
      message: `Starting findings ingestion for account ${accountId}...`,
      progress: 12,
      resourceId: accountId,
      actorId: user.id,
      dedupeKey: `first-run-findings:${accountId}:${user.id}`,
    });

    const actionsJobId = addJob({
      type: 'actions',
      title: 'Computing actions',
      message: `Preparing remediation actions for account ${accountId}...`,
      progress: 12,
      resourceId: accountId,
      actorId: user.id,
      dedupeKey: `first-run-actions:${accountId}:${user.id}`,
    });

    try {
      const shouldQueueIngest = !draft.fastPathTriggered;
      const shouldQueueCompute = !draft.fastPathComputeQueued;
      const queueOperations: Promise<unknown>[] = [];
      if (shouldQueueIngest) {
        queueOperations.push(triggerIngest(accountId, undefined, connectedAccount.regions));
      }
      if (shouldQueueCompute) {
        queueOperations.push(triggerComputeActions({ account_id: accountId }));
      }
      if (queueOperations.length > 0) {
        await Promise.all(queueOperations);
      }
      if (shouldQueueIngest) {
        recordFirstIngestQueue('processing', Date.now(), accountId);
      }

      updateJob(findingsJobId, {
        progress: 45,
        status: 'running',
        message: shouldQueueIngest
          ? 'Finding ingestion queued. We will continue tracking on Findings.'
          : 'Finding ingestion was already queued earlier via fast path. Continuing tracking on Findings.',
      });
      updateJob(actionsJobId, {
        progress: 45,
        status: 'running',
        message: shouldQueueCompute
          ? 'Action computation queued. We will continue tracking on Findings.'
          : 'Action computation was already queued earlier via fast path. Continuing tracking on Findings.',
      });

      await markOnboardingComplete();

      if (typeof window !== 'undefined') {
        localStorage.setItem(
          FIRST_RUN_STORAGE_KEY,
          JSON.stringify({
            accountId,
            startedAt: Date.now(),
            findingsJobId,
            actionsJobId,
          })
        );
      }

      setInfo('Initial processing started. Redirecting to Findings...');
      router.replace(
        `/findings?first_run=1&account_id=${encodeURIComponent(accountId)}&findings_job_id=${encodeURIComponent(
          findingsJobId
        )}&actions_job_id=${encodeURIComponent(actionsJobId)}`
      );
    } catch (err) {
      const message = getErrorMessage(err);
      failJob(findingsJobId, 'Failed to start findings ingestion.', message);
      failJob(actionsJobId, 'Failed to start action computation.', message);
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <p className="text-muted animate-pulse">Loading onboarding...</p>
      </div>
    );
  }

  const readStackName = read_role_default_stack_name;
  const controlPlaneStackName = sanitizeStackName(draft.controlPlaneStackName || control_plane_forwarder_default_stack_name);
  const readRoleLaunchUrl = buildReadRoleLaunchStackUrl(readStackName) ?? read_role_launch_stack_url;

  const primaryRegion = draft.regions[0] || DEFAULT_REGION;
  const controlPlaneRegion = draft.controlPlaneRegion || primaryRegion;
  const controlPlaneVerifyLabel = isCheckingControlPlane ? `Verifying intake ${controlPlaneVerifyProgress}%` : 'Verify Intake';
  const inspectorUrl = `https://${primaryRegion}.console.aws.amazon.com/inspector/v2/home?region=${primaryRegion}#/getting-started`;
  const securityHubUrl = `https://${primaryRegion}.console.aws.amazon.com/securityhub/home?region=${primaryRegion}#/get-started`;
  const awsConfigUrl = `https://${primaryRegion}.console.aws.amazon.com/config/home?region=${primaryRegion}#/wizard`;
  const controlPlaneLaunchUrl = buildControlPlaneForwarderLaunchStackUrl(
    controlPlaneRegion,
    controlPlaneStackName,
    effectiveControlPlaneToken
  );

  const welcomePrerequisites = [
    {
      icon: 'shield' as const,
      title: 'Administrator Access',
      body: 'You must have Administrator access to the target AWS account to deploy CloudFormation.',
    },
    {
      icon: 'globe' as const,
      title: 'Region Availability',
      body: 'Ensure your target region is supported by our integration framework.',
    },
  ];

  const currentStepLabel = `Step ${Math.min(currentStepIndex + 1, STEP_ORDER.length)} of ${STEP_ORDER.length}`;
  const currentStepIsOptional = OPTIONAL_STEPS.has(draft.step);
  const useCompactLayout = true;
  return (
    <div className="onboarding-shell onboarding-scroll relative min-h-screen overflow-hidden px-4 py-5 md:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute left-[-12rem] top-[-10rem] h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,rgba(11,113,255,0.24),transparent_62%)] blur-3xl" />
        <div className="absolute bottom-[-14rem] right-[-10rem] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(15,46,155,0.3),transparent_68%)] blur-3xl" />
        <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.02),transparent_35%,transparent_65%,rgba(11,113,255,0.05))]" />
      </div>

      <div className="onboarding-frame relative mx-auto max-w-[1520px] lg:overflow-hidden lg:rounded-[28px]">
        <div className="lg:grid lg:min-h-[calc(100vh-2.5rem)] lg:grid-cols-[250px_minmax(0,1fr)] lg:gap-0">
          <aside className="onboarding-sidebar hidden lg:flex lg:min-h-[calc(100vh-2.5rem)] lg:flex-col lg:p-6">
            <div>
              <div className="mb-12 flex items-center gap-3">
                <div className="onboarding-sidebar-logo flex h-8 w-8 items-center justify-center rounded-full text-white">
                  <svg aria-hidden className="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24">
                    <path
                      d="M6.5 18a3.5 3.5 0 010-7c.3 0 .6 0 .9.1A5.5 5.5 0 0118 9.5h.3a3.2 3.2 0 010 6.5H6.5z"
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="1.8"
                    />
                  </svg>
                </div>
                <p className="onboarding-display text-lg font-bold tracking-[0.04em] text-[var(--onboarding-text-strong)]">AWS Link</p>
              </div>

              <ol className="relative space-y-6">
                <div className="onboarding-step-track absolute bottom-4 left-[11px] top-4 w-px" />
                {SIDEBAR_STEP_LABELS.map((sidebarStep, index) => {
                  const step = STEP_ORDER[index];
                  const isActive = index === currentStepIndex;
                  const canJump = index <= currentStepIndex;
                  return (
                    <li key={step} className="relative z-10">
                      <button
                        type="button"
                        onClick={() => {
                          if (canJump) jumpTo(step);
                        }}
                        disabled={!canJump}
                        className="group flex w-full items-start gap-4 text-left disabled:cursor-default"
                      >
                        <span
                          className={`onboarding-step-node mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition-all duration-300 ${isActive
                            ? 'onboarding-step-node-active'
                            : 'onboarding-step-node-default'
                            }`}
                        >
                          <span
                            className={`onboarding-step-dot rounded-full ${isActive
                              ? 'h-2.5 w-2.5 bg-[#0B71FF] shadow-[0_0_14px_rgba(11,113,255,0.65)]'
                              : 'h-2 w-2 bg-[var(--onboarding-step-dot)] transition-colors duration-300 group-hover:bg-[var(--onboarding-step-dot-hover)]'
                              }`}
                          />
                        </span>
                        <div className="min-w-0">
                          <p className={`text-sm leading-tight ${isActive ? 'font-semibold text-[var(--onboarding-text-strong)]' : 'font-medium text-[var(--onboarding-text-muted)] group-hover:text-[var(--onboarding-text-strong)]'}`}>
                            {sidebarStep.title}
                          </p>
                          {sidebarStep.subtitle ? (
                            <p className="mt-1 text-xs text-[var(--onboarding-text-muted)]">
                              {sidebarStep.subtitle}
                            </p>
                          ) : null}
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ol>
            </div>

          </aside>

          <main className="min-w-0 lg:px-8 lg:py-6 xl:px-10">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div className="lg:hidden">
                <p className="onboarding-display text-xs font-bold uppercase tracking-[0.24em] text-[var(--onboarding-text-muted)]">{currentStepLabel}</p>
                <h1 className="onboarding-display mt-1 text-lg font-bold text-[var(--onboarding-text-strong)]">{sectionTitle(draft.step)}</h1>
              </div>
              <div className="ml-auto flex items-center gap-3">
                <div className="lg:hidden">
                  <StatusPill tone={currentStepIsOptional ? 'default' : 'info'}>
                    {currentStepIsOptional ? 'Optional' : 'Required'}
                  </StatusPill>
                </div>
                <NeedHelpLink from="/onboarding" label="Need onboarding help?" variant="secondary" />
                <ThemeToggle />
              </div>
            </div>

            <section className={`onboarding-card overflow-hidden rounded-[30px] ${useCompactLayout ? 'lg:flex lg:h-[calc(100vh-8rem)] lg:flex-col' : ''}`}>
              <div className={`border-b border-[var(--onboarding-divider)] px-6 py-6 sm:px-8 ${useCompactLayout ? 'lg:px-8 lg:py-5' : 'lg:px-10'}`}>
                <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
                  <div className="max-w-3xl">
                    <p className="onboarding-display text-xs font-bold uppercase tracking-[0.28em] text-[#0B71FF]">{currentStepLabel}</p>
                    <h1 className="onboarding-display mt-3 text-3xl font-bold tracking-[-0.04em] text-[var(--onboarding-text-strong)] md:text-4xl">
                      {sectionTitle(draft.step)}
                    </h1>
                    <p className="mt-3 max-w-2xl text-base leading-7 text-[var(--onboarding-text-muted)] md:text-lg">
                      {stepDescription(draft.step)}
                    </p>
                  </div>
                </div>
              </div>

              <div className={`px-6 py-6 sm:px-8 ${useCompactLayout ? 'lg:flex lg:min-h-0 lg:flex-1 lg:flex-col lg:px-8 lg:py-5 overflow-y-auto scrollbar-hide' : 'lg:px-10'}`}>
                {resumeNotice && (
                  <div className="mb-5 flex items-start justify-between gap-3 rounded-[20px] bg-[#f59e0b]/10 px-5 py-4 text-sm leading-6 text-[#facc15]">
                    <span>{resumeNotice}</span>
                    <button onClick={() => setResumeNotice(null)} className="mt-0.5 shrink-0 text-lg leading-none opacity-60 hover:opacity-100 transition-opacity" aria-label="Dismiss">×</button>
                  </div>
                )}
                {error && (
                  <div className="mb-5 flex items-start justify-between gap-3 rounded-[20px] bg-[#ff4444]/10 px-5 py-4 text-sm leading-6 text-[#ff9a9a]">
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="mt-0.5 shrink-0 text-lg leading-none opacity-60 hover:opacity-100 transition-opacity" aria-label="Dismiss">×</button>
                  </div>
                )}
                {info && (
                  <div className="mb-5 flex items-start justify-between gap-3 rounded-[20px] bg-[#00E676]/10 px-5 py-4 text-sm leading-6 text-[#8CF6B7]">
                    <span>{info}</span>
                    <button onClick={() => setInfo(null)} className="mt-0.5 shrink-0 text-lg leading-none opacity-60 hover:opacity-100 transition-opacity" aria-label="Dismiss">×</button>
                  </div>
                )}

                <div key={draft.step} className="onboarding-content">
                  {draft.step === 'welcome' && (
                    <div className="space-y-8">
                      <div className="grid gap-4 md:grid-cols-2">
                        {welcomePrerequisites.map((highlight, index) => (
                          <article
                            key={highlight.title}
                            className="onboarding-inset onboarding-welcome-card flex min-h-[160px] flex-col rounded-[22px] p-4"
                            style={{ animationDelay: `${index * 90}ms` }}
                          >
                            <div className="onboarding-welcome-icon flex h-10 w-10 items-center justify-center rounded-full text-[#0B71FF]">
                              <WelcomeIcon kind={highlight.icon} />
                            </div>
                            <p className="onboarding-display mt-3 text-[12px] font-bold uppercase tracking-[0.2em] text-[#0B71FF]">
                              {highlight.title}
                            </p>
                            <p className="mt-2 text-[12px] leading-relaxed text-[var(--onboarding-text-body)]">{highlight.body}</p>
                          </article>
                        ))}
                      </div>

                      <div className="grid gap-4 lg:grid-cols-[1.25fr_0.95fr]">
                        <div className={`${PANEL_CLASS_LARGE} !p-4`}>
                          <p className="onboarding-display text-base font-bold tracking-[-0.03em] text-[var(--onboarding-text-strong)]">Before you begin</p>
                          <p className="mt-2 text-sm leading-relaxed text-[var(--onboarding-text-body)]">
                            This guided flow prioritizes minimal permissions, clear validation, and safe cost defaults.
                          </p>
                        </div>
                        <div className={`${INSET_PANEL_CLASS_LARGE} !p-4`}>
                          <p className="onboarding-display text-[11px] font-bold uppercase tracking-[0.22em] text-[var(--onboarding-text-muted)]">
                            Minimum successful path
                          </p>
                          <p className="mt-2 text-sm leading-relaxed text-[var(--onboarding-text-body)]">
                            Complete required gates first to reach first findings as early as it is safe to do so.
                          </p>
                        </div>
                      </div>

                    </div>
                  )}

                  {draft.step === 'integration-role' && (
                    <div className="space-y-3 lg:flex lg:min-h-0 lg:flex-1 lg:flex-col">
                      <div className="flex flex-col gap-3 lg:items-stretch">
                        <div className="onboarding-panel rounded-[22px] p-5 lg:p-6 flex flex-col justify-center">
                          <p className="onboarding-display text-[11px] font-bold tracking-widest text-[var(--onboarding-text-muted)] uppercase mb-5">Deployment steps</p>
                          <div className="space-y-4">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                                1. Launch stack, deploy <strong>read-role</strong>
                              </p>
                              {readRoleLaunchUrl && (
                                <a
                                  href={readRoleLaunchUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex min-h-7 items-center justify-center rounded-[8px] bg-[#0B71FF] px-2.5 py-1 text-xs font-semibold text-white shadow-[0_0_12px_rgba(11,113,255,0.3)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_0_20px_rgba(11,113,255,0.5)]"
                                >
                                  Open CloudFormation Launch Stack
                                </a>
                              )}
                              <p className="text-[13px] leading-snug text-[var(--onboarding-text-body)]">.</p>
                            </div>

                            <div className="flex flex-wrap gap-2 items-center">
                              <p className="text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                                2. In parameters, enter <strong>Platform Account ID</strong>
                              </p>
                              {saas_account_id && (
                                <div className="onboarding-chip-info flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium bg-[var(--onboarding-layer-accent)]/5 text-[var(--onboarding-text-muted)] border border-[var(--onboarding-text-soft)]/10">
                                  <span><span className="font-bold text-[var(--onboarding-text-strong)]">{saas_account_id}</span></span>
                                  <CopyButton text={saas_account_id} title="Copy Platform Account ID" />
                                </div>
                              )}
                              <p className="text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                                and <strong>External ID</strong>
                              </p>
                              {tenant?.external_id && (
                                <div className="onboarding-chip-info flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium bg-[var(--onboarding-layer-accent)]/5 text-[var(--onboarding-text-muted)] border border-[var(--onboarding-text-soft)]/10">
                                  <span><span className="font-bold text-[var(--onboarding-text-strong)]">{tenant.external_id}</span></span>
                                  <CopyButton text={tenant.external_id} title="Copy External ID" />
                                </div>
                              )}
                              <p className="text-[13px] leading-snug text-[var(--onboarding-text-body)]">.</p>
                            </div>

                            <p className="text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                              3. Wait for stack <strong>CREATE_COMPLETE</strong>.
                            </p>
                            <p className="text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                              4. Go to CloudFormation &gt; Stacks &gt; <strong>SecurityAutopilotReadRole</strong> &gt; Resources.
                            </p>
                            <p className="text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                              5. Copy the component <strong>ReadRoleCustomResource</strong>. Paste ARN below.
                            </p>
                            <p className="text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                              6. Add monitored regions (up to 5) and validate.
                            </p>
                          </div>
                        </div>
                      </div>

                      <div className="grid gap-3">
                        <FormField label="Integration Role ARN (required)">
                          <input
                            className={`${INPUT_CLASS} !py-2.5`}
                            placeholder="arn:aws:iam::123456789012:role/SecurityAutopilotIntegrationRole"
                            value={draft.integrationRoleArn}
                            onChange={(event) => {
                              const value = event.target.value;
                              updateDraft({ integrationRoleArn: value });
                              if (!draft.accountId) {
                                const inferred = parseAccountIdFromRoleArn(value);
                                if (inferred) updateDraft({ accountId: inferred });
                              }
                            }}
                          />
                        </FormField>
                      </div>

                      <div className="onboarding-panel rounded-[22px] p-4">
                        <div className="flex items-center justify-between gap-4">
                          <div className="flex-1">
                            <p className="onboarding-display text-[11px] font-bold tracking-widest text-[var(--onboarding-text-muted)] uppercase mb-2">Monitored regions</p>
                            <div className="flex flex-wrap gap-1.5 min-h-[32px]">
                              {draft.regions.map((region) => (
                                <span key={region} className="inline-flex items-center gap-1.5 rounded-full bg-[var(--onboarding-text-soft)]/10 px-2.5 py-1 text-[11px] font-bold text-[var(--onboarding-text-strong)] border border-[var(--onboarding-text-soft)]/10">
                                  {region}
                                  <button
                                    type="button"
                                    onClick={() => removeRegion(region)}
                                    disabled={draft.regions.length <= 1}
                                    className="text-[var(--onboarding-text-muted)] hover:text-red-400 transition-colors disabled:opacity-30"
                                  >
                                    ×
                                  </button>
                                </span>
                              ))}
                            </div>
                          </div>
                          <div className="shrink-0">
                            <SelectDropdown
                              value=""
                              onValueChange={addRegion}
                              options={[{ value: '', label: 'Add region...' }, ...availableRegions]}
                              aria-label="Add AWS region"
                              triggerClassName="!h-9 !text-[12px] !min-w-[160px] !rounded-[10px]"
                              contentClassName={SELECT_CONTENT_CLASS}
                            />
                          </div>
                        </div>
                      </div>

                      </div>
                    )}

                  {draft.step === 'inspector' && (
                    <div className="space-y-4">
                      <div className="onboarding-panel rounded-[22px] p-4">
                        <p className="onboarding-display text-[13px] font-bold tracking-wider text-[var(--onboarding-text-muted)] uppercase">Cost-aware Inspector defaults</p>
                        <ol className="mt-2 list-decimal space-y-1 pl-4 text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                          <li className="flex flex-wrap items-center gap-2">
                            <span>Open AWS Inspector -&gt; <strong>Get started</strong>.</span>
                            <a
                              href={inspectorUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex min-h-7 items-center justify-center rounded-[8px] bg-[#0B71FF] px-2.5 py-1 text-xs font-semibold text-white shadow-[0_0_12px_rgba(11,113,255,0.3)] transition-all duration-200 hover:-translate-y-0.5"
                            >
                              Open AWS Inspector
                            </a>
                          </li>
                        </ol>
                      </div>

                      {serviceReadiness && (
                        <div className="onboarding-inset rounded-[20px] p-3 text-[12px] text-[var(--onboarding-text-body)] border border-[var(--onboarding-text-soft)]/10">
                          <span className="font-bold text-[var(--onboarding-text-muted)] uppercase tracking-tight mr-2">Missing regions:</span>
                          {serviceReadiness.missing_inspector_regions.join(', ') || 'none'}
                        </div>
                      )}

                    </div>
                  )}

                  {draft.step === 'security-hub-config' && (
                    <div className="space-y-4">
                      <div className="onboarding-panel rounded-[22px] p-4">
                        <p className="onboarding-display text-[13px] font-bold tracking-wider text-[var(--onboarding-text-muted)] uppercase">Required enablement steps</p>
                        <ol className="mt-2 list-decimal space-y-1 pl-4 text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                          <li className="flex flex-wrap items-center gap-2">
                            <span>Enable <strong>AWS Config</strong> recorder in each region first (Choose <strong>1-click setup</strong>).</span>
                            <a
                              href={awsConfigUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex min-h-7 items-center justify-center rounded-[8px] bg-[#0B71FF] px-2.5 py-1 text-xs font-semibold text-white shadow-[0_0_12px_rgba(11,113,255,0.3)] transition-all duration-200 hover:-translate-y-0.5"
                            >
                              Open AWS Config
                            </a>
                          </li>
                          <li className="flex flex-wrap items-center gap-2">
                            <span>Enable <strong>Security Hub</strong> in each region.</span>
                            <a
                              href={securityHubUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex min-h-7 items-center justify-center rounded-[8px] bg-[#0B71FF] px-2.5 py-1 text-xs font-semibold text-white shadow-[0_0_12px_rgba(11,113,255,0.3)] transition-all duration-200 hover:-translate-y-0.5"
                            >
                              Open Security Hub
                            </a>
                          </li>
                          <li>Select <strong>AWS Foundational Best Practices v1.0.0</strong>.</li>
                        </ol>
                        <p className="mt-2 text-[11px] text-[var(--onboarding-text-muted)] italic">
                          * Config is required for Security Hub compliance evaluations.
                        </p>
                      </div>

                      {serviceReadiness && (
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="onboarding-inset rounded-[18px] p-3 text-[12px] border border-[var(--onboarding-text-soft)]/10">
                            <p className="font-bold text-[10px] text-[var(--onboarding-text-muted)] uppercase mb-1">Missing Security Hub</p>
                            <p className="truncate text-[var(--onboarding-text-body)]">{serviceReadiness.missing_security_hub_regions.join(', ') || 'none'}</p>
                          </div>
                          <div className="onboarding-inset rounded-[18px] p-3 text-[12px] border border-[var(--onboarding-text-soft)]/10">
                            <p className="font-bold text-[10px] text-[var(--onboarding-text-muted)] uppercase mb-1">Missing AWS Config</p>
                            <p className="truncate text-[var(--onboarding-text-body)]">{serviceReadiness.missing_aws_config_regions.join(', ') || 'none'}</p>
                          </div>
                        </div>
                      )}

                    </div>
                  )}

                  {draft.step === 'control-plane' && (
                    <div className="space-y-4">
                      <div className="onboarding-panel rounded-[22px] p-5">
                        <p className="onboarding-display text-[13px] font-bold tracking-wider text-[var(--onboarding-text-muted)] uppercase mb-4">Deploy forwarding stack</p>
                        
                        <div className="grid gap-6 lg:grid-cols-2">
                          <div className="space-y-4">
                            <ol className="list-decimal space-y-4 pl-4 text-[13px] leading-snug text-[var(--onboarding-text-body)]">
                              <li className="flex flex-wrap items-center gap-3">
                                <span>Select region &amp; open CloudFormation:</span>
                                <button
                                  type="button"
                                  onClick={handleLaunchControlPlaneStack}
                                  disabled={isLaunchingControlPlane}
                                  className="inline-flex min-h-8 items-center justify-center rounded-[10px] bg-[#0B71FF] px-4 py-1.5 text-xs font-semibold text-white shadow-[0_0_12px_rgba(11,113,255,0.3)] transition-all duration-200 hover:-translate-y-0.5"
                                >
                                  {isLaunchingControlPlane ? 'Opening CloudFormation...' : 'Launch CloudFormation'}
                                </button>
                              </li>
                              <li>
                                <div className="space-y-2">
                                  <span>Paste <strong>PlatformIngestUrl</strong> &amp; <strong>Token</strong>:</span>
                                  <div className="flex flex-col gap-2.5 mt-1">
                                    <div className="flex items-center gap-2">
                                      <span className="text-[11px] font-bold text-[var(--onboarding-text-muted)] w-24 uppercase tracking-tighter">URL:</span>
                                      {control_plane_ingest_url && (
                                        <div className="onboarding-chip-info flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium bg-[var(--onboarding-layer-accent)]/5 text-[var(--onboarding-text-muted)] border border-[var(--onboarding-text-soft)]/10 max-w-full overflow-hidden">
                                          <span className="truncate font-bold text-[var(--onboarding-text-strong)]">{control_plane_ingest_url}</span>
                                          <CopyButton text={control_plane_ingest_url} title="Copy Ingest URL" />
                                        </div>
                                      )}
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <span className="text-[11px] font-bold text-[var(--onboarding-text-muted)] w-24 uppercase tracking-tighter">Token:</span>
                                      <div className="onboarding-chip-info flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium bg-[var(--onboarding-layer-accent)]/5 text-[var(--onboarding-text-muted)] border border-[var(--onboarding-text-soft)]/10">
                                        <span className="font-bold text-[var(--onboarding-text-strong)]">
                                          {effectiveControlPlaneToken || 'Token hidden'}
                                        </span>
                                        {effectiveControlPlaneToken && <CopyButton text={effectiveControlPlaneToken} title="Copy Token" />}
                                        {canManageControlPlaneToken && (
                                          <button
                                            onClick={handleRotateControlPlaneToken}
                                            disabled={isRotatingControlPlaneToken}
                                            className={`ml-1 text-[var(--onboarding-text-muted)] hover:text-[#0B71FF] transition-all duration-300 ${isRotatingControlPlaneToken ? 'animate-spin' : ''}`}
                                            title="Rotate Token"
                                          >
                                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                            </svg>
                                          </button>
                                        )}
                                        {canManageControlPlaneToken && control_plane_token_active && (
                                          <button onClick={handleRevokeControlPlaneToken} className="ml-2 text-[10px] font-bold uppercase tracking-wider text-red-500/70 hover:text-red-500 transition-colors">
                                            Revoke
                                          </button>
                                        )}
                                      </div>
                                    </div>
                                    <p className="text-[11px] leading-5 text-[var(--onboarding-text-muted)]">
                                      Rotating reveals a new token and starts the grace window for the previous one. Update every deployed forwarder stack before that window expires.
                                    </p>
                                  </div>
                                </div>
                              </li>
                              <li>Click <strong>Verify</strong> (90s timeout).</li>
                            </ol>
                          </div>

                          <div className="space-y-4 border-l border-[var(--onboarding-text-soft)]/10 pl-6">
                            <FormField label="Target Region">
                              <SelectDropdown
                                value={draft.controlPlaneRegion}
                                onValueChange={(value) => updateDraft({ controlPlaneRegion: value })}
                                options={draft.regions.map((region) => ({ value: region, label: region }))}
                                aria-label="Control-plane region"
                                triggerClassName="!h-10 !text-[13px] !rounded-[12px]"
                                contentClassName={SELECT_CONTENT_CLASS}
                              />
                            </FormField>
                            <FormField label="Stack Name">
                              <input
                                className={`${INPUT_CLASS} !py-2`}
                                value={controlPlaneStackName ?? ''}
                                onChange={(event) => updateDraft({ controlPlaneStackName: event.target.value })}
                                placeholder={control_plane_forwarder_default_stack_name}
                              />
                            </FormField>
                          </div>
                        </div>
                      </div>

                      {controlPlaneReadiness && (
                        <div className="onboarding-inset rounded-[18px] p-3 text-[12px] border border-[var(--onboarding-text-soft)]/10">
                          <span className="font-bold text-[var(--onboarding-text-muted)] uppercase tracking-tight mr-2">Missing intake:</span>
                          {controlPlaneReadiness.missing_regions.join(', ') || 'none'}
                        </div>
                      )}

                      {isCheckingControlPlane && (
                        <div className="onboarding-inset rounded-[18px] border border-[var(--onboarding-text-soft)]/10 p-4" role="status" aria-live="polite">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="onboarding-display text-[11px] font-bold uppercase tracking-[0.2em] text-[var(--onboarding-text-muted)]">
                                Estimated progress
                              </p>
                              <p className="mt-1 text-[13px] font-semibold text-[var(--onboarding-text-strong)]">
                                {controlPlaneVerifyHeadline(controlPlaneVerifyPhase, controlPlaneRegion)}
                              </p>
                              <p className="mt-1 text-[12px] leading-5 text-[var(--onboarding-text-body)]">
                                {controlPlaneVerifyDetail(controlPlaneVerifyPhase)}
                              </p>
                            </div>
                            <span className="rounded-full bg-[#0B71FF]/10 px-2.5 py-1 text-[12px] font-bold text-[#0B71FF]">
                              {controlPlaneVerifyProgress}%
                            </span>
                          </div>
                          <div
                            className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--onboarding-text-soft)]/10"
                            role="progressbar"
                            aria-label="Verify intake progress"
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-valuenow={controlPlaneVerifyProgress}
                            aria-valuetext={`${controlPlaneVerifyProgress}%`}
                          >
                            <div
                              className="h-full rounded-full bg-[#0B71FF] transition-all duration-700 ease-out"
                              style={{ width: `${controlPlaneVerifyProgress}%` }}
                            />
                          </div>
                        </div>
                      )}

                    </div>
                  )}

                  {draft.step === 'final-checks' && (
                    <div className="space-y-4">
                      <div className="grid gap-3 lg:grid-cols-2">
                        <div className="onboarding-panel rounded-[22px] p-4 flex flex-col justify-center">
                          <p className="onboarding-display text-[13px] font-bold tracking-wider text-[var(--onboarding-text-muted)] uppercase">Required final checks</p>
                          <ul className="mt-2 list-disc space-y-1 pl-4 text-[12px] leading-snug text-[var(--onboarding-text-body)]">
                            <li>Inspector enabled.</li>
                            <li>Security Hub &amp; Config enabled.</li>
                            <li>Control-plane intake verified.</li>
                          </ul>
                        </div>

                        <div className="onboarding-inset rounded-[22px] p-4 flex flex-col justify-center">
                          <p className="onboarding-display text-[13px] font-bold tracking-wider text-[var(--onboarding-text-muted)] uppercase">First-value fast path</p>
                          {draft.fastPathTriggered ? (
                            <p className="mt-2 text-[12px] text-[#8CF6B7]">Queued at {draft.firstIngestQueuedAt ? new Date(draft.firstIngestQueuedAt).toLocaleTimeString() : 'earlier step'}.</p>
                          ) : isStartingFastPath ? (
                            <p className="mt-2 text-[12px] text-[var(--onboarding-text-muted)]">Evaluating eligibility...</p>
                          ) : (
                            <p className="mt-2 text-[11px] text-[var(--onboarding-text-body)]">Deferred until Security Hub &amp; Config ready.</p>
                          )}
                          {fastPathResult && (
                            <div className="mt-2 grid grid-cols-2 gap-x-2 text-[10px] text-[var(--onboarding-text-muted)]">
                              <p className="truncate line-clamp-1">SH: {fastPathResult.missing_security_hub_regions.length || '0'} missing</p>
                              <p className="truncate line-clamp-1">Cfg: {fastPathResult.missing_aws_config_regions.length || '0'} missing</p>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="onboarding-panel rounded-[20px] p-3 text-[11px] text-[var(--onboarding-text-muted)] italic text-center">
                        Check freshness: required checks older than 15m are revalidated.
                      </div>

                    </div>
                  )}

                  {draft.step === 'processing' && (
                    <div className="flex min-h-[340px] flex-col items-center justify-center gap-6 py-4 text-center">
                      <div className="onboarding-processing-shell relative flex h-24 w-24 items-center justify-center rounded-full">
                        <div className="onboarding-processing-ring absolute inset-0 rounded-full border-4 border-[var(--onboarding-processing-ring)] border-t-[#0B71FF]" />
                        <div className="onboarding-processing-core relative z-10 flex h-14 w-14 items-center justify-center rounded-full">
                          <div className="onboarding-pulse h-5 w-5 rounded-full bg-[#0B71FF]" />
                        </div>
                      </div>

                      <div className="max-w-xl space-y-3">
                        <h2 className="onboarding-display text-2xl font-bold tracking-[-0.04em] text-[var(--onboarding-text-strong)]">Processing...</h2>
                        <div className="onboarding-inset rounded-[22px] px-5 py-4">
                          <p className="text-sm leading-normal text-[var(--onboarding-text-body)]">
                            We&apos;re queuing ingestion and action computation. Your findings will be ready shortly.
                          </p>
                        </div>
                        <p className="text-[11px] leading-relaxed text-[var(--onboarding-text-muted)] opacity-60">
                          Progress preserved for 30 days. You can safely close or reload.
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                {draft.step !== 'welcome' && draft.step !== 'integration-role' && draft.step !== 'processing' ? (
                  <div className="mt-8 border-t border-[var(--onboarding-divider)] pt-5">
                    <p className="text-xs leading-6 text-[var(--onboarding-text-muted)]">
                      Need a break? Your progress and inputs are saved automatically.{' '}
                      <Link href="/login" className="text-[#6AA7FF] transition-colors hover:text-[var(--onboarding-text-strong)] hover:underline">
                        You can safely come back later.
                      </Link>
                    </p>
                  </div>
                ) : null}
                </div>

                {/* Shared Action Footer - Fixed at bottom of card */}
                {draft.step !== 'processing' && (
                  <div className={STICKY_ACTIONS_CLASS}>
                    {draft.step === 'welcome' && (
                      <div className="flex items-center justify-end gap-3">
                        <ActionButton onClick={nextStep}>Start onboarding</ActionButton>
                      </div>
                    )}
                    {draft.step === 'integration-role' && (
                      <div className="flex items-center justify-between gap-3">
                        <ActionButton tone="secondary" onClick={prevStep} disabled={!canGoBack || isSubmitting} className="!min-h-10 !h-10 !px-6">
                          Back
                        </ActionButton>
                        <ActionButton onClick={handleValidateIntegrationRole} disabled={!canValidateIntegrationRole} loading={isSubmitting} className="!min-h-10 !h-10 !px-8">
                          Validate role
                        </ActionButton>
                      </div>
                    )}
                    {draft.step === 'inspector' && (
                      <div className="flex items-center justify-between gap-3">
                        <ActionButton tone="secondary" onClick={prevStep} className="!min-h-10 !h-10 !px-6">Back</ActionButton>
                        <ActionButton onClick={handleVerifyInspector} loading={isCheckingInspector} className="!min-h-10 !h-10 !px-8">Verify Inspector</ActionButton>
                      </div>
                    )}
                    {draft.step === 'security-hub-config' && (
                      <div className="flex items-center justify-between gap-3">
                        <ActionButton tone="secondary" onClick={prevStep} className="!min-h-10 !h-10 !px-6">Back</ActionButton>
                        <ActionButton onClick={handleVerifySecurityHubAndConfig} loading={isCheckingSecurityHub} className="!min-h-10 !h-10 !px-8">
                          Verify Security Hub + Config
                        </ActionButton>
                      </div>
                    )}
                    {draft.step === 'control-plane' && (
                      <div className="flex items-center justify-between gap-3">
                        <ActionButton tone="secondary" onClick={prevStep} className="!min-h-10 !h-10 !px-6">Back</ActionButton>
                        <ActionButton onClick={handleVerifyControlPlane} disabled={isCheckingControlPlane} className="!min-h-10 !h-10 !px-8">
                          {controlPlaneVerifyLabel}
                        </ActionButton>
                      </div>
                    )}
                    {draft.step === 'final-checks' && (
                      <div className="flex items-center justify-between gap-3">
                        <ActionButton tone="secondary" onClick={prevStep} className="!min-h-10 !h-10 !px-6">Back</ActionButton>
                        <ActionButton onClick={handleRunFinalChecks} loading={isRunningFinalChecks} className="!min-h-10 !h-10 !px-8">Run final checks</ActionButton>
                      </div>
                    )}
                  </div>
                )}
              </section>
            </main>
        </div>
      </div>

      <style jsx>{`
        .onboarding-shell {
          --onboarding-text-strong: #0f1f42;
          --onboarding-text-body: #314872;
          --onboarding-text-muted: #5b6f93;
          --onboarding-text-soft: #1d3b69;
          --onboarding-info-text: #1f4f9f;
          --onboarding-frame-bg: rgba(221, 231, 243, 0.46);
          --onboarding-frame-border: rgba(173, 192, 223, 0.34);
          --onboarding-frame-shadow: 0 28px 60px rgba(148, 163, 184, 0.2);
          --onboarding-sidebar-bg: rgba(255, 255, 255, 0.72);
          --onboarding-sidebar-border: rgba(173, 192, 223, 0.42);
          --onboarding-sidebar-shadow: 14px 0 30px rgba(148, 163, 184, 0.14);
          --onboarding-card-bg: rgba(255, 255, 255, 0.78);
          --onboarding-card-border: rgba(173, 192, 223, 0.58);
          --onboarding-card-shadow: 18px 18px 36px rgba(191, 205, 225, 0.72), -14px -14px 30px rgba(255, 255, 255, 0.92);
          --onboarding-inset-bg: rgba(237, 243, 251, 0.92);
          --onboarding-inset-shadow: inset 6px 6px 12px rgba(198, 211, 230, 0.78), inset -6px -6px 12px rgba(255, 255, 255, 0.96);
          --onboarding-panel-bg: rgba(255, 255, 255, 0.56);
          --onboarding-panel-muted-bg: rgba(241, 246, 253, 0.78);
          --onboarding-panel-border: transparent;
          --onboarding-divider: rgba(173, 192, 223, 0.5);
          --onboarding-field-bg: rgba(246, 250, 255, 0.95);
          --onboarding-field-border: rgba(173, 192, 223, 0.42);
          --onboarding-field-shadow: inset 6px 6px 12px rgba(206, 218, 235, 0.72), inset -6px -6px 12px rgba(255, 255, 255, 0.96);
          --onboarding-placeholder: #6d7fa1;
          --onboarding-sticky-bg: rgba(231, 239, 249, 0.9);
          --onboarding-chip-bg: rgba(248, 251, 255, 0.95);
          --onboarding-chip-border: rgba(173, 192, 223, 0.62);
          --onboarding-chip-text: #314872;
          --onboarding-chip-info-text: #1f4f9f;
          --onboarding-step-track: rgba(173, 192, 223, 0.72);
          --onboarding-step-node-bg: rgba(239, 245, 252, 0.96);
          --onboarding-step-node-shadow: 0 8px 18px rgba(148, 163, 184, 0.16);
          --onboarding-step-node-border: rgba(173, 192, 223, 0.78);
          --onboarding-step-dot: rgba(91, 111, 147, 0.56);
          --onboarding-step-dot-hover: rgba(31, 79, 159, 0.88);
          --onboarding-button-secondary-bg: rgba(239, 245, 252, 0.82);
          --onboarding-button-secondary-border: transparent;
          --onboarding-button-secondary-text: #1f4f9f;
          --onboarding-button-secondary-hover-text: #173d7d;
          --onboarding-button-ghost-text: #5b6f93;
          --onboarding-button-ghost-hover: #0f1f42;
          --onboarding-icon-shadow: 0 12px 28px rgba(59, 130, 246, 0.18);
          --onboarding-processing-ring: rgba(173, 192, 223, 0.72);
          background:
            radial-gradient(circle at top left, rgba(11, 113, 255, 0.14), transparent 32%),
            linear-gradient(180deg, #eef4fb 0%, #dde7f3 100%);
          color: var(--onboarding-text-strong);
          font-family: var(--font-ds-body);
        }

        :global(.dark) .onboarding-shell {
          --onboarding-text-strong: #f8fafc;
          --onboarding-text-body: #c5d3eb;
          --onboarding-text-muted: #8b9bb4;
          --onboarding-text-soft: #dce7f8;
          --onboarding-info-text: #d8e8ff;
          --onboarding-frame-bg: rgba(3, 18, 40, 0.92);
          --onboarding-frame-border: rgba(255, 255, 255, 0.04);
          --onboarding-frame-shadow: 0 24px 72px rgba(2, 8, 20, 0.38);
          --onboarding-sidebar-bg: #061224;
          --onboarding-sidebar-border: rgba(255, 255, 255, 0.05);
          --onboarding-sidebar-shadow: 8px 0 16px #030812;
          --onboarding-card-bg: rgba(6, 18, 36, 0.92);
          --onboarding-card-border: rgba(255, 255, 255, 0.06);
          --onboarding-card-shadow: 8px 8px 16px #030812, -8px -8px 16px #0b1e38;
          --onboarding-inset-bg: rgba(7, 21, 40, 0.82);
          --onboarding-inset-shadow: inset 6px 6px 12px #030812, inset -6px -6px 12px #0b1e38;
          --onboarding-panel-bg: rgba(255, 255, 255, 0.025);
          --onboarding-panel-muted-bg: rgba(255, 255, 255, 0.03);
          --onboarding-panel-border: transparent;
          --onboarding-divider: rgba(255, 255, 255, 0.06);
          --onboarding-field-bg: rgba(7, 21, 40, 0.88);
          --onboarding-field-border: transparent;
          --onboarding-field-shadow: inset 6px 6px 12px #030812, inset -6px -6px 12px #0b1e38;
          --onboarding-placeholder: #8b9bb4;
          --onboarding-sticky-bg: rgba(6, 18, 36, 0.92);
          --onboarding-chip-bg: rgba(255, 255, 255, 0.04);
          --onboarding-chip-border: rgba(255, 255, 255, 0.08);
          --onboarding-chip-text: #dce7f8;
          --onboarding-chip-info-text: #d8e8ff;
          --onboarding-step-track: rgba(255, 255, 255, 0.08);
          --onboarding-step-node-bg: #061224;
          --onboarding-step-node-shadow: 8px 8px 16px #030812, -8px -8px 16px #0b1e38;
          --onboarding-step-node-border: rgba(255, 255, 255, 0.06);
          --onboarding-step-dot: rgba(255, 255, 255, 0.3);
          --onboarding-step-dot-hover: rgba(255, 255, 255, 0.55);
          --onboarding-button-secondary-bg: rgba(255, 255, 255, 0.04);
          --onboarding-button-secondary-border: transparent;
          --onboarding-button-secondary-text: #d9e7ff;
          --onboarding-button-secondary-hover-text: #ffffff;
          --onboarding-button-ghost-text: #8b9bb4;
          --onboarding-button-ghost-hover: #f8fafc;
          --onboarding-icon-shadow: 8px 8px 16px #030812, -8px -8px 16px #0b1e38, 0 0 18px rgba(11, 113, 255, 0.14);
          --onboarding-processing-ring: #0b1e38;
          background:
            radial-gradient(circle at top left, rgba(11, 113, 255, 0.12), transparent 32%),
            linear-gradient(180deg, #071120 0%, #061224 100%);
        }

        .onboarding-display {
          font-family: var(--font-ds-head);
        }

        @media (min-width: 1024px) {
          .onboarding-frame {
            background: var(--onboarding-frame-bg);
            border: 1px solid var(--onboarding-frame-border);
            box-shadow: var(--onboarding-frame-shadow);
            backdrop-filter: blur(18px);
          }
        }

        .onboarding-sidebar {
          background: var(--onboarding-sidebar-bg);
          border-right: 1px solid var(--onboarding-sidebar-border);
          box-shadow: var(--onboarding-sidebar-shadow);
        }

        .onboarding-sidebar-logo {
          background: linear-gradient(135deg, #0b71ff, #0f2e9b);
          box-shadow: 0 0 16px rgba(11, 113, 255, 0.4);
        }

        .onboarding-card {
          background: var(--onboarding-card-bg);
          border: 1px solid var(--onboarding-card-border);
          box-shadow: var(--onboarding-card-shadow);
          backdrop-filter: blur(20px);
        }

        .onboarding-panel,
        .onboarding-panel-muted {
          border: 1px solid var(--onboarding-panel-border);
          transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .onboarding-panel {
          background: var(--onboarding-panel-bg);
        }

        .onboarding-panel-muted {
          background: var(--onboarding-panel-muted-bg);
        }

        .onboarding-inset {
          background: var(--onboarding-inset-bg);
          box-shadow: var(--onboarding-inset-shadow);
        }

        .onboarding-chip {
          border: 1px solid var(--onboarding-chip-border);
          background: var(--onboarding-chip-bg);
          color: var(--onboarding-chip-text);
        }

        .onboarding-chip-info {
          border-color: rgba(11, 113, 255, 0.25);
          background: rgba(11, 113, 255, 0.1);
          color: var(--onboarding-chip-info-text);
        }

        .onboarding-step-track {
          background: var(--onboarding-step-track);
        }

        .onboarding-step-node {
          background: var(--onboarding-step-node-bg);
          border-color: var(--onboarding-step-node-border);
          box-shadow: var(--onboarding-step-node-shadow);
        }

        .onboarding-step-node-active {
          border-color: rgba(11, 113, 255, 0.35);
          box-shadow: 0 0 18px rgba(11, 113, 255, 0.22), var(--onboarding-step-node-shadow);
        }

        .onboarding-status-default {
          border-color: var(--onboarding-chip-border);
          background: var(--onboarding-panel-muted-bg);
          color: var(--onboarding-text-muted);
        }

        .onboarding-button-secondary {
          background: var(--onboarding-button-secondary-bg);
          border-color: var(--onboarding-button-secondary-border);
          color: var(--onboarding-button-secondary-text);
        }

        .onboarding-button-secondary:hover {
          border-color: rgba(11, 113, 255, 0.6);
          color: var(--onboarding-button-secondary-hover-text);
        }

        .onboarding-button-ghost {
          color: var(--onboarding-button-ghost-text);
        }

        .onboarding-button-ghost:hover {
          color: var(--onboarding-button-ghost-hover);
        }

        .onboarding-footer {
          border-top: 1px solid var(--onboarding-divider);
          background: var(--onboarding-sticky-bg);
        }

        .onboarding-field {
          border: 1px solid var(--onboarding-field-border);
          background: var(--onboarding-field-bg);
          box-shadow: var(--onboarding-field-shadow);
          color: var(--onboarding-text-strong);
          transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
        }

        .onboarding-field:focus {
          outline: none;
          border-color: rgba(11, 113, 255, 0.65);
          box-shadow:
            var(--onboarding-field-shadow),
            0 0 0 1px rgba(11, 113, 255, 0.4),
            0 0 18px rgba(11, 113, 255, 0.16);
        }

        .onboarding-input::placeholder {
          color: var(--onboarding-placeholder);
        }

        .onboarding-select-trigger {
          border: 1px solid var(--onboarding-field-border) !important;
          background: var(--onboarding-field-bg) !important;
          color: var(--onboarding-text-strong) !important;
          box-shadow: var(--onboarding-field-shadow);
        }

        .onboarding-check {
          border: 1px solid var(--onboarding-field-border);
          background: var(--onboarding-field-bg);
          box-shadow: var(--onboarding-field-shadow);
        }

        .onboarding-welcome-card {
          animation: onboarding-welcome-rise 520ms ease both;
        }

        .onboarding-welcome-icon {
          background: var(--onboarding-chip-bg);
          box-shadow: var(--onboarding-icon-shadow);
        }

        .onboarding-content {
          animation: onboarding-slide-in 420ms ease both;
        }

        .onboarding-processing-ring {
          animation: onboarding-spin 1.5s linear infinite;
        }

        .onboarding-processing-shell {
          box-shadow: var(--onboarding-inset-shadow);
        }

        .onboarding-processing-core {
          box-shadow: var(--onboarding-card-shadow);
        }

        .onboarding-pulse {
          box-shadow: 0 0 22px rgba(11, 113, 255, 0.5);
          animation: onboarding-pulse 1.6s ease-in-out infinite;
        }

        .onboarding-spinner {
          animation: onboarding-spin 0.9s linear infinite;
        }

        .onboarding-scroll {
          scrollbar-width: thin;
          scrollbar-color: rgba(106, 167, 255, 0.22) transparent;
        }

        .onboarding-scroll :global(::-webkit-scrollbar) {
          width: 10px;
        }

        .onboarding-scroll :global(::-webkit-scrollbar-thumb) {
          background: rgba(106, 167, 255, 0.22);
          border-radius: 999px;
        }

        @keyframes onboarding-welcome-rise {
          from {
            opacity: 0;
            transform: translate3d(0, 22px, 0);
          }

          to {
            opacity: 1;
            transform: translate3d(0, 0, 0);
          }
        }

        @keyframes onboarding-slide-in {
          from {
            opacity: 0;
            transform: translate3d(30px, 0, 0);
          }

          to {
            opacity: 1;
            transform: translate3d(0, 0, 0);
          }
        }

        @keyframes onboarding-spin {
          from {
            transform: rotate(0deg);
          }

          to {
            transform: rotate(360deg);
          }
        }

        @keyframes onboarding-pulse {
          0%,
          100% {
            transform: scale(0.96);
            opacity: 0.72;
          }

          50% {
            transform: scale(1.06);
            opacity: 1;
          }
        }
      `}</style>
    </div >
  );
}
