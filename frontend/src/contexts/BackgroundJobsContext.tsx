'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

export type BackgroundJobType = 'findings' | 'actions' | 'onboarding' | 'account' | 'system';
export type BackgroundJobSeverity = 'info' | 'success' | 'warning' | 'error';
export type BackgroundJobStatus =
  | 'queued'
  | 'running'
  | 'partial'
  | 'success'
  | 'error'
  | 'timed_out'
  | 'canceled';

export interface BackgroundJob {
  id: string;
  type: BackgroundJobType;
  title: string;
  message: string;
  progress: number;
  status: BackgroundJobStatus;
  severity: BackgroundJobSeverity;
  dedupeKey?: string | null;
  resourceId?: string | null;
  actorId?: string | null;
  detail?: string | null;
  bannerVisible: boolean;
  bannerAutoDismissAt?: number | null;
  createdAt: number;
  updatedAt: number;
}

interface BackgroundJobsContextValue {
  jobs: BackgroundJob[];
  activeCount: number;
  addJob: (input: {
    type: BackgroundJobType;
    title: string;
    message: string;
    progress?: number;
    status?: 'queued' | 'running' | 'partial';
    severity?: BackgroundJobSeverity;
    dedupeKey?: string | null;
    resourceId?: string | null;
    actorId?: string | null;
  }) => string;
  updateJob: (
    jobId: string,
    patch: Partial<Pick<BackgroundJob, 'message' | 'progress' | 'detail' | 'status' | 'severity'>>
  ) => void;
  completeJob: (jobId: string, message?: string, detail?: string | null) => void;
  failJob: (jobId: string, message: string, detail?: string | null) => void;
  timeoutJob: (jobId: string, message: string, detail?: string | null) => void;
  cancelJob: (jobId: string, message?: string, detail?: string | null) => void;
  dismissBanner: (jobId: string) => void;
  dismissJob: (jobId: string) => void;
  clearFinishedJobs: () => void;
}

const STORAGE_KEY = 'background_jobs_v1';
const MAX_STORED_JOBS = 30;
const FINISHED_JOB_TTL_MS = 30 * 24 * 60 * 60 * 1000;
const BANNER_SUCCESS_AUTODISMISS_MS = 8_000;
const DEDUPE_WINDOW_MS = 10 * 60 * 1000;
const ACTIVE_JOB_STALE_MS_DEFAULT = 20 * 60 * 1000;
const ACTIVE_JOB_STALE_MS_BY_TYPE: Partial<Record<BackgroundJobType, number>> = {
  onboarding: 15 * 60 * 1000,
  account: 5 * 60 * 1000,
};

const BackgroundJobsContext = createContext<BackgroundJobsContextValue | null>(null);

function clampProgress(value: number | undefined): number {
  if (value == null) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function isTerminalStatus(status: BackgroundJobStatus): boolean {
  return status === 'success' || status === 'error' || status === 'timed_out' || status === 'canceled';
}

function defaultSeverityForStatus(status: BackgroundJobStatus): BackgroundJobSeverity {
  if (status === 'error' || status === 'timed_out') return 'error';
  if (status === 'canceled') return 'warning';
  if (status === 'success') return 'success';
  return 'info';
}

function isActiveStatus(status: BackgroundJobStatus): boolean {
  return status === 'queued' || status === 'running' || status === 'partial';
}

function staleJobDetailMessage(): string {
  return 'No status update was received for a long time. The task may have completed; refresh or retry if needed.';
}

function markStaleIfNeeded(job: BackgroundJob, now: number): BackgroundJob {
  if (!isActiveStatus(job.status)) return job;
  const maxAgeMs = ACTIVE_JOB_STALE_MS_BY_TYPE[job.type] ?? ACTIVE_JOB_STALE_MS_DEFAULT;
  if (now - job.updatedAt <= maxAgeMs) return job;
  return {
    ...job,
    status: 'timed_out',
    severity: 'error',
    progress: Math.max(job.progress, 100),
    detail: job.detail ?? staleJobDetailMessage(),
    bannerVisible: true,
    bannerAutoDismissAt: null,
    updatedAt: now,
  };
}

function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function loadInitialJobs(): BackgroundJob[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Array<Partial<BackgroundJob> & { id: string }>;
    const now = Date.now();
    return parsed
      .map((job) => {
        const rawStatus = String(job.status ?? '');
        const status = rawStatus === 'done' ? 'success' : rawStatus || 'running';
        const normalizedStatus = status as BackgroundJobStatus;
        return markStaleIfNeeded({
          id: job.id,
          type: (job.type as BackgroundJobType) ?? 'system',
          title: job.title ?? 'Background task',
          message: job.message ?? '',
          progress: clampProgress(job.progress ?? 0),
          status: normalizedStatus,
          severity: (job.severity as BackgroundJobSeverity) ?? defaultSeverityForStatus(normalizedStatus),
          dedupeKey: job.dedupeKey ?? null,
          resourceId: job.resourceId ?? null,
          actorId: job.actorId ?? null,
          detail: job.detail ?? null,
          bannerVisible: job.bannerVisible ?? !isTerminalStatus(normalizedStatus),
          bannerAutoDismissAt: job.bannerAutoDismissAt ?? null,
          createdAt: job.createdAt ?? now,
          updatedAt: job.updatedAt ?? now,
        } as BackgroundJob, now);
      })
      .filter((job) => {
        if (!isTerminalStatus(job.status)) return true;
        return now - job.updatedAt <= FINISHED_JOB_TTL_MS;
      });
  } catch {
    return [];
  }
}

export function BackgroundJobsProvider({ children }: { children: React.ReactNode }) {
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [storageHydrated, setStorageHydrated] = useState(false);
  const jobsRef = useRef<BackgroundJob[]>(jobs);

  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

  // Hydrate localStorage after mount to avoid SSR/client hydration mismatch.
  useEffect(() => {
    const stored = loadInitialJobs();
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setJobs((prev) => {
        if (prev.length === 0) return stored;
        const byId = new Map<string, BackgroundJob>();
        for (const job of stored) byId.set(job.id, job);
        for (const job of prev) byId.set(job.id, job);
        return Array.from(byId.values())
          .sort((a, b) => b.updatedAt - a.updatedAt)
          .slice(0, MAX_STORED_JOBS);
      });
      setStorageHydrated(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!storageHydrated) return;
    const now = Date.now();
    const pruned = jobs
      .filter((job) => (!isTerminalStatus(job.status) ? true : now - job.updatedAt <= FINISHED_JOB_TTL_MS))
      .slice(0, MAX_STORED_JOBS);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pruned));
  }, [jobs, storageHydrated]);

  // Auto-hide success banners, but keep notification records in center.
  useEffect(() => {
    const now = Date.now();
    const nextAutoDismissAt = jobs
      .filter((job) => job.bannerVisible && job.bannerAutoDismissAt && job.bannerAutoDismissAt > now)
      .map((job) => job.bannerAutoDismissAt as number)
      .sort((a, b) => a - b)[0];

    const hasDueNow = jobs.some(
      (job) => job.bannerVisible && !!job.bannerAutoDismissAt && job.bannerAutoDismissAt <= now
    );

    if (!nextAutoDismissAt && !hasDueNow) return;

    const timer = window.setTimeout(() => {
      const runAt = Date.now();
      setJobs((prev) =>
        prev.map((job) =>
          job.bannerVisible && !!job.bannerAutoDismissAt && job.bannerAutoDismissAt <= runAt
            ? {
                ...job,
                bannerVisible: false,
                bannerAutoDismissAt: null,
                updatedAt: runAt,
              }
            : job
        )
      );
    }, hasDueNow ? 0 : Math.max(100, (nextAutoDismissAt as number) - now));
    return () => window.clearTimeout(timer);
  }, [jobs]);

  // Convert orphaned active jobs into timed_out so loading UI cannot remain stuck forever.
  useEffect(() => {
    const timer = window.setInterval(() => {
      const now = Date.now();
      setJobs((prev) => {
        let changed = false;
        const next = prev.map((job) => {
          const updated = markStaleIfNeeded(job, now);
          if (updated !== job) changed = true;
          return updated;
        });
        return changed ? next : prev;
      });
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const addJob = useCallback(
    (input: {
      type: BackgroundJobType;
      title: string;
      message: string;
      progress?: number;
      status?: 'queued' | 'running' | 'partial';
      severity?: BackgroundJobSeverity;
      dedupeKey?: string | null;
      resourceId?: string | null;
      actorId?: string | null;
    }) => {
      const status: BackgroundJobStatus = input.status ?? 'running';
      const dedupeKey =
        input.dedupeKey ??
        (input.resourceId && input.actorId ? `${input.type}:${input.resourceId}:${input.actorId}` : null);
      const now = Date.now();
      const existing =
        dedupeKey
          ? jobsRef.current.find(
              (job) =>
                job.dedupeKey === dedupeKey &&
                now - job.updatedAt <= DEDUPE_WINDOW_MS &&
                !isTerminalStatus(job.status)
            )
          : undefined;
      const jobId = existing?.id ?? uid();

      setJobs((prev) => {
        const base = dedupeKey ? prev.filter((job) => job.dedupeKey !== dedupeKey || job.id === existing?.id) : prev;

        if (existing) {
          return base.map((job) =>
            job.id === existing.id
              ? {
                  ...job,
                  title: input.title,
                  message: input.message,
                  status,
                  severity: input.severity ?? defaultSeverityForStatus(status),
                  progress: clampProgress(input.progress ?? job.progress),
                  detail: null,
                  bannerVisible: true,
                  bannerAutoDismissAt: null,
                  updatedAt: now,
                }
              : job
          );
        }

        const job: BackgroundJob = {
          id: jobId,
          type: input.type,
          title: input.title,
          message: input.message,
          progress: clampProgress(input.progress ?? 0),
          status,
          severity: input.severity ?? defaultSeverityForStatus(status),
          dedupeKey,
          resourceId: input.resourceId ?? null,
          actorId: input.actorId ?? null,
          detail: null,
          bannerVisible: true,
          bannerAutoDismissAt: null,
          createdAt: now,
          updatedAt: now,
        };
        return [job, ...base].slice(0, MAX_STORED_JOBS);
      });

      return jobId;
    },
    []
  );

  const updateJob = useCallback(
    (
      jobId: string,
      patch: Partial<Pick<BackgroundJob, 'message' | 'progress' | 'detail' | 'status' | 'severity'>>
    ) => {
      setJobs((prev) =>
        prev.map((job) =>
          job.id === jobId
            ? {
                ...job,
                ...patch,
                progress: clampProgress(patch.progress ?? job.progress),
                severity: patch.severity ?? (patch.status ? defaultSeverityForStatus(patch.status) : job.severity),
                bannerVisible: true,
                bannerAutoDismissAt:
                  patch.status && patch.status === 'success'
                    ? Date.now() + BANNER_SUCCESS_AUTODISMISS_MS
                    : patch.status && (patch.status === 'error' || patch.status === 'timed_out')
                      ? null
                      : job.bannerAutoDismissAt,
                updatedAt: Date.now(),
              }
            : job
        )
      );
    },
    []
  );

  const completeJob = useCallback((jobId: string, message?: string, detail?: string | null) => {
    setJobs((prev) =>
      prev.map((job) =>
        job.id === jobId
          ? {
              ...job,
              status: 'success',
              severity: 'success',
              progress: 100,
              message: message ?? job.message,
              detail: detail ?? job.detail,
              bannerVisible: true,
              bannerAutoDismissAt: Date.now() + BANNER_SUCCESS_AUTODISMISS_MS,
              updatedAt: Date.now(),
            }
          : job
      )
    );
  }, []);

  const failJob = useCallback((jobId: string, message: string, detail?: string | null) => {
    setJobs((prev) =>
      prev.map((job) =>
        job.id === jobId
          ? {
              ...job,
              status: 'error',
              severity: 'error',
              message,
              detail: detail ?? job.detail,
              progress: Math.max(job.progress, 100),
              bannerVisible: true,
              bannerAutoDismissAt: null,
              updatedAt: Date.now(),
            }
          : job
      )
    );
  }, []);

  const timeoutJob = useCallback((jobId: string, message: string, detail?: string | null) => {
    setJobs((prev) =>
      prev.map((job) =>
        job.id === jobId
          ? {
              ...job,
              status: 'timed_out',
              severity: 'error',
              message,
              detail: detail ?? job.detail,
              progress: Math.max(job.progress, 100),
              bannerVisible: true,
              bannerAutoDismissAt: null,
              updatedAt: Date.now(),
            }
          : job
      )
    );
  }, []);

  const cancelJob = useCallback((jobId: string, message?: string, detail?: string | null) => {
    setJobs((prev) =>
      prev.map((job) =>
        job.id === jobId
          ? {
              ...job,
              status: 'canceled',
              severity: 'warning',
              message: message ?? job.message,
              detail: detail ?? job.detail,
              bannerVisible: true,
              bannerAutoDismissAt: null,
              updatedAt: Date.now(),
            }
          : job
      )
    );
  }, []);

  const dismissBanner = useCallback((jobId: string) => {
    setJobs((prev) =>
      prev.map((job) =>
        job.id === jobId
          ? {
              ...job,
              bannerVisible: false,
              bannerAutoDismissAt: null,
              updatedAt: Date.now(),
            }
          : job
      )
    );
  }, []);

  const dismissJob = useCallback((jobId: string) => {
    setJobs((prev) => prev.filter((job) => job.id !== jobId));
  }, []);

  const clearFinishedJobs = useCallback(() => {
    setJobs((prev) => prev.filter((job) => !isTerminalStatus(job.status)));
  }, []);

  const value = useMemo<BackgroundJobsContextValue>(
    () => ({
      jobs,
      activeCount: jobs.filter((job) => job.status === 'queued' || job.status === 'running' || job.status === 'partial')
        .length,
      addJob,
      updateJob,
      completeJob,
      failJob,
      timeoutJob,
      cancelJob,
      dismissBanner,
      dismissJob,
      clearFinishedJobs,
    }),
    [jobs, addJob, updateJob, completeJob, failJob, timeoutJob, cancelJob, dismissBanner, dismissJob, clearFinishedJobs]
  );

  return <BackgroundJobsContext.Provider value={value}>{children}</BackgroundJobsContext.Provider>;
}

export function useBackgroundJobs() {
  const ctx = useContext(BackgroundJobsContext);
  if (!ctx) throw new Error('useBackgroundJobs must be used within BackgroundJobsProvider');
  return ctx;
}
