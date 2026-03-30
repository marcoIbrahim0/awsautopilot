import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ChangeEvent, ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LoginPage from './page';

const {
  push,
  login,
  completeMfaLogin,
  resendEmailVerification,
  deliverFirebaseVerificationEmail,
} = vi.hoisted(() => ({
  push: vi.fn(),
  login: vi.fn(),
  completeMfaLogin: vi.fn(),
  resendEmailVerification: vi.fn(),
  deliverFirebaseVerificationEmail: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => new URLSearchParams(''),
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    login,
    completeMfaLogin,
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
    endAdornment,
  }: {
    id: string;
    label: string;
    value: string;
    onChange: (event: ChangeEvent<HTMLInputElement>) => void;
    type?: string;
    endAdornment?: ReactNode;
  }) => (
    <label htmlFor={id}>
      {label}
      <input id={id} type={type} value={value} onChange={onChange} />
      {endAdornment}
    </label>
  ),
}));

vi.mock('@/components/ui/Button', () => ({
  Button: ({
    children,
    onClick,
    disabled,
    type = 'button',
  }: {
    children: ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    type?: 'button' | 'submit' | 'reset';
  }) => (
    <button type={type} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

vi.mock('@/components/ui/Modal', () => ({
  Modal: ({
    isOpen,
    children,
    title,
  }: {
    isOpen: boolean;
    children: ReactNode;
    title: string;
  }) => (isOpen ? <div aria-label={title}>{children}</div> : null),
}));

vi.mock('@/components/ui', () => ({
  ThemeToggle: () => <div>Theme Toggle</div>,
}));

vi.mock('@/components/ui/aurora-background', () => ({
  AuroraBackground: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/ui/NeumorphicLoader', () => ({
  NeumorphicLoader: () => <div>Loading...</div>,
}));

vi.mock('@/lib/navigation-feedback', () => ({
  startNavigationFeedback: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  forgotPassword: vi.fn(),
  getErrorMessage: vi.fn(() => 'Request failed'),
  resendEmailVerification,
}));

vi.mock('@/lib/verification-email', () => ({
  deliverFirebaseVerificationEmail,
  loadPendingEmailVerificationState: vi.fn(() => ({
    email: 'pending@example.com',
    resend_ticket: 'resend-ticket-123',
  })),
  savePendingEmailVerificationState: vi.fn(),
}));

describe('LoginPage', () => {
  beforeEach(() => {
    push.mockReset();
    login.mockReset();
    completeMfaLogin.mockReset();
    resendEmailVerification.mockReset();
    deliverFirebaseVerificationEmail.mockReset();
    window.sessionStorage.clear();
    login.mockResolvedValue({ mfaRequired: false });
  });

  it('submits remember_me=false by default and true when checked', async () => {
    const user = userEvent.setup();
    const { unmount } = render(<LoginPage />);

    await user.type(screen.getByLabelText('Email'), 'marco.ibrahim@ocypheris.com');
    await user.type(screen.getByLabelText('Password'), 'Maher730@');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(login).toHaveBeenCalledWith('marco.ibrahim@ocypheris.com', 'Maher730@', false);

    login.mockClear();
    unmount();
    render(<LoginPage />);

    await user.type(screen.getByLabelText('Email'), 'marco.ibrahim@ocypheris.com');
    await user.type(screen.getByLabelText('Password'), 'Maher730@');
    await user.click(screen.getByLabelText('Remember me'));
    await user.click(screen.getByRole('button', { name: 'Sign in' }));

    expect(login).toHaveBeenCalledWith('marco.ibrahim@ocypheris.com', 'Maher730@', true);
  });

  it('toggles password visibility on the login form', async () => {
    const user = userEvent.setup();

    render(<LoginPage />);

    const passwordInput = screen.getByLabelText('Password');
    expect(passwordInput).toHaveAttribute('type', 'password');

    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(passwordInput).toHaveAttribute('type', 'text');

    await user.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('resends verification using the stored resend ticket', async () => {
    const user = userEvent.setup();
    login.mockRejectedValueOnce(
      Object.assign(new Error('email_verification_required'), {
        email: 'pending@example.com',
        resendTicket: 'resend-ticket-123',
      })
    );
    resendEmailVerification.mockResolvedValue({
      message: 'If your account exists, a new link was sent.',
      resend_ticket: 'fresh-ticket',
      firebase_delivery: {
        custom_token: 'firebase-custom-token',
        continue_url: 'https://app.example.com/verify-email/callback?vt=abc',
      },
    });

    render(<LoginPage />);

    await user.type(screen.getByLabelText('Email'), 'pending@example.com');
    await user.type(screen.getByLabelText('Password'), 'Password123!');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    await user.click(screen.getByRole('button', { name: 'Resend verification email' }));

    expect(resendEmailVerification).toHaveBeenCalledWith({ resend_ticket: 'resend-ticket-123' });
    expect(deliverFirebaseVerificationEmail).toHaveBeenCalledWith({
      custom_token: 'firebase-custom-token',
      continue_url: 'https://app.example.com/verify-email/callback?vt=abc',
    });
  });

  it('does not render the tenant-id dev mode entry point', () => {
    render(<LoginPage />);

    expect(screen.queryByText('Continue with tenant ID (dev mode)')).not.toBeInTheDocument();
  });
});
