interface FindingsHandoffParams {
  accountId?: string | null;
  region?: string | null;
  controlId?: string | null;
  status?: string | null;
  severity?: string | null;
  source?: string | null;
}

function appendIfPresent(params: URLSearchParams, key: string, value?: string | null) {
  const trimmed = value?.trim();
  if (trimmed) params.set(key, trimmed);
}

export function buildFindingsResourceScopeHandoffHref({
  accountId,
  region,
  controlId,
  status,
  severity,
  source,
}: FindingsHandoffParams): string {
  const params = new URLSearchParams({ view: 'flat' });
  appendIfPresent(params, 'account_id', accountId);
  appendIfPresent(params, 'region', region);
  appendIfPresent(params, 'control_id', controlId);
  appendIfPresent(params, 'status', status);
  appendIfPresent(params, 'severity', severity);
  appendIfPresent(params, 'source', source);
  return `/findings?${params.toString()}`;
}
