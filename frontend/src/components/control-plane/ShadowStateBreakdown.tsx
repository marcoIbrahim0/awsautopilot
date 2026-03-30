import { ControlPlaneShadowSummaryResponse } from '@/lib/api';

interface ShadowStateBreakdownProps {
  summary: ControlPlaneShadowSummaryResponse;
  onControlSelect?: (controlId: string) => void;
}

export function ShadowStateBreakdown({ summary, onControlSelect }: ShadowStateBreakdownProps) {
  const controls = Object.entries(summary.controls || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        <StatCard label="Total" value={summary.total_rows} />
        <StatCard label="OPEN" value={summary.open_count} tone="danger" />
        <StatCard label="RESOLVED" value={summary.resolved_count} tone="success" />
        <StatCard label="SOFT_RESOLVED" value={summary.soft_resolved_count} tone="warning" />
      </div>

      <div className="rounded-xl border border-border bg-surface p-4">
        <h3 className="text-sm font-medium text-text">Controls Distribution</h3>
        <div className="mt-3 max-h-64 overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-2 pr-3">Control</th>
                <th className="py-2">Rows</th>
              </tr>
            </thead>
            <tbody>
              {controls.length === 0 && (
                <tr>
                  <td colSpan={2} className="py-3 text-muted">No control data.</td>
                </tr>
              )}
              {controls.map(([control, count]) => (
                <tr key={control} className="border-t border-border/60">
                  <td className="py-2 pr-3 font-mono text-xs">
                    {onControlSelect ? (
                      <button
                        type="button"
                        onClick={() => onControlSelect(control)}
                        className="text-left text-accent hover:underline"
                        title="Drill down"
                      >
                        {control}
                      </button>
                    ) : (
                      control
                    )}
                  </td>
                  <td className="py-2">{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'danger' | 'success' | 'warning' }) {
  const color = tone === 'danger' ? 'text-danger' : tone === 'success' ? 'text-success' : tone === 'warning' ? 'text-warning' : 'text-text';
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${color}`}>{value}</p>
    </div>
  );
}
