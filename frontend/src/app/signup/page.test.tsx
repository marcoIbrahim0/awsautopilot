import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ChangeEvent, ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SignupPage from './page';

const { push, signup, savePendingEmailVerificationState } = vi.hoisted(() => ({
  push: vi.fn(),
  signup: vi.fn(),
  savePendingEmailVerificationState: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    signup,
    isAuthenticated: false,
    isLoading: false,
  }),
}));

vi.mock('@/components/auth', () => ({
  AuthFormField: ({
    id,
    label,
    value,
    onChange,
    type = 'text',
  }: {
    id: string;
    label: string;
    value: string;
    onChange: (event: ChangeEvent<HTMLInputElement>) => void;
    type?: string;
  }) => (
    <label htmlFor={id}>
      {label}
      <input id={id} type={type} value={value} onChange={onChange} />
    </label>
  ),
}));

vi.mock('@/components/ui', () => ({
  ThemeToggle: () => <div>Theme Toggle</div>,
}));

vi.mock('@/components/ui/NeumorphicLoader', () => ({
  NeumorphicLoader: () => <div>Loading...</div>,
}));

vi.mock('@/lib/navigation-feedback', () => ({
  startNavigationFeedback: vi.fn(),
}));

vi.mock('@/lib/verification-email', () => ({
  savePendingEmailVerificationState,
}));

describe('SignupPage', () => {
  beforeEach(() => {
    push.mockReset();
    signup.mockReset();
    savePendingEmailVerificationState.mockReset();
  });

  it('stores pending verification state before redirecting', async () => {
    const user = userEvent.setup();
    signup.mockResolvedValue({
      email: 'admin@acme.com',
      resend_ticket: 'resend-ticket-123',
      firebase_delivery: {
        custom_token: 'firebase-custom-token',
        continue_url: 'https://app.example.com/verify-email/callback?vt=abc',
      },
    });

    render(<SignupPage />);

    await user.type(screen.getByLabelText('Company name'), 'Acme Security');
    await user.type(screen.getByLabelText('Full name'), 'Acme Admin');
    await user.type(screen.getByLabelText('Email address'), 'admin@acme.com');
    await user.type(screen.getByLabelText('Password'), 'Password123!');
    await user.type(screen.getByLabelText('Confirm password'), 'Password123!');
    await user.click(screen.getByRole('button', { name: 'Sign Up' }));

    expect(savePendingEmailVerificationState).toHaveBeenCalledWith({
      email: 'admin@acme.com',
      resend_ticket: 'resend-ticket-123',
      firebase_delivery: {
        custom_token: 'firebase-custom-token',
        continue_url: 'https://app.example.com/verify-email/callback?vt=abc',
      },
    });
    expect(push).toHaveBeenCalledWith('/verify-email/pending?email=admin%40acme.com');
  });
});
