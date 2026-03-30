import { Badge } from '@/components/ui/Badge';

interface SloBurnBadgeProps {
  label: string;
  valueMs: number | null;
  targetMs: number;
}

function formatMinutes(ms: number | null): string {
  if (ms == null) return '—';
  return `${(ms / 60000).toFixed(2)} min`;
}

export function SloBurnBadge({ label, valueMs, targetMs }: SloBurnBadgeProps) {
  const ratio = valueMs == null ? 0 : valueMs / targetMs;
  const variant = valueMs == null ? 'default' : ratio <= 1 ? 'success' : ratio <= 1.25 ? 'warning' : 'danger';
  return (
    <div className="flex items-center justify-between rounded-xl border border-border bg-surface p-3">
      <p className="text-sm text-muted">{label}</p>
      <Badge variant={variant}>{formatMinutes(valueMs)}</Badge>
    </div>
  );
}
