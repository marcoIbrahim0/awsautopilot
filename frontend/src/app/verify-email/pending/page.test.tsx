import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import VerifyEmailPendingPage from './page';

const {
  replace,
  deliverFirebaseVerificationEmail,
  loadPendingEmailVerificationState,
  savePendingEmailVerificationState,
} = vi.hoisted(() => ({
  replace: vi.fn(),
  deliverFirebaseVerificationEmail: vi.fn(),
  loadPendingEmailVerificationState: vi.fn(),
  savePendingEmailVerificationState: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams('email=admin@acme.com'),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: false,
    isLoading: false,
  }),
}));

vi.mock('@/components/ui', () => ({
  ThemeToggle: () => <div>Theme Toggle</div>,
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
  getErrorMessage: vi.fn(() => 'Request failed'),
  resendEmailVerification: vi.fn(),
}));

vi.mock('@/lib/navigation-feedback', () => ({
  startNavigationFeedback: vi.fn(),
}));

vi.mock('@/lib/verification-email', () => ({
  deliverFirebaseVerificationEmail,
  loadPendingEmailVerificationState,
  savePendingEmailVerificationState,
}));

describe('VerifyEmailPendingPage', () => {
  beforeEach(() => {
    replace.mockReset();
    deliverFirebaseVerificationEmail.mockReset();
    loadPendingEmailVerificationState.mockReset();
    savePendingEmailVerificationState.mockReset();
    loadPendingEmailVerificationState.mockReturnValue({
      email: 'admin@acme.com',
      resend_ticket: 'resend-ticket-123',
      firebase_delivery: {
        custom_token: 'firebase-custom-token',
        continue_url: 'https://app.example.com/verify-email/callback?vt=abc',
      },
    });
    deliverFirebaseVerificationEmail.mockResolvedValue(undefined);
  });

  it('auto-sends the stored Firebase verification email on first load', async () => {
    render(<VerifyEmailPendingPage />);

    await waitFor(() => {
      expect(deliverFirebaseVerificationEmail).toHaveBeenCalledWith({
        custom_token: 'firebase-custom-token',
        continue_url: 'https://app.example.com/verify-email/callback?vt=abc',
      });
    });

    expect(savePendingEmailVerificationState).toHaveBeenCalledWith({
      email: 'admin@acme.com',
      resend_ticket: 'resend-ticket-123',
    });
    expect(screen.getAllByText(/We sent a verification link to admin@acme.com/i)).toHaveLength(2);
  });
});
