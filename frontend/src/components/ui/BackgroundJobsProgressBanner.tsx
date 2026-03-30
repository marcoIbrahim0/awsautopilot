'use client';

import { useMemo } from 'react';
import { useBackgroundJobs, BackgroundJobType } from '@/contexts/BackgroundJobsContext';

interface BackgroundJobsProgressBannerProps {
  types: BackgroundJobType[];
}

export function BackgroundJobsProgressBanner({ types }: BackgroundJobsProgressBannerProps) {
  const { jobs } = useBackgroundJobs();

  const runningJobs = useMemo(
    () =>
      jobs.filter(
        (job) =>
          (job.status === 'queued' || job.status === 'running' || job.status === 'partial') &&
          types.includes(job.type)
      ),
    [jobs, types]
  );

  if (runningJobs.length === 0) return null;

  return (
    <div className="mb-4 space-y-2 rounded-2xl border border-border bg-surface/70 p-4">
      <p className="text-sm font-medium text-text">
        {runningJobs.length === 1 ? 'Background task in progress' : `${runningJobs.length} background tasks in progress`}
      </p>
      {runningJobs.map((job) => (
        <div key={job.id} className="rounded-xl border border-border/60 bg-bg/50 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-sm text-text">{job.title}</p>
            <span className="text-xs text-muted">{job.progress}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg">
            <div
              className="h-full rounded-full bg-accent transition-all duration-300"
              style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-muted">{job.message}</p>
        </div>
      ))}
    </div>
  );
}
