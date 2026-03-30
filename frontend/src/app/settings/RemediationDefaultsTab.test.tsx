import type { ReactNode } from 'react';
import { render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { RemediationDefaultsTab } from './RemediationDefaultsTab';

const mockedGetRemediationSettings = vi.fn();
const mockedPatchRemediationSettings = vi.fn();

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { role: 'admin' },
  }),
}));

vi.mock('@/components/ui/ExplainerHint', () => ({
  ExplainerHint: () => null,
}));

vi.mock('@/components/ui/Badge', () => ({
  Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock('@/components/ui/Button', () => ({
  Button: ({
    children,
    type = 'button',
  }: {
    children: ReactNode;
    type?: 'button' | 'submit' | 'reset';
  }) => <button type={type}>{children}</button>,
}));

vi.mock('@/lib/api', () => ({
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
  getRemediationSettings: (...args: unknown[]) => mockedGetRemediationSettings(...args),
  patchRemediationSettings: (...args: unknown[]) => mockedPatchRemediationSettings(...args),
}));

describe('RemediationDefaultsTab', () => {
  beforeEach(() => {
    mockedGetRemediationSettings.mockReset();
    mockedPatchRemediationSettings.mockReset();
    mockedGetRemediationSettings.mockResolvedValue({
      sg_access_path_preference: null,
      approved_admin_cidrs: [],
      approved_bastion_security_group_ids: [],
      cloudtrail: {
        default_bucket_name: null,
        default_kms_key_arn: null,
      },
      config: {
        delivery_mode: null,
        default_bucket_name: null,
        default_kms_key_arn: null,
      },
      s3_access_logs: {
        default_target_bucket_name: null,
      },
      s3_encryption: {
        mode: null,
        kms_key_arn: null,
      },
    });
    window.history.replaceState({}, '', '/settings?tab=remediation-defaults#config-default-bucket-name');
  });

  it('renders explicit remediation-default field ids and scrolls hashed targets into view', async () => {
    if (!HTMLElement.prototype.scrollIntoView) {
      HTMLElement.prototype.scrollIntoView = () => {};
    }
    const scrollSpy = vi
      .spyOn(HTMLElement.prototype, 'scrollIntoView')
      .mockImplementation(() => {});

    render(<RemediationDefaultsTab />);

    await waitFor(() => {
      expect(mockedGetRemediationSettings).toHaveBeenCalledTimes(1);
    });

    expect(document.getElementById('cloudtrail-default-bucket-name')).not.toBeNull();
    expect(document.getElementById('config-default-bucket-name')).not.toBeNull();
    expect(document.getElementById('cloudtrail-default-kms-key-arn')).not.toBeNull();
    expect(document.getElementById('s3-access-logs-default-target-bucket-name')).not.toBeNull();

    await waitFor(() => {
      expect(scrollSpy).toHaveBeenCalled();
    });

    scrollSpy.mockRestore();
  });
});
