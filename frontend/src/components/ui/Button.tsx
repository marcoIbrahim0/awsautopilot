'use client';

import { ButtonHTMLAttributes, forwardRef } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent' | 'icon';
export type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "relative overflow-hidden rounded-full border border-[var(--primary-btn-border)] bg-tab-active text-[var(--primary-btn-text)] shadow-[0_18px_38px_-20px_var(--primary-btn-shadow)] before:absolute before:inset-px before:rounded-full before:bg-[var(--primary-btn-inner-bg)] before:transition before:content-[''] hover:-translate-y-px hover:border-[var(--border-strong)] hover:shadow-[0_22px_44px_-20px_var(--primary-btn-shadow)] hover:before:bg-[var(--primary-btn-inner-hover-bg)] active:translate-y-0 active:border-[var(--border-strong)] active:before:bg-[var(--primary-btn-inner-active-bg)]",
  secondary:
    'rounded-full border border-[var(--secondary-btn-border)] bg-[var(--secondary-btn-bg)] text-[var(--secondary-btn-text)] shadow-[0_10px_24px_-20px_rgba(10,33,90,0.55)] hover:-translate-y-px hover:border-[var(--border-strong)] hover:bg-[var(--secondary-btn-hover-bg)] hover:text-[var(--secondary-btn-hover-text)]',
  ghost:
    'rounded-full border border-transparent bg-transparent text-muted hover:border-[var(--border-strong)] hover:bg-[var(--control-hover)] hover:text-text',
  danger:
    'rounded-full border border-danger/34 bg-danger/12 text-danger shadow-[0_10px_24px_-20px_rgba(184,48,72,0.8)] hover:-translate-y-px hover:border-danger/46 hover:bg-danger/18',
  accent:
    'rounded-full border border-accent/30 bg-accent/12 text-accent shadow-[0_10px_24px_-20px_rgba(10,113,255,0.85)] hover:-translate-y-px hover:border-accent/42 hover:bg-accent/18',
  icon:
    'rounded-2xl border border-[var(--secondary-btn-border)] bg-[var(--secondary-btn-bg)] text-[var(--secondary-btn-text)] shadow-[0_10px_24px_-20px_rgba(10,33,90,0.55)] hover:-translate-y-px hover:border-[var(--border-strong)] hover:bg-[var(--secondary-btn-hover-bg)] hover:text-[var(--secondary-btn-hover-text)]',
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'min-h-9 px-3.5 py-2 text-sm gap-1.5',
  md: 'min-h-10 px-4.5 py-2.5 text-sm gap-2',
  lg: 'min-h-11 px-5 py-3 text-base gap-2',
};

const baseButtonClassName = `
  inline-flex items-center justify-center font-semibold whitespace-nowrap
  transition-all duration-150 ease-out
  focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-dropdown-bg
  disabled:opacity-45 disabled:cursor-not-allowed disabled:translate-y-0 disabled:shadow-none
`;

export function buttonClassName({
  variant = 'primary',
  size = 'md',
  className = '',
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
}): string {
  return `${baseButtonClassName} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      children,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={buttonClassName({ variant, size, className })}
        {...props}
      >
        {isLoading ? (
          <svg
            className="relative z-10 animate-spin w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
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
        ) : leftIcon ? (
          <span className="relative z-10 inline-flex items-center shrink-0">{leftIcon}</span>
        ) : null}
        <span className="relative z-10 inline-flex items-center gap-2 whitespace-nowrap [&>svg]:inline-block [&>svg]:shrink-0">
          {children}
        </span>
        {rightIcon && !isLoading && (
          <span className="relative z-10 inline-flex items-center shrink-0">{rightIcon}</span>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';
