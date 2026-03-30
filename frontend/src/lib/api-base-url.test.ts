import { afterEach, describe, expect, it, vi } from 'vitest';

async function loadApiBaseUrlModule() {
  vi.resetModules();
  return import('@/lib/api-base-url');
}

describe('resolveApiBaseUrl', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it('uses localhost for localhost frontend runtime', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'https://api.ocypheris.com');
    const { resolveApiBaseUrl } = await loadApiBaseUrlModule();

    expect(resolveApiBaseUrl('localhost')).toBe('http://localhost:8000');
    expect(resolveApiBaseUrl('127.0.0.1')).toBe('http://localhost:8000');
  });

  it('uses the configured public API URL on non-local hosts', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'https://api.ocypheris.com');
    const { resolveApiBaseUrl } = await loadApiBaseUrlModule();

    expect(resolveApiBaseUrl('ocypheris.com')).toBe('https://api.ocypheris.com');
  });

  it('fails closed when the configured API URL points at localhost on a non-local host', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'http://localhost:8000');
    const { resolveApiBaseUrl } = await loadApiBaseUrlModule();

    expect(resolveApiBaseUrl('ocypheris.com')).toBe('');
  });

  it('fails closed when NEXT_PUBLIC_API_URL is missing on a non-local host', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL', '');
    const { resolveApiBaseUrl } = await loadApiBaseUrlModule();

    expect(resolveApiBaseUrl('ocypheris.com')).toBe('');
  });
});
