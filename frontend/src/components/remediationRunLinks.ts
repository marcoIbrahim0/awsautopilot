const GENERATED_FILES_ANCHOR = 'run-generated-files';

function isExternalHref(href: string): boolean {
  return /^[a-z][a-z0-9+.-]*:/i.test(href);
}

function getHrefAnchor(href: string): string | null {
  const hashIndex = href.indexOf('#');
  if (hashIndex === -1) return null;
  const anchor = href.slice(hashIndex + 1).trim();
  return anchor || null;
}

export function getEvidenceCardId(key: string): string {
  return `run-evidence-${key}`;
}

export function getEvidenceCardHref(runId: string, key: string): string {
  return `/remediation-runs/${runId}#${getEvidenceCardId(key)}`;
}

export function resolveRunSectionHref(
  href: string | null | undefined,
  generatedFilesVisible: boolean,
): string | null {
  if (!href) return null;
  if (isExternalHref(href)) return href;
  const anchor = getHrefAnchor(href);
  if (anchor !== GENERATED_FILES_ANCHOR) return href;
  return generatedFilesVisible ? href : null;
}

export function resolveEvidenceNavigationHref(
  runId: string,
  key: string,
  href: string | null | undefined,
  generatedFilesVisible: boolean,
): string {
  return resolveRunSectionHref(href, generatedFilesVisible) ?? getEvidenceCardHref(runId, key);
}
