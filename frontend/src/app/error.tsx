'use client';

import { useEffect } from 'react';
import { logError } from '@/lib/errorLogger';

interface GlobalErrorProps {
  error: Error & { digest?: string };
}

export default function GlobalError({ error }: GlobalErrorProps) {
  useEffect(() => {
    logError(error, {
      boundary: 'app/error',
      digest: error.digest,
    });
  }, [error]);

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-6">
      <div className="w-full max-w-lg rounded-xl border border-border bg-surface p-6 text-center">
        <h1 className="text-xl font-semibold text-text">Something went wrong</h1>
        <p className="mt-3 text-sm text-muted">
          Something went wrong. Please refresh the page or contact support.
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-5 inline-flex h-10 items-center justify-center rounded-xl bg-accent px-4 text-sm font-medium text-white hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-surface"
        >
          Refresh page
        </button>
      </div>
    </div>
  );
}
