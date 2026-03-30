'use client';

import { useMemo } from 'react';
import { useBackgroundJobs } from '@/contexts/BackgroundJobsContext';
import { Button } from '@/components/ui/Button';

function statusText(status: string): string {
  if (status === 'queued') return 'Queued';
  if (status === 'running') return 'Running';
  if (status === 'partial') return 'Partial';
  if (status === 'success') return 'Success';
  if (status === 'timed_out') return 'Timed out';
  if (status === 'canceled') return 'Canceled';
  return 'Failed';
}

function bannerClasses(status: string): string {
  if (status === 'success') return 'text-success';
  if (status === 'error' || status === 'timed_out') return 'text-danger';
  if (status === 'partial' || status === 'canceled') return 'text-warning';
  return 'text-accent';
}

export function GlobalAsyncBannerRail() {
  const { jobs, dismissBanner } = useBackgroundJobs();

  const visible = useMemo(
    () =>
      [...jobs]
        .filter((job) => job.bannerVisible)
        .sort((a, b) => b.updatedAt - a.updatedAt)
        .slice(0, 3),
    [jobs]
  );

  if (visible.length === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] flex flex-col items-center gap-3 pointer-events-none w-full px-4">
      {visible.map((job) => (
        <div
          key={job.id}
          className={`pointer-events-auto w-auto max-w-lg rounded-2xl px-5 py-3 nm-neu-sm bg-surface transition-all duration-300 ${bannerClasses(job.status)}`}
          role="status"
          aria-live="polite"
        >
          <div className="flex items-center justify-between gap-6">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold mb-0.5">
                {job.title} · {statusText(job.status)}
              </p>
              <p className="text-sm text-text/90 leading-tight">{job.message}</p>
              {job.detail && <p className="text-xs text-text/70 mt-1">{job.detail}</p>}
              <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-border/40 nm-inset-sm">
                <div
                  className="h-full rounded-full bg-current transition-all duration-300 shadow-[0_0_8px_currentColor]"
                  style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }}
                />
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => dismissBanner(job.id)}
              className="h-8 w-8 p-0 rounded-full shrink-0 flex items-center justify-center text-muted hover:text-text hover:bg-border/30 nm-neu-flat transition-colors"
              aria-label="Dismiss banner"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
