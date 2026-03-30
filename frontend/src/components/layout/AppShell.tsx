'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Sidebar, SidebarProvider } from './Sidebar';
import { TopBar } from './TopBar';
import { GlobalAsyncBannerRail } from '@/components/ui/GlobalAsyncBannerRail';
import { useAuth } from '@/contexts/AuthContext';
import { NoiseBackground } from '@/components/ui/NoiseBackground';

interface AppShellProps {
  children: React.ReactNode;
  title?: string;
  wide?: boolean;
}

/**
 * AppShell - Main layout wrapper for all dashboard pages
 *
 * Uses Aceternity-style sidebar: expandable on hover (desktop), drawer (mobile).
 * Content offset by collapsed sidebar width so expanded sidebar overlays.
 */
export function AppShell({ children, title, wide = false }: AppShellProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isLoading } = useAuth();

  useEffect(() => {
    if (isLoading) return;
    if (!user) return;
    if (user.onboarding_completed_at) return;
    if (pathname === '/onboarding') return;
    router.replace('/onboarding');
  }, [isLoading, pathname, router, user]);

  return (
    <SidebarProvider>
      <div className="dashboard-neumorphic relative min-h-screen overflow-hidden">
        {/* Subtle decorative noise */}
        <div className="fixed inset-0 z-0 pointer-events-none opacity-[0.03] dark:opacity-[0.05]">
          <NoiseBackground />
        </div>

        <div
          aria-hidden="true"
          className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(circle_at_top_left,rgba(10,113,255,0.14),transparent_24%),radial-gradient(circle_at_20%_80%,rgba(15,46,155,0.12),transparent_24%),radial-gradient(circle_at_100%_0%,rgba(10,113,255,0.08),transparent_18%)]"
        />

        <div className="relative z-10">
          <Sidebar />

          {/* Main content: offset by collapsed sidebar on desktop; space for hamburger on mobile */}
          <div className="pl-14 md:pl-16 transition-all duration-200">
            <TopBar title={title} />

            <main className="p-6 flex justify-center min-h-[calc(100vh-5rem)]">
              <div className={`w-full ${wide ? 'max-w-none' : 'max-w-7xl'} mx-auto`}>
                <GlobalAsyncBannerRail />
                {children}
              </div>
            </main>
          </div>
        </div>
      </div>
    </SidebarProvider>
  );
}
