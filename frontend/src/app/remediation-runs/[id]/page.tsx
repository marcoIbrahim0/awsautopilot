'use client';

import { use } from 'react';
import Link from 'next/link';
import { AppShell } from '@/components/layout';
import { RemediationRunProgress } from '@/components/RemediationRunProgress';
import { useTenantId } from '@/lib/tenant';
import { useAuth } from '@/contexts/AuthContext';

export const runtime = 'nodejs';

interface RemediationRunDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function RemediationRunDetailPage({ params }: RemediationRunDetailPageProps) {
  const { id } = use(params);
  const { tenantId } = useTenantId();
  const { isAuthenticated } = useAuth();
  const effectiveTenantId = isAuthenticated ? undefined : tenantId;
  const showContent = isAuthenticated || tenantId;

  if (!showContent) {
    return (
      <AppShell title="Generation details" wide>
        <div className="max-w-2xl p-6 text-muted">
          Sign in or enter your tenant ID to view these generation details.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title="Generation details" wide>
      <div className="mx-auto w-full px-4">
        <Link
          href="/actions"
          className="inline-flex items-center gap-2 text-muted hover:text-text mb-6 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          Back to Actions
        </Link>
        <RemediationRunProgress
          runId={id}
          tenantId={effectiveTenantId}
          compact={false}
          fullWidth
        />
      </div>
    </AppShell>
  );
}
