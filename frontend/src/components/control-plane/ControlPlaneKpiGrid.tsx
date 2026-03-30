import { ControlPlaneSloResponse } from '@/lib/api';

function formatMs(value: number | null): string {
  if (value == null) return '—';
  if (value < 1000) return `${Math.round(value)} ms`;
  if (value < 60000) return `${(value / 1000).toFixed(2)} s`;
  return `${(value / 60000).toFixed(2)} min`;
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

interface ControlPlaneKpiGridProps {
  slo: ControlPlaneSloResponse;
}

export function ControlPlaneKpiGrid({ slo }: ControlPlaneKpiGridProps) {
  const items = [
    { label: 'p95 End-to-End', value: formatMs(slo.p95_end_to_end_lag_ms) },
    { label: 'p99 End-to-End', value: formatMs(slo.p99_end_to_end_lag_ms) },
    { label: 'p95 Resolution', value: formatMs(slo.p95_resolution_freshness_ms) },
    { label: 'p95 CloudTrail Delivery', value: formatMs(slo.p95_cloudtrail_delivery_lag_ms) },
    { label: 'p95 Queue Lag', value: formatMs(slo.p95_queue_lag_ms) },
    { label: 'p95 Handler Latency', value: formatMs(slo.p95_handler_latency_ms) },
    { label: 'Drop Rate', value: formatPct(slo.drop_rate) },
    { label: 'Duplicate Rate', value: formatPct(slo.duplicate_rate) },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl border border-border bg-surface p-4">
          <p className="text-xs uppercase tracking-wide text-muted">{item.label}</p>
          <p className="mt-1 text-lg font-semibold text-text">{item.value}</p>
        </div>
      ))}
    </div>
  );
}
