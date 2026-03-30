'use client';

import { ButtonHTMLAttributes, forwardRef } from 'react';
import { NoiseBackground } from './NoiseBackground';

/**
 * Major action button using Aceternity-style noise background (gradient + noise).
 * Use for primary CTAs: Approve & run, Generate PR bundle, key onboarding steps, etc.
 * @see https://ui.aceternity.com/components/noise-background
 */
interface MajorActionButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  isLoading?: boolean;
  children: React.ReactNode;
  className?: string;
}

const GRADIENT_COLORS = [
  'rgb(62, 140, 255)',
  'rgb(42, 114, 235)',
  'rgb(35, 98, 210)',
];

export const MajorActionButton = forwardRef<HTMLButtonElement, MajorActionButtonProps>(
  ({ isLoading = false, children, className = '', disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={`
          relative inline-flex items-center justify-center
          px-5 py-2.5 text-base font-semibold text-[var(--primary-btn-text)]
          !rounded-full overflow-hidden border border-[var(--primary-btn-border)]
          bg-[linear-gradient(135deg,var(--primary-btn-gradient-start),var(--primary-btn-gradient-mid),var(--primary-btn-gradient-end))]
          shadow-[0_10px_28px_var(--primary-btn-shadow)]
          focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-dropdown-bg
          disabled:opacity-50 disabled:cursor-not-allowed
          before:absolute before:inset-[2px] before:rounded-full before:bg-[var(--primary-btn-inner-bg)] before:content-['']
          hover:before:bg-[var(--primary-btn-inner-hover-bg)] active:before:bg-[var(--primary-btn-inner-active-bg)]
          transition-all duration-150
          ${className}
        `}
        {...props}
      >
        <NoiseBackground
          containerClassName="absolute inset-0 rounded-full pointer-events-none"
          className="absolute inset-0"
          gradientColors={GRADIENT_COLORS}
          noiseIntensity={0.08}
          animating={!isLoading}
        />
        <span className="relative z-10 flex items-center gap-2">
          {isLoading ? (
            <>
              <svg
                className="animate-spin w-4 h-4"
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
              <span>{children}</span>
            </>
          ) : (
            children
          )}
        </span>
      </button>
    );
  }
);

MajorActionButton.displayName = 'MajorActionButton';
