'use client';

import { use } from 'react';
import Link from 'next/link';

import { AppShell } from '@/components/layout';
import { RootKeyRemediationLifecycle } from '@/components/root-key/RootKeyRemediationLifecycle';
import { useAuth } from '@/contexts/AuthContext';
import { useTenantId } from '@/lib/tenant';

export const runtime = 'nodejs';

interface RootKeyRemediationRunPageProps {
  params: Promise<{ id: string }>;
}

const ROOT_KEY_UI_FLAG = process.env.NEXT_PUBLIC_ROOT_KEY_REMEDIATION_UI_ENABLED;

function isFeatureEnabled(): boolean {
  const value = (ROOT_KEY_UI_FLAG ?? '').toLowerCase();
  return value === 'true' || value === '1';
}

export default function RootKeyRemediationRunPage({ params }: RootKeyRemediationRunPageProps) {
  const { id } = use(params);
  const { tenantId } = useTenantId();
  const { isAuthenticated, user } = useAuth();

  const showContent = isAuthenticated || tenantId;
  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const isAdmin = isAuthenticated && user?.role === 'admin';

  if (!showContent) {
    return (
      <AppShell title="Root-Key Remediation Run" wide>
        <div className="max-w-2xl p-6 text-muted">Sign in or enter your tenant ID to view this run.</div>
      </AppShell>
    );
  }

  if (!isFeatureEnabled()) {
    return (
      <AppShell title="Root-Key Remediation Run" wide>
        <div className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-warning">
          <p className="text-sm font-medium">Root-key remediation UI is disabled.</p>
          <p className="mt-1 text-xs text-warning/80">
            Set <code>NEXT_PUBLIC_ROOT_KEY_REMEDIATION_UI_ENABLED=true</code> to enable this feature.
          </p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Root-Key Remediation Run" wide>
      <div className="mx-auto w-full px-4">
        <Link
          href="/actions"
          className="mb-6 inline-flex items-center gap-2 text-muted transition-colors hover:text-text"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          Back to Actions
        </Link>
        <RootKeyRemediationLifecycle runId={id} tenantId={effectiveTenantId} isAdmin={isAdmin} />
      </div>
    </AppShell>
  );
}
