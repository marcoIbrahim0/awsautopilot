import Link from 'next/link';

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white text-gray-900 flex flex-col">
      <header className="border-b border-gray-100 bg-white sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-gray-900 hover:text-gray-600 transition-colors">
            <span className="font-bold text-lg tracking-tight">Ocypheris</span>
            <span className="text-xs text-gray-400 border border-gray-200 rounded px-1.5 py-0.5 font-medium">
              Autopilot
            </span>
          </Link>
          <nav className="flex items-center gap-5 text-sm text-gray-500">
            <Link href="/legal/privacy" className="hover:text-gray-900 transition-colors">Privacy Policy</Link>
            <Link href="/legal/terms" className="hover:text-gray-900 transition-colors">Terms of Service</Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        {children}
      </main>

      <footer className="border-t border-gray-100 py-8 mt-16">
        <div className="max-w-4xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-gray-400">
          <p>© {new Date().getFullYear()} Ocypheris. All rights reserved.</p>
          <div className="flex gap-5">
            <Link href="/legal/privacy" className="hover:text-gray-600 transition-colors">Privacy Policy</Link>
            <Link href="/legal/terms" className="hover:text-gray-600 transition-colors">Terms of Service</Link>
            <a href="mailto:legal@ocypheris.com" className="hover:text-gray-600 transition-colors">legal@ocypheris.com</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
