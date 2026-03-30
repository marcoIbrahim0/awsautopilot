import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import VerifyEmailCallbackPage from './page';

const {
  replace,
  loadPendingEmailVerificationState,
  firebaseSyncEmailVerification,
  clearPendingEmailVerificationState,
  startNavigationFeedback,
  navigationState,
} = vi.hoisted(() => ({
  replace: vi.fn(),
  loadPendingEmailVerificationState: vi.fn(),
  firebaseSyncEmailVerification: vi.fn(),
  clearPendingEmailVerificationState: vi.fn(),
  startNavigationFeedback: vi.fn(),
  navigationState: { search: '' },
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(navigationState.search),
}));

vi.mock('firebase/auth', () => ({
  applyActionCode: vi.fn(),
  checkActionCode: vi.fn(),
}));

vi.mock('@/components/ui', () => ({
  ThemeToggle: () => <div>Theme Toggle</div>,
}));

vi.mock('@/components/ui/Button', () => ({
  Button: ({
    children,
    disabled,
    onClick,
  }: {
    children: ReactNode;
    disabled?: boolean;
    onClick?: () => void;
  }) => (
    <button type="button" disabled={disabled} onClick={onClick}>
      {children}
    </button>
  ),
}));

vi.mock('@/components/ui/NeumorphicLoader', () => ({
  NeumorphicLoader: () => <div>Loading...</div>,
}));

vi.mock('motion/react', () => ({
  motion: {
    div: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  },
}));

vi.mock('@/lib/api', () => ({
  firebaseSyncEmailVerification,
  getErrorMessage: vi.fn(() => 'Request failed'),
  resendEmailVerification: vi.fn(),
}));

vi.mock('@/lib/firebase', () => ({
  getFirebaseAuth: vi.fn(() => ({})),
}));

vi.mock('@/lib/navigation-feedback', () => ({
  startNavigationFeedback,
}));

vi.mock('@/lib/verification-email', () => ({
  clearPendingEmailVerificationState,
  deliverFirebaseVerificationEmail: vi.fn(),
  loadPendingEmailVerificationState,
  savePendingEmailVerificationState: vi.fn(),
}));

describe('VerifyEmailCallbackPage', () => {
  beforeEach(() => {
    navigationState.search = '';
    replace.mockReset();
    loadPendingEmailVerificationState.mockReset();
    loadPendingEmailVerificationState.mockReturnValue(null);
    firebaseSyncEmailVerification.mockReset();
    clearPendingEmailVerificationState.mockReset();
    startNavigationFeedback.mockReset();
  });

  it('does not render free-form email resend when no stored resend ticket exists', async () => {
    render(<VerifyEmailCallbackPage />);

    expect(await screen.findByText(/This verification link is incomplete or invalid./i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('you@company.com')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resend verification email' })).toBeDisabled();
  });

  it('syncs and redirects when the callback only contains a sync token', async () => {
    navigationState.search = 'vt=sync-token';
    loadPendingEmailVerificationState.mockReturnValue({
      email: 'verify-sync@example.com',
      resend_ticket: 'resend-ticket',
    });
    firebaseSyncEmailVerification.mockResolvedValue({ verified: true });

    render(<VerifyEmailCallbackPage />);

    await screen.findByText(/Applying your Firebase verification and syncing your account./i);
    await waitFor(() => {
      expect(firebaseSyncEmailVerification).toHaveBeenCalledWith({ sync_token: 'sync-token' });
      expect(clearPendingEmailVerificationState).toHaveBeenCalledTimes(1);
      expect(startNavigationFeedback).toHaveBeenCalledTimes(1);
      expect(replace).toHaveBeenCalledWith('/login?verified=1');
    });
  });
});
