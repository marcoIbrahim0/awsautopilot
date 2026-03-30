'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { useAuth } from '@/contexts/AuthContext';
import { type BackgroundJob, useBackgroundJobs } from '@/contexts/BackgroundJobsContext';
import {
  getErrorMessage,
  getNotifications,
  patchNotificationState,
  type NotificationCenterItem,
  upsertJobNotification,
} from '@/lib/api';

interface NotificationCenterContextValue {
  items: NotificationCenterItem[];
  isLoading: boolean;
  isOpen: boolean;
  unreadCount: number;
  activeJobCount: number;
  error: string | null;
  setOpen: (open: boolean) => void;
  refresh: () => Promise<void>;
  markAllRead: () => Promise<void>;
  archiveNotification: (item: NotificationCenterItem) => Promise<void>;
}

const NotificationCenterContext = createContext<NotificationCenterContextValue | null>(null);
const ACTIVE_JOB_STATUSES = new Set(['queued', 'running', 'partial']);


function isActiveJobStatus(status: string): boolean {
  return ACTIVE_JOB_STATUSES.has(status);
}


function buildLocalJobItem(job: BackgroundJob): NotificationCenterItem {
  return {
    id: `local-job-${job.id}`,
    kind: 'job',
    source: 'background_job',
    severity: job.severity,
    status: job.status,
    title: job.title,
    message: job.message,
    detail: job.detail ?? null,
    progress: job.progress,
    action_url: null,
    target_type: null,
    target_id: null,
    client_key: job.id,
    created_at: new Date(job.createdAt).toISOString(),
    updated_at: new Date(job.updatedAt).toISOString(),
    read_at: null,
    archived_at: null,
  };
}


function mergeItems(
  serverItems: NotificationCenterItem[],
  jobs: BackgroundJob[],
  localReadAt: Record<string, string>,
  localArchivedAt: Record<string, string>,
): NotificationCenterItem[] {
  const merged = new Map<string, NotificationCenterItem>();
  for (const item of serverItems) {
    merged.set(item.client_key || item.id, item);
  }
  for (const job of jobs) {
    const local = buildLocalJobItem(job);
    const key = local.client_key || local.id;
    const existing = merged.get(key);
    const read_at = existing?.read_at ?? localReadAt[key] ?? null;
    const archived_at = existing?.archived_at ?? localArchivedAt[key] ?? null;
    if (archived_at) continue;
    merged.set(key, {
      ...(existing ?? local),
      ...local,
      id: existing?.id ?? local.id,
      read_at,
      archived_at,
    });
  }
  return Array.from(merged.values()).sort((a, b) => {
    const left = Date.parse(a.updated_at || a.created_at);
    const right = Date.parse(b.updated_at || b.created_at);
    return right - left;
  });
}


function unreadOverlayCount(items: NotificationCenterItem[], serverItems: NotificationCenterItem[]): number {
  const serverKeys = new Set(serverItems.map((item) => item.client_key || item.id));
  return items.filter((item) => {
    const key = item.client_key || item.id;
    return !item.read_at && !item.archived_at && !serverKeys.has(key);
  }).length;
}


function signatureForJob(job: BackgroundJob): string {
  return [
    job.status,
    job.title,
    job.message,
    job.detail ?? '',
    job.progress,
    job.updatedAt,
  ].join('|');
}


export function NotificationCenterProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { jobs } = useBackgroundJobs();
  const [serverItems, setServerItems] = useState<NotificationCenterItem[]>([]);
  const [serverUnreadCount, setServerUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localReadAt, setLocalReadAt] = useState<Record<string, string>>({});
  const [localArchivedAt, setLocalArchivedAt] = useState<Record<string, string>>({});
  const syncTimersRef = useRef<Map<string, number>>(new Map());
  const syncSignaturesRef = useRef<Map<string, string>>(new Map());
  const fetchAbortRef = useRef<AbortController | null>(null);

  const activeJobCount = useMemo(
    () => jobs.filter((job) => isActiveJobStatus(job.status)).length,
    [jobs],
  );

  const items = useMemo(
    () => mergeItems(serverItems, jobs, localReadAt, localArchivedAt),
    [jobs, localArchivedAt, localReadAt, serverItems],
  );

  const unreadCount = useMemo(
    () => serverUnreadCount + unreadOverlayCount(items, serverItems),
    [items, serverItems, serverUnreadCount],
  );

  const refresh = useCallback(async () => {
    if (!isAuthenticated) return;
    fetchAbortRef.current?.abort();
    const controller = new AbortController();
    fetchAbortRef.current = controller;
    setIsLoading(true);
    setError(null);
    try {
      const response = await getNotifications({ limit: 50 }, controller.signal);
      setServerItems(response.items);
      setServerUnreadCount(response.unread_total);
    } catch (err) {
      if (controller.signal.aborted) return;
      setError(getErrorMessage(err));
    } finally {
      if (!controller.signal.aborted) setIsLoading(false);
    }
  }, [isAuthenticated]);

  const syncJobNow = useCallback(async (job: BackgroundJob) => {
    try {
      await upsertJobNotification(job.id, {
        status: job.status,
        title: job.title,
        message: job.message,
        severity: job.severity,
        detail: job.detail ?? null,
        progress: job.progress,
      });
    } catch {
      return;
    }
  }, []);

  const scheduleJobSync = useCallback((job: BackgroundJob) => {
    const existing = syncTimersRef.current.get(job.id);
    if (existing) window.clearTimeout(existing);
    const delay = isActiveJobStatus(job.status) ? 700 : 0;
    const timer = window.setTimeout(() => {
      syncTimersRef.current.delete(job.id);
      void syncJobNow(job);
    }, delay);
    syncTimersRef.current.set(job.id, timer);
  }, [syncJobNow]);

  const markAllRead = useCallback(async () => {
    const now = new Date().toISOString();
    const nextReadAt: Record<string, string> = {};
    for (const item of items) {
      nextReadAt[item.client_key || item.id] = now;
    }
    setLocalReadAt((current) => ({ ...current, ...nextReadAt }));
    setServerItems((current) => current.map((item) => ({ ...item, read_at: item.read_at ?? now })));
    setServerUnreadCount(0);
    try {
      await patchNotificationState({ action: 'mark_all_read' });
    } catch (err) {
      setError(getErrorMessage(err));
      void refresh();
    }
  }, [items, refresh]);

  const archiveNotification = useCallback(async (item: NotificationCenterItem) => {
    const now = new Date().toISOString();
    const key = item.client_key || item.id;
    setLocalArchivedAt((current) => ({ ...current, [key]: now }));
    setServerItems((current) => current.filter((entry) => entry.id !== item.id));
    if (item.id.startsWith('local-job-')) return;
    try {
      await patchNotificationState({ action: 'archive', notification_ids: [item.id] });
    } catch (err) {
      setError(getErrorMessage(err));
      void refresh();
    }
  }, [refresh]);

  useEffect(() => {
    if (!isAuthenticated) {
      setServerItems([]);
      setServerUnreadCount(0);
      setIsOpen(false);
      return;
    }
    void refresh();
  }, [isAuthenticated, refresh]);

  useEffect(() => {
    if (!isAuthenticated) return;
    for (const job of jobs) {
      const next = signatureForJob(job);
      if (syncSignaturesRef.current.get(job.id) === next) continue;
      syncSignaturesRef.current.set(job.id, next);
      scheduleJobSync(job);
    }
  }, [isAuthenticated, jobs, scheduleJobSync]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const runRefresh = () => {
      if (document.hidden) return;
      void refresh();
    };
    window.addEventListener('focus', runRefresh);
    document.addEventListener('visibilitychange', runRefresh);
    return () => {
      window.removeEventListener('focus', runRefresh);
      document.removeEventListener('visibilitychange', runRefresh);
    };
  }, [isAuthenticated, refresh]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const delay = isOpen || activeJobCount > 0 ? 10_000 : 30_000;
    const timer = window.setTimeout(() => {
      if (document.hidden) return;
      void refresh();
    }, delay);
    return () => window.clearTimeout(timer);
  }, [activeJobCount, isAuthenticated, isOpen, refresh]);

  const value = useMemo<NotificationCenterContextValue>(() => ({
    items,
    isLoading,
    isOpen,
    unreadCount,
    activeJobCount,
    error,
    setOpen: setIsOpen,
    refresh,
    markAllRead,
    archiveNotification,
  }), [activeJobCount, archiveNotification, error, isLoading, isOpen, items, markAllRead, refresh, unreadCount]);

  return (
    <NotificationCenterContext.Provider value={value}>
      {children}
    </NotificationCenterContext.Provider>
  );
}


export function useNotificationCenter() {
  const context = useContext(NotificationCenterContext);
  if (!context) throw new Error('useNotificationCenter must be used within NotificationCenterProvider');
  return context;
}
