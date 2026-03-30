import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center px-6">
      <div className="w-full max-w-lg rounded-xl border border-border bg-surface p-6 text-center">
        <h1 className="text-xl font-semibold text-text">Page not found</h1>
        <p className="mt-3 text-sm text-muted">
          The page you are looking for does not exist.
        </p>
        <Link
          href="/findings"
          className="mt-5 inline-flex h-10 items-center justify-center rounded-xl bg-accent px-4 text-sm font-medium text-white hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-surface"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
