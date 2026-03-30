import { describe, expect, it } from 'vitest';

import type { AwsAccount } from '@/lib/api';

import {
  buildOnboardingAccountMutation,
  resolveOnboardingConnectedAccount,
  upsertAwsAccount,
} from '@/app/onboarding/account-connection';

function buildAccount(overrides: Partial<AwsAccount> = {}): AwsAccount {
  return {
    id: overrides.id ?? 'account-row-1',
    account_id: overrides.account_id ?? '123456789012',
    role_read_arn: overrides.role_read_arn ?? 'arn:aws:iam::123456789012:role/ReadRole',
    role_write_arn: overrides.role_write_arn ?? null,
    regions: overrides.regions ?? ['us-east-1'],
    status: overrides.status ?? 'validated',
    last_validated_at: overrides.last_validated_at ?? '2026-03-11T10:00:00Z',
    created_at: overrides.created_at ?? '2026-03-11T10:00:00Z',
    updated_at: overrides.updated_at ?? '2026-03-11T10:00:00Z',
  };
}

describe('onboarding account connection helpers', () => {
  it('builds an update mutation when the account is already connected', () => {
    const existingAccount = buildAccount({ id: 'existing-row' });

    const mutation = buildOnboardingAccountMutation({
      existingAccount,
      parsedAccountId: '123456789012',
      regions: ['eu-west-1', 'us-east-1'],
      roleReadArn: 'arn:aws:iam::123456789012:role/NewReadRole',
      tenantId: 'tenant-1',
    });

    expect(mutation).toEqual({
      kind: 'update',
      accountId: '123456789012',
      payload: {
        role_read_arn: 'arn:aws:iam::123456789012:role/NewReadRole',
        regions: ['eu-west-1', 'us-east-1'],
      },
    });
  });

  it('builds a register mutation when no connected account exists', () => {
    const mutation = buildOnboardingAccountMutation({
      existingAccount: null,
      parsedAccountId: '123456789012',
      regions: ['us-east-1'],
      roleReadArn: 'arn:aws:iam::123456789012:role/ReadRole',
      tenantId: 'tenant-1',
    });

    expect(mutation).toEqual({
      kind: 'register',
      accountId: '123456789012',
      payload: {
        account_id: '123456789012',
        role_read_arn: 'arn:aws:iam::123456789012:role/ReadRole',
        role_write_arn: null,
        regions: ['us-east-1'],
        tenant_id: 'tenant-1',
      },
    });
  });

  it('ignores a stale connectedAccountId when the user changed to a different account', () => {
    const staleAccount = buildAccount({ id: 'stale-row', account_id: '111111111111' });
    const matchingAccount = buildAccount({ id: 'matching-row', account_id: '222222222222' });

    const resolved = resolveOnboardingConnectedAccount({
      accounts: [staleAccount, matchingAccount],
      connectedAccountId: staleAccount.id,
      parsedAccountId: '222222222222',
      fallbackAccount: staleAccount,
    });

    expect(resolved).toEqual(matchingAccount);
  });

  it('replaces an existing cached account in place', () => {
    const oldAccount = buildAccount({ id: 'row-1', regions: ['us-east-1'] });
    const otherAccount = buildAccount({ id: 'row-2', account_id: '999999999999' });
    const nextAccount = buildAccount({ id: 'row-1', regions: ['us-east-1', 'us-west-2'] });

    const updated = upsertAwsAccount([oldAccount, otherAccount], nextAccount);

    expect(updated).toEqual([nextAccount, otherAccount]);
  });
});
