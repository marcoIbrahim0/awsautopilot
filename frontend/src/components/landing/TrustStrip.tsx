'use client';

import { MovingBorder } from './MovingBorder';
import { cn } from '@/lib/utils';

const TRUST_PILLS = [
  'Read-only first',
  'STS AssumeRole + ExternalId',
  'One-off report in 48h',
];

export function TrustStrip() {
  return (
    <section className="relative px-4 py-12 sm:px-6">
      <div className="mx-auto max-w-4xl">
        <MovingBorder
          containerClassName="rounded-xl"
          duration={4000}
          borderClassName="opacity-60"
        >
          <div className="flex flex-wrap items-center justify-center gap-6 px-6 py-5 sm:gap-8">
            <p className="text-muted text-center text-sm sm:text-base">
              No long-lived keys. Read-only access. Report in 48 hours.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              {TRUST_PILLS.map((label) => (
                <span
                  key={label}
                  className={cn(
                    'inline-flex items-center rounded-full border border-border bg-surface-alt px-4 py-1.5',
                    'text-muted text-xs font-medium'
                  )}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        </MovingBorder>
      </div>
    </section>
  );
}
