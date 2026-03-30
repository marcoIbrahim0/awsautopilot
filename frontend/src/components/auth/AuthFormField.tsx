'use client';

import { InputHTMLAttributes, forwardRef } from 'react';

/**
 * Neumorphic form field: label + inset-shadow input.
 * Renders as a recessed text pool that sits flush with the Neumorphic surface.
 */

export interface AuthFormFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  id: string;
  error?: string;
  endAdornment?: React.ReactNode;
}

export const AuthFormField = forwardRef<HTMLInputElement, AuthFormFieldProps>(
  ({ label, id, error, className = '', endAdornment, ...props }, ref) => {
    return (
      <div className="space-y-2">
        <label
          htmlFor={id}
          className="block text-sm font-medium"
          style={{ color: 'var(--nm-text, var(--text))' }}
        >
          {label}
        </label>
        <div className="relative">
          <input
            ref={ref}
            id={id}
            className={`
              w-full rounded-xl border-0 bg-transparent px-4 py-3 placeholder:opacity-50
              transition-shadow duration-150
              focus:outline-none focus:ring-2 focus:ring-[var(--nm-accent,var(--accent))] focus:ring-offset-1
              disabled:cursor-not-allowed disabled:opacity-50
              ${endAdornment ? 'pr-12' : ''}
              ${error ? 'ring-2 ring-red-500' : ''}
              ${className}
            `}
            style={{
              color: 'var(--nm-text, var(--text))',
              boxShadow:
                'inset 3px 3px 8px var(--nm-shadow-dark, rgba(166,184,207,0.85)), inset -3px -3px 8px var(--nm-shadow-light, rgba(255,255,255,0.92))',
            }}
            {...props}
          />
          {endAdornment ? (
            <div className="absolute inset-y-0 right-0 flex items-center pr-3">
              {endAdornment}
            </div>
          ) : null}
        </div>
        {error && (
          <p className="text-sm text-red-600">{error}</p>
        )}
      </div>
    );
  }
);

AuthFormField.displayName = 'AuthFormField';
