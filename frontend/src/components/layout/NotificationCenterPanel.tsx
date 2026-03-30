'use client';

import Link from 'next/link';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { type NotificationCenterItem } from '@/lib/api';

interface NotificationCenterPanelProps {
  items: NotificationCenterItem[];
  isLoading: boolean;
  error: string | null;
  unreadCount: number;
  onMarkAllRead: () => void;
  onArchive: (item: NotificationCenterItem) => void;
  onClose?: () => void;
}

const ACTIVE_JOB_STATUSES = new Set(['queued', 'running', 'partial']);


function isActiveJob(status: string): boolean {
  return ACTIVE_JOB_STATUSES.has(status);
}


function badgeVariant(severity: string): 'default' | 'success' | 'warning' | 'danger' | 'info' {
  if (severity === 'success') return 'success';
  if (severity === 'warning') return 'warning';
  if (severity === 'error') return 'danger';
  if (severity === 'info') return 'info';
  return 'default';
}


function statusLabel(status: string): string {
  return status.replace(/_/g, ' ');
}


function timeAgo(iso: string | null): string {
  if (!iso) return 'Just now';
  const diff = Date.now() - Date.parse(iso);
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}


function NotificationRow({
  item,
  onArchive,
  onClose,
}: {
  item: NotificationCenterItem;
  onArchive: (item: NotificationCenterItem) => void;
  onClose?: () => void;
}) {
  const canArchive = !isActiveJob(item.status) && Boolean(item.read_at);
  return (
    <article className="rounded-3xl border border-border/70 bg-surface/80 p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-text">{item.title}</p>
            {!item.read_at ? <span className="h-2 w-2 rounded-full bg-accent" aria-hidden /> : null}
          </div>
          <p className="text-sm text-text/90">{item.message}</p>
        </div>
        <Badge variant={badgeVariant(item.severity)}>{statusLabel(item.status)}</Badge>
      </div>
      {typeof item.progress === 'number' ? (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-border/40">
          <div
            className="h-full rounded-full bg-accent transition-all duration-300"
            style={{ width: `${Math.max(0, Math.min(100, item.progress))}%` }}
          />
        </div>
      ) : null}
      {item.detail ? <p className="mt-2 text-xs text-muted">{item.detail}</p> : null}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted">{timeAgo(item.updated_at || item.created_at)}</p>
        <div className="flex flex-wrap items-center gap-2">
          {item.action_url ? (
            <Link
              href={item.action_url}
              onClick={onClose}
              className="inline-flex min-h-11 items-center rounded-full px-3 text-sm font-medium text-accent hover:bg-accent/10"
            >
              Open
            </Link>
          ) : null}
          {canArchive ? (
            <Button type="button" variant="ghost" size="sm" onClick={() => onArchive(item)} className="min-h-11 rounded-full">
              Archive
            </Button>
          ) : null}
        </div>
      </div>
    </article>
  );
}


export function NotificationCenterPanel({
  items,
  isLoading,
  error,
  unreadCount,
  onMarkAllRead,
  onArchive,
  onClose,
}: NotificationCenterPanelProps) {
  const activeJobs = items.filter((item) => item.source === 'background_job' && isActiveJob(item.status));
  const recentAlerts = items.filter((item) => !(item.source === 'background_job' && isActiveJob(item.status)));
  return (
    <div className="flex max-h-[min(80vh,40rem)] min-h-[18rem] w-full flex-col bg-dropdown-bg">
      <div className="flex items-center justify-between gap-3 border-b border-border/70 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-text">Notification Center</p>
          <p className="text-xs text-muted">{unreadCount} unread</p>
        </div>
        <div className="flex items-center gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onMarkAllRead} className="min-h-11 rounded-full">
            Mark all read
          </Button>
          {onClose ? (
            <Button type="button" variant="ghost" size="sm" onClick={onClose} className="min-h-11 rounded-full">
              Close
            </Button>
          ) : null}
        </div>
      </div>
      <div className="scrollbar-hide flex-1 overflow-y-auto px-4 py-4">
        {isLoading && items.length === 0 ? (
          <p className="animate-pulse text-sm text-muted">Loading notifications...</p>
        ) : null}
        {error ? <p className="mb-3 text-sm text-danger">{error}</p> : null}
        {!isLoading && items.length === 0 ? (
          <div className="rounded-3xl border border-dashed border-border/80 px-4 py-8 text-center text-sm text-muted">
            No notifications yet.
          </div>
        ) : null}
        {activeJobs.length > 0 ? (
          <section className="space-y-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Active jobs</p>
              <Badge variant="info">{activeJobs.length}</Badge>
            </div>
            {activeJobs.map((item) => (
              <NotificationRow key={item.id} item={item} onArchive={onArchive} onClose={onClose} />
            ))}
          </section>
        ) : null}
        {recentAlerts.length > 0 ? (
          <section className={activeJobs.length > 0 ? 'mt-5 space-y-3' : 'space-y-3'}>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted">Recent alerts</p>
              <Badge variant="default">{recentAlerts.length}</Badge>
            </div>
            {recentAlerts.map((item) => (
              <NotificationRow key={item.id} item={item} onArchive={onArchive} onClose={onClose} />
            ))}
          </section>
        ) : null}
      </div>
    </div>
  );
}
