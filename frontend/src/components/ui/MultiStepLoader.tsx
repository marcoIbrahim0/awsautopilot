'use client';

import { motion } from 'motion/react';

/**
 * Aceternity-style multi-step loader for run progress (e.g. Generate PR).
 * @see https://ui.aceternity.com/components/multi-step-loader
 */
export interface MultiStepLoaderStep {
  key: string;
  label: string;
  done: boolean;
  /** Current active step (loading) */
  active?: boolean;
  /** Failed state for this step */
  failed?: boolean;
}

interface MultiStepLoaderProps {
  steps: MultiStepLoaderStep[];
  className?: string;
}

export function MultiStepLoader({ steps, className = '' }: MultiStepLoaderProps) {
  return (
    <div className={`flex items-center justify-between gap-2 ${className}`}>
      {steps.map((step, idx) => (
        <div key={step.key} className="flex items-center flex-1 min-w-0">
          <div className="flex flex-col items-center shrink-0">
            <motion.div
              initial={false}
              animate={{
                backgroundColor: step.failed
                  ? 'var(--color-danger)'
                  : step.done
                    ? 'var(--color-accent)'
                    : 'var(--color-border)',
                scale: step.active ? 1.1 : 1,
              }}
              transition={{ duration: 0.3 }}
              className="w-10 h-10 rounded-full flex items-center justify-center border-2 border-border"
            >
              {step.done ? (
                step.failed ? (
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )
              ) : step.active ? (
                <svg
                  className="animate-spin w-5 h-5 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              ) : (
                <span className="text-sm font-medium text-muted">{idx + 1}</span>
              )}
            </motion.div>
            <span className="text-xs text-muted mt-2 truncate max-w-[90px] text-center">{step.label}</span>
          </div>
          {idx < steps.length - 1 && (
            <div
              className={`flex-1 h-0.5 mx-2 min-w-[20px] transition-colors duration-300 ${
                step.done ? 'bg-accent' : 'bg-border'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}
