import '@testing-library/jest-dom/vitest';

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ChangeEvent, ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ConnectAccountModal } from './ConnectAccountModal';
import { registerAccount, updateAccount } from '@/lib/api';

vi.mock('@/components/ui/Modal', () => ({
  Modal: ({
    children,
    isOpen,
    title,
    variant,
    headerContent,
  }: {
    children: ReactNode;
    isOpen: boolean;
    title: string;
    variant?: string;
    headerContent?: ReactNode;
  }) => (
    isOpen ? (
      <div data-testid="modal" data-variant={variant}>
        <h1>{title}</h1>
        {headerContent}
        {children}
      </div>
    ) : null
  ),
}));

vi.mock('@/components/ui/Button', () => ({
  buttonClassName: () => '',
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

vi.mock('@/components/ui/Input', () => ({
  Input: ({
    label,
    id,
    value,
    onChange,
    helperText,
    disabled,
    ...props
  }: {
    label?: string;
    id?: string;
    value?: string;
    onChange?: (event: ChangeEvent<HTMLInputElement>) => void;
    helperText?: ReactNode;
    disabled?: boolean;
    [key: string]: unknown;
  }) => {
    const inputId = id || String(label ?? '').toLowerCase().replace(/\s+/g, '-');
    return (
      <label htmlFor={inputId}>
        <span>{label}</span>
        <input id={inputId} value={value} onChange={onChange} disabled={disabled} {...props} />
        {helperText}
      </label>
    );
  },
}));

vi.mock('@/components/ui/Badge', () => ({
  Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock('@/components/ui/SelectDropdown', () => ({
  SelectDropdown: ({
    value,
    onValueChange,
    options,
    placeholder,
  }: {
    value: string;
    onValueChange: (value: string) => void;
    options: Array<{ value: string; label: string }>;
    placeholder?: string;
  }) => (
    <label>
      <span>{placeholder || 'Select'}</span>
      <select value={value} onChange={(event) => onValueChange(event.target.value)}>
        <option value="">{placeholder || 'Select'}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  ),
}));

vi.mock('@/components/ui/remediation-surface', () => ({
  REMEDIATION_EYEBROW_CLASS: 'eyebrow',
  SectionTitleExplainer: () => null,
  RemediationCallout: ({
    children,
    title,
    description,
  }: {
    children?: ReactNode;
    title?: ReactNode;
    description?: ReactNode;
  }) => (
    <section>
      {title ? <h2>{title}</h2> : null}
      {description ? <p>{description}</p> : null}
      {children}
    </section>
  ),
  RemediationPanel: ({ children }: { children: ReactNode }) => <section>{children}</section>,
  remediationInsetClass: () => '',
}));

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => ({
    tenant: {
      id: 'tenant-1',
      external_id: 'external-123',
    },
    saas_account_id: '999999999999',
    read_role_default_stack_name: 'SecurityAutopilotReadRole',
    read_role_launch_stack_url: 'https://example.com/read-role',
    read_role_template_url: 'https://example.com/read-role/v1.5.4.yaml',
    buildReadRoleLaunchStackUrl: (stackName: string) => `https://example.com/read-role?stack=${stackName}`,
    isAuthenticated: true,
  }),
}));

vi.mock('@/lib/api', () => ({
  registerAccount: vi.fn(),
  updateAccount: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}));

const mockedRegisterAccount = vi.mocked(registerAccount);
const mockedUpdateAccount = vi.mocked(updateAccount);

describe('ConnectAccountModal', () => {
  beforeEach(() => {
    mockedRegisterAccount.mockReset();
    mockedUpdateAccount.mockReset();
    mockedRegisterAccount.mockResolvedValue({} as never);
    mockedUpdateAccount.mockResolvedValue({} as never);
  });

  it('uses dashboard modal chrome and registers a new account from the pasted ARN', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    const onClose = vi.fn();

    const { container } = render(
      <ConnectAccountModal
        isOpen
        onClose={onClose}
        onSuccess={onSuccess}
      />,
    );

    expect(screen.getByTestId('modal')).toHaveAttribute('data-variant', 'dashboard');
    expect(screen.getByRole('heading', { name: 'Connect AWS account' })).toBeInTheDocument();
    expect(screen.getByText('Deploy the ReadRole stack in AWS')).toBeInTheDocument();
    expect(screen.getByText('Save the ReadRole ARN and monitored regions')).toBeInTheDocument();
    expect(screen.getByTestId('template-version')).toHaveTextContent('v1.5.4');
    expect(screen.queryByLabelText(/WriteRole ARN/i)).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Deploy ReadRole in AWS' })).toHaveAttribute(
      'href',
      'https://example.com/read-role?stack=SecurityAutopilotReadRole',
    );
    expect(container.querySelector('a button, button a')).toBeNull();

    await user.type(
      screen.getByLabelText(/ReadRole ARN/),
      'arn:aws:iam::123456789012:role/SecurityAutopilotReadRole',
    );
    await user.click(screen.getByRole('button', { name: 'Connect account' }));

    await waitFor(() => {
      expect(mockedRegisterAccount).toHaveBeenCalledWith({
        account_id: '123456789012',
        role_read_arn: 'arn:aws:iam::123456789012:role/SecurityAutopilotReadRole',
        regions: ['us-east-1'],
        tenant_id: 'tenant-1',
      });
    });

    expect(onSuccess).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });
});
