'use client';

import type { HTMLAttributes, ReactNode } from 'react';

import { ExplainerHint } from '@/components/ui/ExplainerHint';
import { cn } from '@/lib/utils';

export type RemediationTone =
  | 'default'
  | 'accent'
  | 'info'
  | 'success'
  | 'warning'
  | 'danger';

const PANEL_BASE_CLASS =
  'relative overflow-hidden rounded-[2rem] border bg-[var(--card)] shadow-[0_28px_70px_-38px_rgba(15,23,42,0.48)] backdrop-blur-xl';

const PANEL_TONE_CLASS: Record<RemediationTone, string> = {
  default: 'border-[var(--border-card)]',
  accent: 'border-accent/24 dark:border-accent/34',
  info: 'border-accent/24 dark:border-accent/34',
  success: 'border-success/24 dark:border-success/32',
  warning: 'border-warning/28 dark:border-warning/34',
  danger: 'border-danger/28 dark:border-danger/34',
};

const PANEL_BAND_CLASS: Record<RemediationTone, string | null> = {
  default: null,
  accent: 'from-[#0f2e9b]/18 via-[#0a71ff]/10 to-transparent',
  info: 'from-[#0f2e9b]/18 via-[#0a71ff]/10 to-transparent',
  success: 'from-success/16 via-success/8 to-transparent',
  warning: 'from-warning/16 via-warning/8 to-transparent',
  danger: 'from-danger/16 via-danger/8 to-transparent',
};

const INSET_CLASS: Record<RemediationTone, string> = {
  default:
    'border-[var(--border-soft)] bg-[var(--card-inset)] shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]',
  accent:
    'border-accent/18 bg-accent/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]',
  info:
    'border-accent/18 bg-accent/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]',
  success:
    'border-success/18 bg-success/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]',
  warning:
    'border-warning/18 bg-warning/12 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]',
  danger:
    'border-danger/18 bg-danger/12 shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]',
};

const CALLOUT_CLASS: Record<RemediationTone, string> = {
  default: 'border-[var(--border-card)] bg-[var(--overlay)] text-text',
  accent: 'border-accent/20 bg-accent/10 text-text',
  info: 'border-accent/20 bg-accent/10 text-text',
  success: 'border-success/22 bg-success/12 text-text',
  warning: 'border-warning/24 bg-warning/12 text-text',
  danger: 'border-danger/24 bg-danger/12 text-text',
};

export const REMEDIATION_DIALOG_CLASS =
  '[--nm-base:#dde6f0] [--nm-base-dark:#c3cfdd] [--nm-shadow-dark:rgba(158,172,191,0.85)] [--nm-shadow-light:rgba(255,255,255,0.95)] dark:[--nm-base:#010206] dark:[--nm-base-dark:#000000] dark:[--nm-shadow-dark:rgba(0,0,0,0.98)] dark:[--nm-shadow-light:rgba(255,255,255,0.05)] bg-[var(--overlay)] border border-[var(--border-shell)] rounded-[2.5rem] shadow-[0_32px_90px_rgba(0,0,0,0.3)] backdrop-blur-2xl';

export const REMEDIATION_DIALOG_HEADER_CLASS =
  'border-b border-[var(--border-soft)] bg-[var(--card-hero)] px-8 py-6';

export const REMEDIATION_DIALOG_BODY_CLASS =
  'px-8 py-8 min-w-0 overflow-y-auto overflow-x-hidden';

export const REMEDIATION_EYEBROW_CLASS =
  'text-[10px] font-bold uppercase tracking-[0.2em] text-muted/70';

export const REMEDIATION_SECTION_TITLE_CLASS =
  'text-lg font-semibold leading-tight text-text';

export function remediationPanelClass(
  tone: RemediationTone = 'default',
  className?: string,
) {
  return cn(PANEL_BASE_CLASS, PANEL_TONE_CLASS[tone], className);
}

export function remediationInsetClass(
  tone: RemediationTone = 'default',
  className?: string,
) {
  return cn(
    'rounded-[1.5rem] border px-5 py-4',
    INSET_CLASS[tone],
    className,
  );
}

export function remediationCalloutClass(
  tone: RemediationTone = 'default',
  className?: string,
) {
  return cn(
    'rounded-[1.5rem] border px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.36)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]',
    CALLOUT_CLASS[tone],
    className,
  );
}

export function remediationTableWrapperClass(className?: string) {
  return remediationPanelClass('default', cn('overflow-hidden', className));
}

export function dashboardTabListClass(className?: string) {
  return cn(
    'inline-flex flex-wrap items-center gap-2 rounded-[1.75rem] border border-[var(--border-card)] bg-[var(--card)] p-2 shadow-[0_18px_40px_-28px_rgba(15,23,42,0.42)] backdrop-blur-xl',
    className,
  );
}

export function dashboardTabButtonClass(active: boolean, className?: string) {
  return cn(
    'rounded-full px-4 py-2.5 text-sm font-semibold transition-all duration-150',
    active
      ? 'bg-tab-active text-[var(--tab-active-text)] shadow-[0_16px_28px_-20px_rgba(10,48,145,0.95)]'
      : 'border border-transparent bg-transparent text-muted hover:border-[var(--border-strong)] hover:bg-[var(--control-hover)] hover:text-text',
    className,
  );
}

export function dashboardFieldClass(className?: string) {
  return cn(
    'w-full rounded-2xl border border-[var(--border-card)] bg-[var(--control-bg)] px-4 py-3 text-sm text-text shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] outline-none transition-all duration-150 placeholder:text-muted focus:ring-2 focus:ring-ring focus:border-[var(--border-strong)] focus:bg-[var(--control-hover)] disabled:cursor-not-allowed disabled:opacity-50',
    className,
  );
}

export function DashboardTabList({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={dashboardTabListClass(className)} {...props}>
      {children}
    </div>
  );
}

export function DashboardTabButton({
  active,
  className,
  ...props
}: HTMLAttributes<HTMLButtonElement> & { active: boolean }) {
  return <button type="button" className={dashboardTabButtonClass(active, className)} {...props} />;
}

export function DashboardHero({
  eyebrow,
  title,
  titleExplainer,
  description,
  action,
  children,
  className,
  tone = 'accent',
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  titleExplainer?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
  tone?: RemediationTone;
}) {
  return (
    <RemediationSection
      eyebrow={eyebrow}
      title={title}
      titleExplainer={titleExplainer}
      description={description}
      action={action}
      tone={tone}
      className={className}
    >
      {children}
    </RemediationSection>
  );
}

export function DashboardFilterBar({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={remediationInsetClass('default', cn('flex flex-col gap-3', className))}>{children}</div>;
}

export function DashboardTableCard({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('overflow-hidden rounded-[1.7rem] border border-[var(--border-card)] bg-[var(--card)]', className)}>
      {children}
    </div>
  );
}

interface RemediationPanelProps extends HTMLAttributes<HTMLDivElement> {
  tone?: RemediationTone;
}

export function RemediationPanel({
  children,
  className,
  tone = 'default',
  ...props
}: RemediationPanelProps) {
  const bandClass = PANEL_BAND_CLASS[tone];

  return (
    <div className={remediationPanelClass(tone, className)} {...props}>
      {bandClass ? (
        <div
          aria-hidden="true"
          className={cn(
            'pointer-events-none absolute inset-x-0 top-0 h-32 bg-gradient-to-b opacity-80',
            bandClass,
          )}
        />
      ) : null}
      <div className="relative">{children}</div>
    </div>
  );
}

interface RemediationSectionProps
  extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  action?: ReactNode;
  description?: ReactNode;
  descriptionExplainer?: ReactNode;
  eyebrow?: ReactNode;
  titleExplainer?: ReactNode;
  title?: ReactNode;
  tone?: RemediationTone;
}

export function RemediationSection({
  action,
  children,
  className,
  description,
  descriptionExplainer,
  eyebrow,
  titleExplainer,
  title,
  tone = 'default',
  ...props
}: RemediationSectionProps) {
  const hasHeader = eyebrow || title || description || action;

  return (
    <RemediationPanel className={className} tone={tone} {...props}>
      {hasHeader ? (
        <div className="flex flex-col gap-4 border-b border-border/35 px-6 py-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            {eyebrow ? <p className={REMEDIATION_EYEBROW_CLASS}>{eyebrow}</p> : null}
            {title ? (
              <div className="flex flex-wrap items-center gap-2">
                <h3 className={REMEDIATION_SECTION_TITLE_CLASS}>{title}</h3>
                {titleExplainer}
              </div>
            ) : null}
            {description ? (
              <div className="flex max-w-3xl flex-wrap items-start gap-2">
                <p className="text-sm leading-7 text-text/72">{description}</p>
                {descriptionExplainer}
              </div>
            ) : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </div>
      ) : null}
      <div className="px-6 py-6">{children}</div>
    </RemediationPanel>
  );
}

interface RemediationStatCardProps extends HTMLAttributes<HTMLDivElement> {
  detail?: ReactNode;
  label: ReactNode;
  labelExplainer?: ReactNode;
  value: ReactNode;
}

export function RemediationStatCard({
  className,
  detail,
  label,
  labelExplainer,
  value,
  ...props
}: RemediationStatCardProps) {
  return (
    <div className={remediationInsetClass('default', className)} {...props}>
      <div className="flex flex-wrap items-center gap-2">
        <p className={REMEDIATION_EYEBROW_CLASS}>{label}</p>
        {labelExplainer}
      </div>
      <p className="mt-3 text-3xl font-semibold leading-none text-text">{value}</p>
      {detail ? <p className="mt-3 text-sm leading-6 text-text/68">{detail}</p> : null}
    </div>
  );
}

interface RemediationCalloutProps
  extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  description?: ReactNode;
  title?: ReactNode;
  tone?: RemediationTone;
}

export function RemediationCallout({
  children,
  className,
  description,
  title,
  tone = 'default',
  ...props
}: RemediationCalloutProps) {
  return (
    <div className={remediationCalloutClass(tone, className)} {...props}>
      {title ? <p className="text-sm font-semibold text-text">{title}</p> : null}
      {description ? (
        <p className={cn('text-sm leading-6 text-text/76', title ? 'mt-1' : null)}>
          {description}
        </p>
      ) : null}
      {children ? <div className={cn(title || description ? 'mt-3' : null)}>{children}</div> : null}
    </div>
  );
}

export function RemediationPromptRow({
  action,
  className,
  description,
  title,
  tone = 'default',
  ...props
}: Omit<HTMLAttributes<HTMLDivElement>, 'title'> & {
  action?: ReactNode;
  description?: ReactNode;
  title: ReactNode;
  tone?: RemediationTone;
}) {
  return (
    <div className={remediationInsetClass(tone, cn('space-y-3', className))} {...props}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1.5">
          <p className="text-sm font-semibold leading-6 text-text">{title}</p>
          {description ? <p className="text-sm leading-6 text-text/72">{description}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </div>
  );
}

export function SectionTitleExplainer({
  conceptId,
  context = 'default',
  label,
}: {
  conceptId: import('@/components/operatorExplainers').ExplainerConceptId;
  context?: import('@/components/operatorExplainers').ExplainerContext;
  label?: string;
}) {
  return <ExplainerHint content={{ conceptId, context }} label={label} iconOnly />;
}
