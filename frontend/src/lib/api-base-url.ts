const LOCAL_API_URL = 'http://localhost:8000';
const LOCAL_HOSTNAMES = new Set(['localhost', '127.0.0.1']);
const PUBLIC_API_URL = (process.env.NEXT_PUBLIC_API_URL ?? '').trim();

function isLocalHostname(hostname?: string): boolean {
  return Boolean(hostname && LOCAL_HOSTNAMES.has(hostname));
}

function isLocalApiUrl(value: string): boolean {
  try {
    return isLocalHostname(new URL(value).hostname);
  } catch {
    return false;
  }
}

export function resolveApiBaseUrl(hostname?: string): string {
  if (isLocalHostname(hostname)) return LOCAL_API_URL;
  if (!PUBLIC_API_URL || isLocalApiUrl(PUBLIC_API_URL)) return '';
  return PUBLIC_API_URL;
}

export function getApiBaseUrl(): string {
  return resolveApiBaseUrl(typeof window !== 'undefined' ? window.location.hostname : undefined);
}
