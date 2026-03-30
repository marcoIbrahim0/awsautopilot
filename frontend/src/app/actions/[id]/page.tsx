'use client';

import { use } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { NeedHelpLink } from '@/components/help/NeedHelpLink';
import { AppShell } from '@/components/layout';
import { ActionDetailModal } from '@/components/ActionDetailModal';
import { remediationInsetClass } from '@/components/ui/remediation-surface';

export const runtime = 'nodejs';

interface ActionDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function ActionDetailPage({ params }: ActionDetailPageProps) {
  const { id } = use(params);
  const router = useRouter();

  const handleClose = () => {
    router.push('/findings');
  };

  return (
    <AppShell title="Action Detail">
      <div className="max-w-4xl mx-auto w-full">
        <div className={`mb-6 flex flex-wrap items-center justify-between gap-3 ${remediationInsetClass('default', 'px-5 py-4')}`}>
          <Link
            href="/findings"
            className="inline-flex items-center gap-2 text-muted hover:text-text transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
            Back to Findings
          </Link>
          <NeedHelpLink from={`/actions/${id}`} actionId={id} label="Need help with this action?" />
        </div>
      </div>

      <ActionDetailModal
        actionId={id}
        isOpen={true}
        onClose={handleClose}
      />
    </AppShell>
  );
}
