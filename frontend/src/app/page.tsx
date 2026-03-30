'use client';

/**
 * Root page - handles auth routing
 * 
 * - If authenticated and onboarding not complete → /onboarding
 * - If authenticated and onboarding complete → /findings
 * - If not authenticated → /landing
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { NeumorphicLoader } from '@/components/ui/NeumorphicLoader';

export default function Home() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();

  useEffect(() => {
    if (isLoading) return;

    if (isAuthenticated) {
      // Check onboarding status
      if (!user?.onboarding_completed_at) {
        router.replace('/onboarding');
      } else {
        router.replace('/findings');
      }
    } else {
      // Not authenticated - show marketing/landing experience by default
      router.replace('/landing');
    }
  }, [isAuthenticated, isLoading, user, router]);


  // Loading state
  return (
    <div className="min-h-screen bg-bg flex items-center justify-center">
      <NeumorphicLoader />
    </div>
  );
}
