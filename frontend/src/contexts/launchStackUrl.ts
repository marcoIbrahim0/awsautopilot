const READ_ROLE_DEFAULT_STACK_NAME = 'SecurityAutopilotReadRole';

function sanitizeStackName(stackName: string | null | undefined, fallbackName = READ_ROLE_DEFAULT_STACK_NAME): string {
  const sanitized = (stackName || '').trim().replace(/[^a-zA-Z0-9-]/g, '-').slice(0, 128);
  return sanitized || fallbackName;
}

function extractLaunchUrlHashQuery(launchUrl?: string | null): string | null {
  if (!launchUrl) return null;
  for (const marker of ['#/stacks/create/review?', '#/stacks/new?', '#/stacks/create/template?']) {
    const parts = launchUrl.split(marker);
    if (parts[1]) return parts[1];
  }
  return null;
}

export function extractTemplateUrlFromLaunchUrl(launchUrl?: string | null): string | null {
  const hashQuery = extractLaunchUrlHashQuery(launchUrl);
  if (!hashQuery) return null;
  try {
    return new URLSearchParams(hashQuery).get('templateURL');
  } catch {
    return null;
  }
}

export function buildCloudFormationLaunchStackUrl({
  existingLaunchUrl,
  fallbackTemplateUrl,
  region,
  stackName,
  fallbackStackName = READ_ROLE_DEFAULT_STACK_NAME,
  fallbackParams = {},
}: {
  existingLaunchUrl?: string | null;
  fallbackTemplateUrl?: string | null;
  region?: string | null;
  stackName?: string | null;
  fallbackStackName?: string;
  fallbackParams?: Record<string, string | null | undefined>;
}): string | null {
  const normalizedRegion = (region || '').trim();
  if (!normalizedRegion) return null;

  const params = (() => {
    const hashQuery = extractLaunchUrlHashQuery(existingLaunchUrl);
    if (!hashQuery) return new URLSearchParams();
    try {
      return new URLSearchParams(hashQuery);
    } catch {
      return new URLSearchParams();
    }
  })();

  const templateUrl = params.get('templateURL') || (fallbackTemplateUrl || '').trim();
  if (!templateUrl) return null;

  params.set('templateURL', templateUrl);
  params.set('stackName', sanitizeStackName(stackName, fallbackStackName));

  for (const [key, value] of Object.entries(fallbackParams)) {
    const normalized = (value || '').trim();
    if (!normalized || params.has(key)) continue;
    params.set(key, normalized);
  }

  return `https://${normalizedRegion}.console.aws.amazon.com/cloudformation/home?region=${normalizedRegion}#/stacks/create/review?${params.toString()}`;
}
