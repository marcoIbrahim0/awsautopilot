import '@testing-library/jest-dom/vitest';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import AttackPathsPageClient from './AttackPathsPageClient';
import { getAttackPath, getAttackPaths } from '@/lib/api';

const replace = vi.fn();
let searchParamValue = 'path_id=path-1&action_id=action-1';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(searchParamValue),
}));

vi.mock('@/components/layout', () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/ui/Badge', () => ({
  Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock('@/components/ui/Button', () => ({
  Button: ({
    children,
    onClick,
    type,
    variant,
  }: {
    children: ReactNode;
    onClick?: () => void;
    type?: 'button' | 'submit';
    variant?: string;
  }) => (
    <button type={type ?? 'button'} data-variant={variant} onClick={onClick}>
      {children}
    </button>
  ),
}));

vi.mock('@/components/ui/Input', () => ({
  Input: ({
    value,
    onChange,
    placeholder,
  }: {
    value?: string;
    onChange?: (event: { target: { value: string } }) => void;
    placeholder?: string;
  }) => (
    <input
      aria-label={placeholder}
      value={value}
      onChange={(event) => onChange?.({ target: { value: event.target.value } })}
      placeholder={placeholder}
    />
  ),
}));

vi.mock('@/lib/tenant', () => ({
  useTenantId: () => ({
    tenantId: 'tenant-1',
    setTenantId: vi.fn(),
  }),
}));

vi.mock('@/lib/api', () => ({
  getAttackPath: vi.fn(),
  getAttackPaths: vi.fn(),
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'Request failed'),
}));

const mockedGetAttackPath = vi.mocked(getAttackPath);
const mockedGetAttackPaths = vi.mocked(getAttackPaths);

describe('AttackPathsPageClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    searchParamValue = 'path_id=path-1&action_id=action-1';
    mockedGetAttackPaths.mockResolvedValue({
      items: [
        {
          id: 'path-1',
          status: 'available',
          rank: 86,
          confidence: 0.92,
          entry_points: [{ node_id: 'entry-1', kind: 'entry_point', label: 'Public exposure' }],
          target_assets: [{ node_id: 'target-1', kind: 'target_asset', label: 'prod-bucket' }],
          summary: 'Attackers can reach the production bucket from public exposure.',
          business_impact_summary: 'Critical production data is reachable.',
          recommended_fix_summary: 'Safest next step: Generate PR bundle via PR only.',
          owner_labels: ['Payments API'],
          linked_action_ids: ['action-1'],
          freshness: {
            summary: 'Observed 2 hours ago',
          },
          remediation_summary: {
            linked_actions_total: 1,
            open_actions: 1,
            in_progress_actions: 0,
            resolved_actions: 0,
            highest_priority_open: 86,
            coverage_summary: '1 linked action remains open and 0 already resolved.',
          },
          runtime_signals: {
            workload_presence: 'present',
            publicly_reachable: true,
            sensitive_target_count: 1,
            identity_hops: 1,
            confidence: 0.92,
            summary: '1 entry point, 1 identity hop, and 1 connected asset inform this path.',
          },
          governance_summary: {
            provider_count: 1,
            drifted_count: 0,
            in_sync_count: 1,
            linked_items: ['jira:SEC-1'],
            summary: 'External workflow links are present across 1 provider and currently aligned.',
          },
          access_scope: {
            scope: 'tenant_scoped',
            evidence_visibility: 'full',
            restricted_sections: [],
            export_allowed: true,
          },
        },
      ],
      total: 1,
      selected_view: null,
      available_views: [
        {
          key: 'actively_exploited',
          label: 'Actively exploited',
          description: 'Shared paths where exploitability pressure is prominent.',
        },
      ],
    } as never);
    mockedGetAttackPath.mockResolvedValue({
      id: 'path-1',
      status: 'available',
      rank: 91,
      rank_factors: [
        {
          factor_name: 'exploit_signals',
          label: 'Exploitability',
          contribution: 15,
          explanation: 'Threat intel and exposed surface raise priority.',
        },
      ],
      confidence: 0.94,
      freshness: {
        label: 'Fresh',
        summary: 'Observed 1 hour ago',
      },
      path_nodes: [
        { node_id: 'entry-1', kind: 'entry_point', label: 'Public exposure' },
        { node_id: 'target-1', kind: 'target_asset', label: 'prod-bucket' },
      ],
      path_edges: [{ source_node_id: 'entry-1', target_node_id: 'target-1', label: 'can reach' }],
      entry_points: [{ node_id: 'entry-1', kind: 'entry_point', label: 'Public exposure' }],
      target_assets: [{ node_id: 'target-1', kind: 'target_asset', label: 'prod-bucket' }],
      summary: 'Attackers can reach the production bucket from public exposure.',
      business_impact: {
        summary: 'Critical production data is reachable.',
      },
      risk_reasons: ['Public exposure', 'Sensitive data reachable'],
      owners: [{ owner_key: 'payments-api', owner_label: 'Payments API' }],
      recommended_fix: {
        summary: 'Safest next step: Generate PR bundle via PR only.',
      },
      linked_actions: [
        {
          id: 'action-1',
          title: 'Block public access',
          status: 'open',
        },
      ],
      remediation_summary: {
        linked_actions_total: 1,
        open_actions: 1,
        in_progress_actions: 0,
        resolved_actions: 0,
        highest_priority_open: 91,
        coverage_summary: '1 linked action remains open and 0 already resolved.',
      },
      runtime_signals: {
        workload_presence: 'present',
        publicly_reachable: true,
        sensitive_target_count: 1,
        identity_hops: 1,
        confidence: 0.94,
        summary: '1 entry point, 1 identity hop, and 1 connected asset inform this path.',
      },
      exposure_validation: {
        status: 'verified',
        summary: 'Persisted graph evidence resolves a bounded entry point and target path.',
      },
      code_context: {
        owner_label: 'Payments API',
        service_owner_key: 'payments-api',
        repository_count: 1,
        implementation_artifact_count: 1,
        summary: '1 linked repo target and 1 implementation artifact are available.',
      },
      linked_repositories: [
        {
          provider: 'generic_git',
          repository: 'acme/platform',
          base_branch: 'main',
          root_path: 'infra',
          source_run_id: 'run-1',
        },
      ],
      implementation_artifacts: [
        {
          run_id: 'run-1',
          run_status: 'success',
          run_mode: 'pr_only',
          artifact_key: 'pr_payload',
          kind: 'pr_payload',
          label: 'Provider-agnostic PR payload',
          description: 'Draft PR payload',
          href: '/remediation-runs/run-1',
          executable: false,
          generated_at: '2026-03-12T12:00:00+00:00',
          closure_status: 'pending',
          metadata: { repository: 'acme/platform' },
        },
      ],
      closure_targets: {
        open_action_ids: ['action-1'],
        in_progress_action_ids: [],
        resolved_action_ids: [],
        summary: '1 open linked action remains before this path can materially drop.',
      },
      external_workflow_summary: {
        provider_count: 1,
        drifted_count: 1,
        in_sync_count: 0,
        linked_items: ['jira:SEC-1'],
        summary: '1 linked external workflow item is drifted across 1 provider.',
      },
      exception_summary: {
        active_count: 1,
        expiring_count: 0,
        summary: '1 active exception currently governs linked actions on this path.',
      },
      evidence_exports: {
        evidence_item_count: 1,
        implementation_artifact_count: 1,
        export_ready: true,
        summary: '1 evidence item and 1 implementation artifact are available for closure review.',
      },
      access_scope: {
        scope: 'tenant_scoped',
        evidence_visibility: 'full',
        restricted_sections: [],
        export_allowed: true,
      },
      evidence: [
        { label: 'Exposure', value: 'public', source: 'graph' },
      ],
      provenance: [
        { label: 'Source', value: 'security_graph_nodes', source: 'graph' },
      ],
      truncated: false,
      availability_reason: null,
      owner_labels: ['Payments API'],
      linked_action_ids: ['action-1'],
    } as never);
  });

  it('renders ranked attack paths and loads shared detail by path_id', async () => {
    render(<AttackPathsPageClient />);

    await waitFor(() => {
      expect(mockedGetAttackPaths).toHaveBeenCalledWith(
        expect.objectContaining({ action_id: 'action-1' }),
        'tenant-1',
      );
    });

    await waitFor(() => {
      expect(mockedGetAttackPath).toHaveBeenCalledWith('path-1', 'tenant-1');
    });

    expect(screen.getAllByText('Attackers can reach the production bucket from public exposure.').length).toBeGreaterThan(0);
    expect(screen.getByText('Path detail')).toBeInTheDocument();
    expect(screen.getByText('Exploitability (+15) - Threat intel and exposed surface raise priority.')).toBeInTheDocument();
    expect(screen.getByText('Observed 1 hour ago')).toBeInTheDocument();
    expect(screen.getAllByText('Public exposure').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Critical production data is reachable.').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1 linked action remains open and 0 already resolved.').length).toBeGreaterThan(0);
    expect(screen.getByText('Runtime truth')).toBeInTheDocument();
    expect(screen.getByText('Code to cloud')).toBeInTheDocument();
    expect(screen.getByText('Workflow controls')).toBeInTheDocument();
    expect(screen.getByText('1 linked external workflow item is drifted across 1 provider.')).toBeInTheDocument();
    expect(screen.getByText('acme/platform -> main (infra)')).toBeInTheDocument();
    expect(document.querySelector('a[href*="path_id=path-1"]')).not.toBeNull();
  });

  it('applies bounded preset views through the shared list route', async () => {
    render(<AttackPathsPageClient />);

    await waitFor(() => {
      expect(screen.getByText('Actively exploited')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Actively exploited'));

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith('/attack-paths?action_id=action-1&view=actively_exploited&path_id=path-1');
    });
  });
});
