'use client';

import { cn } from '@/lib/utils';

interface Step {
  label: string;
  active?: boolean;
}

interface DynamicIslandPillProps {
  steps: Step[];
  className?: string;
}

export function DynamicIslandPill({ steps, className }: DynamicIslandPillProps) {
  return (
    <div
      className={cn(
        'inline-flex items-center gap-2 rounded-full border border-border bg-surface-alt px-4 py-2',
        className
      )}
    >
      {steps.map((step, i) => (
        <span key={i} className="inline-flex items-center gap-2">
          <span
            className={cn(
              'text-xs font-medium transition-colors',
              step.active ? 'text-accent' : 'text-muted'
            )}
          >
            {step.label}
          </span>
          {i < steps.length - 1 && <span className="text-border text-xs">→</span>}
        </span>
      ))}
    </div>
  );
}
