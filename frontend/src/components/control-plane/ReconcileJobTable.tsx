import { ControlPlaneReconcileJob } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';

interface ReconcileJobTableProps {
  jobs: ControlPlaneReconcileJob[];
}

function statusVariant(status: string) {
  const value = status.toLowerCase();
  if (value === 'enqueued') return 'success';
  if (value === 'error') return 'danger';
  if (value === 'queued') return 'warning';
  return 'default' as const;
}

export function ReconcileJobTable({ jobs }: ReconcileJobTableProps) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <h3 className="text-sm font-medium text-text">Recent Reconcile Operations</h3>
      <div className="mt-3 overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="py-2 pr-3">Job Type</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2 pr-3">Submitted</th>
              <th className="py-2 pr-3">Submitted By</th>
              <th className="py-2 pr-3">Payload</th>
              <th className="py-2">Error</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 && (
              <tr>
                <td colSpan={6} className="py-3 text-muted">No reconcile jobs yet.</td>
              </tr>
            )}
            {jobs.map((job) => (
              <tr key={job.id} className="border-t border-border/60 align-top">
                <td className="py-2 pr-3 font-mono text-xs">{job.job_type}</td>
                <td className="py-2 pr-3"><Badge variant={statusVariant(job.status)}>{job.status}</Badge></td>
                <td className="py-2 pr-3">{job.submitted_at ? new Date(job.submitted_at).toLocaleString() : '—'}</td>
                <td className="py-2 pr-3">{job.submitted_by ?? '—'}</td>
                <td className="py-2 pr-3">
                  {job.payload_summary ? (
                    <pre className="max-w-sm whitespace-pre-wrap text-xs text-muted">{JSON.stringify(job.payload_summary, null, 2)}</pre>
                  ) : '—'}
                </td>
                <td className="py-2 text-danger">{job.error_message ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
