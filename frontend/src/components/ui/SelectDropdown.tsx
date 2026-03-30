'use client';

import * as React from 'react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuItemIndicator,
} from '@/components/ui/DropdownMenu';
import { cn } from '@/lib/utils';

/**
 * Single-select dropdown using shadcn-style DropdownMenu (Radix).
 * Use across the site instead of native <select> for consistent UI.
 */
export interface SelectDropdownOption<T extends string = string> {
  value: T;
  label: string;
  disabled?: boolean;
}

interface SelectDropdownProps<T extends string = string> {
  value: T;
  onValueChange: (value: T) => void;
  options: SelectDropdownOption<T>[];
  placeholder?: string;
  disabled?: boolean;
  triggerClassName?: string;
  contentClassName?: string;
  /** Accessible label for the trigger */
  'aria-label'?: string;
}

export function SelectDropdown<T extends string = string>({
  value,
  onValueChange,
  options,
  placeholder = 'Select…',
  disabled = false,
  triggerClassName,
  contentClassName,
  'aria-label': ariaLabel,
}: SelectDropdownProps<T>) {
  const selectedOption = options.find((o) => o.value === value);
  const displayLabel = selectedOption?.label ?? placeholder;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-label={ariaLabel}
          className={cn(
            'inline-flex h-10 items-center justify-center px-3 py-0 rounded-xl text-sm leading-none',
            'nm-neu-pressed border-none text-text onboarding-select-trigger',
            'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-dropdown-bg',
            'transition-all duration-200 active:scale-[0.98]',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'min-w-32',
            triggerClassName
          )}
        >
          <span className="inline-flex max-w-full items-center justify-center gap-2">
            <span className="truncate leading-none">{displayLabel}</span>
            <svg
              className="h-4 w-4 shrink-0 text-muted"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className={cn('max-h-[min(16rem,70vh)] overflow-y-auto', contentClassName)}>
        <DropdownMenuRadioGroup value={value} onValueChange={(v) => onValueChange(v as T)}>
          {options.map((opt) => (
            <DropdownMenuRadioItem key={opt.value} value={opt.value} disabled={opt.disabled}>
              <DropdownMenuItemIndicator />
              {opt.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
