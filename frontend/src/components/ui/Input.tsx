'use client';

import { InputHTMLAttributes, forwardRef } from 'react';
import { ExplainerHint } from '@/components/ui/ExplainerHint';
import type { ExplainerConceptId, ExplainerContext } from '@/components/operatorExplainers';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  labelExplainer?: { conceptId: ExplainerConceptId; context?: ExplainerContext };
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, labelExplainer, className = '', id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="space-y-1.5">
        {label && (
          <div className="flex flex-wrap items-center gap-2">
            <label
              htmlFor={inputId}
              className="block text-sm font-medium text-text"
            >
              {label}
            </label>
            {labelExplainer ? <ExplainerHint content={labelExplainer} label={label} iconOnly /> : null}
          </div>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`
            w-full rounded-2xl border px-4 py-3
            bg-[var(--control-bg)]
            text-text placeholder:text-muted
            shadow-[inset_0_1px_0_rgba(255,255,255,0.22)]
            transition-all duration-150
            focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent focus:bg-[var(--control-hover)]
            disabled:opacity-50 disabled:cursor-not-allowed
            ${error ? 'border-danger' : 'border-border'}
            ${className}
          `}
          {...props}
        />
        {error && (
          <p className="text-sm text-danger">{error}</p>
        )}
        {helperText && !error && (
          <p className="text-sm text-muted">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
