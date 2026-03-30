import type { AwsAccount, RegisterAccountRequest, UpdateAccountRequest } from '@/lib/api';

interface ResolveOnboardingConnectedAccountArgs {
  accounts: AwsAccount[];
  connectedAccountId: string | null;
  parsedAccountId: string;
  fallbackAccount?: AwsAccount | null;
}

interface BuildOnboardingAccountMutationArgs {
  existingAccount: AwsAccount | null;
  parsedAccountId: string;
  regions: string[];
  roleReadArn: string;
  tenantId: string;
}

export type OnboardingAccountMutation =
  | { accountId: string; kind: 'register'; payload: RegisterAccountRequest }
  | { accountId: string; kind: 'update'; payload: UpdateAccountRequest };

export function resolveOnboardingConnectedAccount({
  accounts,
  connectedAccountId,
  parsedAccountId,
  fallbackAccount,
}: ResolveOnboardingConnectedAccountArgs): AwsAccount | null {
  const fallback =
    fallbackAccount && (!parsedAccountId || fallbackAccount.account_id === parsedAccountId) ? fallbackAccount : null;
  const matchedById = connectedAccountId
    ? accounts.find((account) => account.id === connectedAccountId) ?? null
    : null;

  if (matchedById && (!parsedAccountId || matchedById.account_id === parsedAccountId)) return matchedById;
  if (!parsedAccountId) return fallback;
  return accounts.find((account) => account.account_id === parsedAccountId) ?? fallback;
}

export function upsertAwsAccount(accounts: AwsAccount[], nextAccount: AwsAccount): AwsAccount[] {
  const index = accounts.findIndex(
    (account) => account.id === nextAccount.id || account.account_id === nextAccount.account_id
  );
  if (index === -1) return [nextAccount, ...accounts];
  const next = [...accounts];
  next[index] = nextAccount;
  return next;
}

export function buildOnboardingAccountMutation({
  existingAccount,
  parsedAccountId,
  regions,
  roleReadArn,
  tenantId,
}: BuildOnboardingAccountMutationArgs): OnboardingAccountMutation {
  if (existingAccount) {
    return {
      kind: 'update',
      accountId: existingAccount.account_id,
      payload: { role_read_arn: roleReadArn, regions },
    };
  }

  return {
    kind: 'register',
    accountId: parsedAccountId,
    payload: {
      account_id: parsedAccountId,
      role_read_arn: roleReadArn,
      role_write_arn: null,
      regions,
      tenant_id: tenantId,
    },
  };
}
