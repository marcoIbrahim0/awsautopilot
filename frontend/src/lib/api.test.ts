import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

async function loadApiModule() {
  vi.resetModules();
  return import('@/lib/api');
}

describe('api runtime base URL resolution', () => {
  const originalFetch = global.fetch;
  const originalLocation = window.location;

  beforeEach(() => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'https://api.ocypheris.com');
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { hostname: 'ocypheris.com' },
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
    global.fetch = originalFetch;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
    vi.resetModules();
  });

  it('uses the runtime public API URL for attack path requests on production hosts', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0 }),
    });
    global.fetch = fetchMock as typeof fetch;

    const { getAttackPaths } = await loadApiModule();
    await getAttackPaths({ limit: 2, offset: 1 });

    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.ocypheris.com/api/actions/attack-paths?limit=2&offset=1',
      expect.objectContaining({
        credentials: 'include',
      }),
    );
  });
});
