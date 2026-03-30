import '@testing-library/jest-dom/vitest';

import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { useTenantId } from './tenant';

const STORAGE_KEY = 'dev_tenant_id';

describe('useTenantId', () => {
  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY);
    delete process.env.NEXT_PUBLIC_DEV_TENANT_ID;
  });

  it('reads the persisted tenant id and reacts to same-tab updates', () => {
    process.env.NEXT_PUBLIC_DEV_TENANT_ID = 'env-tenant';
    localStorage.setItem(STORAGE_KEY, 'local-tenant');

    const { result } = renderHook(() => useTenantId());

    expect(result.current.tenantId).toBe('local-tenant');

    act(() => {
      result.current.setTenantId('next-tenant');
    });

    expect(localStorage.getItem(STORAGE_KEY)).toBe('next-tenant');
    expect(result.current.tenantId).toBe('next-tenant');
  });
});
