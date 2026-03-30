'use client';

import { useCallback, useSyncExternalStore } from 'react';

const STORAGE_KEY = 'dev_tenant_id';
const TENANT_CHANGE_EVENT = 'dev-tenant-id-change';

function getStored(): string {
  if (typeof window === 'undefined') return '';
  try {
    return localStorage.getItem(STORAGE_KEY) ?? '';
  } catch {
    return '';
  }
}

function getFromEnv(): string {
  return (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_DEV_TENANT_ID) || '';
}

/**
 * Effective tenant ID: localStorage first (user-configured in UI), then env.
 */
export function getEffectiveTenantId(): string {
  const stored = getStored();
  if (stored.trim()) return stored.trim();
  return getFromEnv().trim();
}

function subscribeToTenantId(callback: () => void): () => void {
  if (typeof window === 'undefined') return () => {};

  window.addEventListener('storage', callback);
  window.addEventListener(TENANT_CHANGE_EVENT, callback);
  return () => {
    window.removeEventListener('storage', callback);
    window.removeEventListener(TENANT_CHANGE_EVENT, callback);
  };
}

/**
 * Hook for tenant ID with optional UI persistence.
 * Use this when you want the user to be able to set tenant ID in a text field and save.
 */
export function useTenantId(): { tenantId: string; setTenantId: (value: string) => void } {
  const tenantId = useSyncExternalStore(subscribeToTenantId, getEffectiveTenantId, getFromEnv);

  const setTenantId = useCallback((value: string) => {
    const trimmed = value.trim();
    if (typeof window !== 'undefined') {
      try {
        if (trimmed) localStorage.setItem(STORAGE_KEY, trimmed);
        else localStorage.removeItem(STORAGE_KEY);
      } catch {
        // ignore
      }
      window.dispatchEvent(new Event(TENANT_CHANGE_EVENT));
    }
  }, []);

  return { tenantId, setTenantId };
}
