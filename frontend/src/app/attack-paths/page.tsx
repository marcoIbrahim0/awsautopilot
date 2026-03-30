import { Suspense } from 'react';

import AttackPathsPageClient from './AttackPathsPageClient';

export const runtime = 'nodejs';

function AttackPathsPageFallback() {
  return <div className="mx-auto w-full max-w-7xl px-6 py-10 text-sm text-muted">Loading attack paths…</div>;
}

export default function AttackPathsPage() {
  return (
    <Suspense fallback={<AttackPathsPageFallback />}>
      <AttackPathsPageClient />
    </Suspense>
  );
}
