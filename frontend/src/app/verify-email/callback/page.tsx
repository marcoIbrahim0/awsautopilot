'use client';

import Link from 'next/link';
import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { applyActionCode, checkActionCode } from 'firebase/auth';
import { motion } from 'motion/react';
import { ThemeToggle } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import { NeumorphicLoader } from '@/components/ui/NeumorphicLoader';
import { firebaseSyncEmailVerification, getErrorMessage, resendEmailVerification } from '@/lib/api';
import { getFirebaseAuth } from '@/lib/firebase';
import { startNavigationFeedback } from '@/lib/navigation-feedback';
import {
  clearPendingEmailVerificationState,
  deliverFirebaseVerificationEmail,
  loadPendingEmailVerificationState,
  savePendingEmailVerificationState,
} from '@/lib/verification-email';

function extractSyncToken(continueUrl: string | null): string {
  if (!continueUrl) return '';
  try {
    const parsed = new URL(continueUrl);
    return parsed.searchParams.get('vt') ?? '';
  } catch {
    return '';
  }
}

function formatFirebaseError(error: unknown): string {
  const code = typeof error === 'object' && error && 'code' in error ? String((error as { code?: unknown }).code) : '';
  if (code === 'auth/invalid-action-code') return 'This verification link is invalid or has already been used.';
  if (code === 'auth/expired-action-code') return 'This verification link has expired.';
  if (code === 'auth/user-disabled') return 'This account is disabled.';
  return error instanceof Error ? error.message : 'Unable to verify this email link.';
}

function extractActionEmail(data: { email?: string | null } | Record<string, unknown>): string {
  if (typeof data.email === 'string' && data.email) return data.email;
  const previousEmail = 'previousEmail' in data ? data.previousEmail : null;
  return typeof previousEmail === 'string' ? previousEmail : '';
}

function VerifyEmailCallbackPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [error, setError] = useState<string | null>(null);
  const [resolvedEmail, setResolvedEmail] = useState('');
  const [resendTicket, setResendTicket] = useState('');
  const [isProcessing, setIsProcessing] = useState(true);
  const [isResending, setIsResending] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const verify = async () => {
      const mode = searchParams.get('mode');
      const oobCode = searchParams.get('oobCode');
      const syncToken = searchParams.get('vt') ?? extractSyncToken(searchParams.get('continueUrl'));
      const pendingState = loadPendingEmailVerificationState();
      const fallbackEmail = pendingState?.email ?? '';
      const fallbackTicket = pendingState?.resend_ticket ?? '';

      if (!syncToken) {
        if (!cancelled) {
          setResolvedEmail(fallbackEmail);
          setResendTicket(fallbackTicket);
          setError('This verification link is incomplete or invalid.');
          setIsProcessing(false);
        }
        return;
      }

      try {
        if (!cancelled) {
          setResolvedEmail(fallbackEmail);
          if (fallbackTicket) {
            setResendTicket(fallbackTicket);
          }
        }

        let email = fallbackEmail;
        if (mode === 'verifyEmail' && oobCode) {
          const auth = getFirebaseAuth();
          const actionInfo = await checkActionCode(auth, oobCode);
          email = extractActionEmail(actionInfo.data as Record<string, unknown>) || email;
          if (!email) {
            throw new Error('Firebase did not return an email address for this verification link.');
          }

          if (!cancelled) {
            setResolvedEmail(email);
          }

          let applyError: unknown = null;
          try {
            await applyActionCode(auth, oobCode);
          } catch (err) {
            applyError = err;
          }

          try {
            await firebaseSyncEmailVerification({
              email,
              sync_token: syncToken,
            });
          } catch (syncError) {
            throw applyError ?? syncError;
          }
        } else {
          await firebaseSyncEmailVerification({ sync_token: syncToken });
        }

        if (cancelled) return;
        clearPendingEmailVerificationState();
        startNavigationFeedback();
        router.replace('/login?verified=1');
      } catch (err) {
        if (cancelled) return;
        const message =
          typeof err === 'object' && err && 'status' in err
            ? getErrorMessage(err)
            : formatFirebaseError(err);
        setError(message);
        setIsProcessing(false);
      }
    };

    void verify();
    return () => {
      cancelled = true;
    };
  }, [router, searchParams]);

  const handleResend = async () => {
    if (!resendTicket) {
      setError('Return to signup or sign in again to request another verification email.');
      return;
    }

    setIsResending(true);
    setError(null);
    setStatusMessage(null);
    try {
      const response = await resendEmailVerification({ resend_ticket: resendTicket });
      await deliverFirebaseVerificationEmail(response.firebase_delivery);
      const preservedEmail = resolvedEmail || loadPendingEmailVerificationState()?.email || '';
      savePendingEmailVerificationState({
        email: preservedEmail,
        resend_ticket: response.resend_ticket,
      });
      setResendTicket(response.resend_ticket);
      setStatusMessage(response.message);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsResending(false);
    }
  };

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
            Verify your email
          </h2>
          <p className="mt-1 text-sm" style={{ color: 'var(--nm-text-muted)' }}>
            We’re confirming your signup link.
          </p>
        </div>

        <div className="nm-raised-lg p-6 sm:p-8 space-y-4">
          {isProcessing ? (
            <div className="flex flex-col items-center gap-4 py-8">
              <NeumorphicLoader />
              <p className="text-sm text-center" style={{ color: 'var(--nm-text-muted)' }}>
                Applying your Firebase verification and syncing your account.
              </p>
            </div>
          ) : (
            <>
              {error && (
                <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3">
                  <p className="text-sm text-red-600">{error}</p>
                </div>
              )}

              {statusMessage && (
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3">
                  <p className="text-sm text-emerald-700">{statusMessage}</p>
                </div>
              )}

              <p className="text-sm leading-6" style={{ color: 'var(--nm-text-muted)' }}>
                {resolvedEmail
                  ? `We can send another verification link to ${resolvedEmail}.`
                  : 'If this link expired, return to signup or sign in again to request another verification email.'}
              </p>

              <div className="flex flex-col gap-3">
                <Button variant="primary" onClick={handleResend} disabled={isResending || !resendTicket}>
                  {isResending ? 'Sending another link...' : 'Resend verification email'}
                </Button>
                <Link href="/login" className="text-center text-sm" style={{ color: 'var(--nm-accent)' }}>
                  Return to sign in
                </Link>
                {!resendTicket && (
                  <Link href="/signup" className="text-center text-sm" style={{ color: 'var(--nm-accent)' }}>
                    Start a new signup
                  </Link>
                )}
              </div>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}

export default function VerifyEmailCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="auth-neumorphic min-h-screen flex items-center justify-center">
          <NeumorphicLoader />
        </div>
      }
    >
      <VerifyEmailCallbackPageContent />
    </Suspense>
  );
}
