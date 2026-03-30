'use client';

import Link from 'next/link';
import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { motion } from 'motion/react';
import { ThemeToggle } from '@/components/ui';
import { NeumorphicLoader } from '@/components/ui/NeumorphicLoader';
import { useAuth } from '@/contexts/AuthContext';
import { getErrorMessage, resendEmailVerification } from '@/lib/api';
import { startNavigationFeedback } from '@/lib/navigation-feedback';
import {
  deliverFirebaseVerificationEmail,
  loadPendingEmailVerificationState,
  savePendingEmailVerificationState,
} from '@/lib/verification-email';

function VerifyEmailPendingPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const fallbackEmail = searchParams.get('email') ?? '';
  const [email, setEmail] = useState(fallbackEmail);

  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isResending, setIsResending] = useState(false);
  const [hasRecoveryState, setHasRecoveryState] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    startNavigationFeedback();
    router.replace('/onboarding');
  }, [isAuthenticated, router]);

  useEffect(() => {
    const pendingState = loadPendingEmailVerificationState();
    if (!pendingState) return;
    setHasRecoveryState(true);
    setEmail(pendingState.email);
    if (!pendingState.firebase_delivery) return;
    let cancelled = false;
    void (async () => {
      try {
        await deliverFirebaseVerificationEmail(pendingState.firebase_delivery!);
        if (cancelled) return;
        setStatusMessage(`We sent a verification link to ${pendingState.email}. Click it to activate your account.`);
        savePendingEmailVerificationState({
          email: pendingState.email,
          resend_ticket: pendingState.resend_ticket,
        });
      } catch (err) {
        if (cancelled) return;
        setError(getErrorMessage(err));
        savePendingEmailVerificationState({
          email: pendingState.email,
          resend_ticket: pendingState.resend_ticket,
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleResend = async () => {
    const pendingState = loadPendingEmailVerificationState();
    if (!pendingState?.resend_ticket) {
      setError('The verification email address is missing. Return to signup and try again.');
      return;
    }

    setIsResending(true);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await resendEmailVerification({ resend_ticket: pendingState.resend_ticket });
      await deliverFirebaseVerificationEmail(response.firebase_delivery);
      savePendingEmailVerificationState({
        email: pendingState.email,
        resend_ticket: response.resend_ticket,
      });
      setStatusMessage(response.message);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsResending(false);
    }
  };

  if (authLoading) {
    return (
      <div className="auth-neumorphic min-h-screen flex items-center justify-center">
        <NeumorphicLoader />
      </div>
    );
  }

  return (
    <div className="auth-neumorphic relative min-h-screen flex items-center justify-center p-6 sm:p-10">
      <div className="absolute top-6 right-6 z-50">
        <ThemeToggle />
      </div>

      <motion.div
        className="w-full max-w-md"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold" style={{ color: 'var(--nm-text)' }}>
            Check your inbox
          </h2>
          <p className="mt-1 text-sm" style={{ color: 'var(--nm-text-muted)' }}>
            Email verification is required before sign-in.
          </p>
        </div>

        <div className="nm-raised-lg p-6 sm:p-8 space-y-4">
          <p className="text-sm leading-6" style={{ color: 'var(--nm-text-muted)' }}>
            {email
              ? `We sent a verification link to ${email}. Click it to activate your account.`
              : 'We sent a verification link to your email address. Click it to activate your account.'}
          </p>

          {statusMessage && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3">
              <p className="text-sm text-emerald-700">{statusMessage}</p>
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <button
            type="button"
            onClick={handleResend}
            disabled={isResending || !hasRecoveryState}
            className="nm-btn-primary w-full py-3 disabled:opacity-60"
          >
            {isResending ? 'Sending another link...' : 'Resend verification email'}
          </button>

          <p className="text-center text-sm" style={{ color: 'var(--nm-text-muted)' }}>
            Already verified?{' '}
            <Link href="/login" className="font-medium" style={{ color: 'var(--nm-accent)' }}>
              Sign in
            </Link>
          </p>
          {!hasRecoveryState && (
            <p className="text-center text-sm" style={{ color: 'var(--nm-text-muted)' }}>
              Verification resend is only available from your current signup or sign-in session.
            </p>
          )}
        </div>
      </motion.div>
    </div>
  );
}

export default function VerifyEmailPendingPage() {
  return (
    <Suspense
      fallback={
        <div className="auth-neumorphic min-h-screen flex items-center justify-center">
          <NeumorphicLoader />
        </div>
      }
    >
      <VerifyEmailPendingPageContent />
    </Suspense>
  );
}
