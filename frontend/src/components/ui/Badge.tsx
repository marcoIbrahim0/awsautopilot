type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
  title?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default:
    'border-[var(--badge-border)] bg-[color:var(--badge-bg)] text-[var(--badge-text)]',
  success:
    'border-success/24 bg-success/12 text-success dark:border-success/28 dark:bg-success/16',
  warning:
    'border-warning/26 bg-warning/12 text-warning dark:border-warning/30 dark:bg-warning/18',
  danger:
    'border-danger/24 bg-danger/12 text-danger dark:border-danger/30 dark:bg-danger/16',
  info:
    'border-accent/24 bg-accent/12 text-accent dark:border-accent/30 dark:bg-accent/16',
};

export function Badge({ children, variant = 'default', className = '', title }: BadgeProps) {
  return (
    <span
      title={title}
      className={`
        inline-flex min-h-7 items-center rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.18em]
        shadow-[inset_0_1px_0_rgba(255,255,255,0.26),0_12px_24px_-22px_rgba(15,23,42,0.48)]
        backdrop-blur-sm dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.06),0_16px_30px_-24px_rgba(0,0,0,0.78)]
        ${variantStyles[variant]}
        ${className}
      `}
    >
      {children}
    </span>
  );
}

// Utility to get badge variant from account status
export function getStatusBadgeVariant(status: string): BadgeVariant {
  switch (status.toLowerCase()) {
    case 'validated':
      return 'success';
    case 'pending':
      return 'warning';
    case 'error':
      return 'danger';
    case 'disabled':
      return 'default';
    default:
      return 'default';
  }
}

// Utility to get badge variant from severity
export function getSeverityBadgeVariant(severity: string): BadgeVariant {
  switch (severity.toUpperCase()) {
    case 'CRITICAL':
      return 'danger';
    case 'HIGH':
      return 'warning';
    case 'MEDIUM':
      return 'info';
    case 'LOW':
      return 'default';
    default:
      return 'default';
  }
}

// Utility to get badge variant from action status (open, in_progress, resolved, suppressed)
export function getActionStatusBadgeVariant(status: string): BadgeVariant {
  switch (status?.toLowerCase()) {
    case 'open':
      return 'warning';
    case 'in_progress':
      return 'info';
    case 'resolved':
      return 'success';
    case 'suppressed':
      return 'default';
    default:
      return 'default';
  }
}

// Utility to get badge variant from evidence export status (pending, running, success, failed)
export function getExportStatusBadgeVariant(status: string): BadgeVariant {
  switch (status?.toLowerCase()) {
    case 'success':
      return 'success';
    case 'failed':
      return 'danger';
    case 'running':
    case 'pending':
      return 'warning';
    default:
      return 'default';
  }
}
