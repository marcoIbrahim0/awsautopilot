'use client';

import { Button } from '@/components/ui/Button';

export default function SessionExpiredPage() {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-6">
      <div className="w-full max-w-md rounded-2xl border border-border bg-surface p-8 text-center">
        <h1 className="text-2xl font-bold text-text">Session expired</h1>
        <p className="mt-3 text-sm text-muted">
          Your session has ended. Please sign in again to continue.
        </p>
        <Button
          type="button"
          className="mt-6 w-full py-3 rounded-xl"
          onClick={() => { window.location.href = '/login'; }}
        >
          Go to sign in
        </Button>
      </div>
    </div>
  );
}
