'use client';

import { ButtonLink } from '@/components/ui/ButtonLink';
import { buildHelpHref, type HelpTab } from '@/lib/help';

interface NeedHelpLinkProps {
  from?: string | null;
  accountId?: string | null;
  actionId?: string | null;
  findingId?: string | null;
  tab?: HelpTab;
  label?: string;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent';
}

export function NeedHelpLink({
  from,
  accountId,
  actionId,
  findingId,
  tab = 'assistant',
  label = 'Need help?',
  variant = 'secondary',
}: NeedHelpLinkProps) {
  return (
    <ButtonLink
      href={buildHelpHref({
        tab,
        from,
        accountId,
        actionId,
        findingId,
      })}
      variant={variant}
      size="sm"
    >
      {label}
    </ButtonLink>
  );
}
