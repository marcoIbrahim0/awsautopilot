'use client';

import { ReactNode } from 'react';
import { ExplainerHint } from '@/components/ui/ExplainerHint';
import type { ExplainerConceptId, ExplainerContext } from '@/components/operatorExplainers';
import {
  remediationCalloutClass,
  remediationPanelClass,
  dashboardFieldClass,
} from '@/components/ui/remediation-surface';

export function SettingsSectionIntro({
  title,
  description,
  action,
  titleExplainer,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  titleExplainer?: { conceptId: ExplainerConceptId; context?: ExplainerContext };
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-text">{title}</h2>
          {titleExplainer ? <ExplainerHint content={titleExplainer} label={title} iconOnly /> : null}
        </div>
        <p className="text-sm text-muted">{description}</p>
      </div>
      {action ? <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div> : null}
    </div>
  );
}

export function SettingsCard({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={`${remediationPanelClass('default', `p-6 ${className}`)}`}>{children}</div>;
}

export function SettingsNotice({
  tone,
  children,
}: {
  tone: 'success' | 'danger' | 'info' | 'warning';
  children: ReactNode;
}) {
  return <div className={`${remediationCalloutClass(tone, 'p-3 text-sm')}`}>{children}</div>;
}

export function TextAreaField({
  id,
  label,
  value,
  onChange,
  placeholder,
  disabled = false,
  helperText,
  rows = 4,
  labelExplainer,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  helperText?: string;
  rows?: number;
  labelExplainer?: { conceptId: ExplainerConceptId; context?: ExplainerContext };
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={id} className="block text-sm font-medium text-text">
          {label}
        </label>
        {labelExplainer ? <ExplainerHint content={labelExplainer} label={label} iconOnly /> : null}
      </div>
      <textarea
        id={id}
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        className={dashboardFieldClass('min-h-32 resize-y')}
      />
      {helperText ? <p className="text-sm text-muted">{helperText}</p> : null}
    </div>
  );
}

export function SelectField({
  id,
  label,
  value,
  onChange,
  disabled = false,
  options,
  placeholder = 'Select an option',
  labelExplainer,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  options: Array<{ value: string; label: string }>;
  placeholder?: string;
  labelExplainer?: { conceptId: ExplainerConceptId; context?: ExplainerContext };
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={id} className="block text-sm font-medium text-text">
          {label}
        </label>
        {labelExplainer ? <ExplainerHint content={labelExplainer} label={label} iconOnly /> : null}
      </div>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className={dashboardFieldClass('h-12')}
      >
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
