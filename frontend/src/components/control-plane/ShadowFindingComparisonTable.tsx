'use client';

import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import type { ControlPlaneShadowCompareItem } from '@/lib/api';

function formatTs(value?: string | null) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString();
}

function statusVariant(normalized: string) {
  const s = (normalized || '').toUpperCase();
  if (s === 'OPEN') return 'warning';
  if (s === 'RESOLVED') return 'success';
  return 'info';
}

export function ShadowFindingComparisonTable(props: {
  items: ControlPlaneShadowCompareItem[];
  total: number;
  offset: number;
  limit: number;
  onPageChange: (nextOffset: number) => void;
}) {
  const { items, total, offset, limit, onPageChange } = props;
  const [onlyMismatches, setOnlyMismatches] = useState(false);

  const filtered = useMemo(() => {
    if (!onlyMismatches) return items;
    return items.filter((r) => r.is_mismatch);
  }, [items, onlyMismatches]);

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + limit, total);

  return (
    <section className="rounded-xl border border-border bg-surface p-6 space-y-4">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-text">Per-Finding Comparison (Shadow vs Live)</h3>
          <p className="text-sm text-muted">
            Shadow state is compared to the latest canonical finding matching (account, region, control_id, resource_id).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={onlyMismatches}
              onChange={(e) => setOnlyMismatches(e.target.checked)}
            />
            Only mismatches
          </label>
          <Badge variant="info">{pageStart}-{pageEnd} / {total}</Badge>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            disabled={offset === 0}
          >
            Prev
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onPageChange(offset + limit)}
            disabled={offset + limit >= total}
          >
            Next
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-bg/40 text-muted">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Resource</th>
              <th className="px-4 py-3 text-left font-medium">Control</th>
              <th className="px-4 py-3 text-left font-medium">Shadow</th>
              <th className="px-4 py-3 text-left font-medium">Live</th>
              <th className="px-4 py-3 text-left font-medium">Timing</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-muted" colSpan={5}>
                  {onlyMismatches ? 'No mismatches on this page.' : 'No rows.'}
                </td>
              </tr>
            ) : (
              filtered.map((row) => (
                <tr key={row.fingerprint} className={row.is_mismatch ? 'bg-warning/5' : ''}>
                  <td className="px-4 py-3">
                    <div className="font-mono text-xs text-text break-all">{row.resource_id || '—'}</div>
                    <div className="text-xs text-muted">
                      {row.account_id} · {row.region}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-mono text-xs text-text">{row.control_id || '—'}</div>
                    <div className="text-xs text-muted">{row.resource_type || '—'}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={statusVariant(row.shadow_status_normalized)}>
                        {row.shadow_status}
                      </Badge>
                      {row.status_reason && (
                        <span className="text-xs text-muted">{row.status_reason}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {row.canonical ? (
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={statusVariant(row.canonical.status_normalized)}>
                            {row.canonical.status_raw}
                          </Badge>
                          <span className="text-xs text-muted">{row.canonical.source}</span>
                        </div>
                        <div className="text-xs text-muted truncate max-w-xl" title={row.canonical.title ?? ''}>
                          {row.canonical.title || '—'}
                        </div>
                      </div>
                    ) : (
                      <Badge variant="info">No match</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-xs text-muted">
                      Shadow event: <span className="font-mono text-text">{formatTs(row.last_observed_event_time)}</span>
                    </div>
                    <div className="text-xs text-muted">
                      Shadow eval: <span className="font-mono text-text">{formatTs(row.last_evaluated_at)}</span>
                    </div>
                    <div className="text-xs text-muted">
                      Live upd: <span className="font-mono text-text">{formatTs(row.canonical?.updated_at)}</span>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
