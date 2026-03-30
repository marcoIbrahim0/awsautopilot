'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'motion/react';
import { useAuth } from '@/contexts/AuthContext';
import { AuthFormField } from '@/components/auth';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ThemeToggle } from '@/components/ui';
import { AuroraBackground } from '@/components/ui/aurora-background';
import { startNavigationFeedback } from '@/lib/navigation-feedback';
import { forgotPassword, getErrorMessage, resendEmailVerification } from '@/lib/api';
import { NeumorphicLoader } from '@/components/ui/NeumorphicLoader';
import {
  deliverFirebaseVerificationEmail,
  loadPendingEmailVerificationState,
  savePendingEmailVerificationState,
} from '@/lib/verification-email';

function PasswordVisibilityIcon({ visible }: { visible: boolean }) {
  if (visible) {
    return (
      <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.8]">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l18 18" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.6 10.7a2 2 0 0 0 2.7 2.7" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.9 5.2A10.8 10.8 0 0 1 12 5c5.2 0 9.3 4.1 10 7-.3 1.1-1.1 2.5-2.3 3.8" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M14.1 18.8c-.7.1-1.4.2-2.1.2-5.2 0-9.3-4.1-10-7 .2-.9.8-2 1.7-3.1" />
      </svg>
    );
  }

  return (
    <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.8]">
      <path strokeLinecap="round" strokeLinejoin="round" d="M2 12c.7-2.9 4.8-7 10-7s9.3 4.1 10 7c-.7 2.9-4.8 7-10 7S2.7 14.9 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, completeMfaLogin, isLoading: authLoading } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verificationBanner, setVerificationBanner] = useState<{
    tone: 'info' | 'error' | 'success';
    message: string;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isResendingVerification, setIsResendingVerification] = useState(false);
  const [showMfaModal, setShowMfaModal] = useState(false);
  const [mfaCode, setMfaCode] = useState('');
  const [mfaTicket, setMfaTicket] = useState<string | null>(null);
  const [mfaMethod, setMfaMethod] = useState<'email' | 'phone' | null>(null);
  const [mfaDestinationHint, setMfaDestinationHint] = useState<string>('');
  const [isVerifyingMfa, setIsVerifyingMfa] = useState(false);
  const [isResendingMfa, setIsResendingMfa] = useState(false);
  const [mfaError, setMfaError] = useState<string | null>(null);

  // Forgot password state
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [isSendingForgot, setIsSendingForgot] = useState(false);
  const [forgotError, setForgotError] = useState<string | null>(null);
  const [forgotSuccess, setForgotSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get('verified') !== '1') return;
    setVerificationBanner({
      tone: 'success',
      message: 'Email verified. Sign in to continue.',
    });
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setVerificationBanner(null);
    setIsLoading(true);
    try {
      const result = await login(email, password, rememberMe);
      if (result.mfaRequired) {
        setMfaTicket(result.mfaTicket ?? null);
        setMfaMethod(result.mfaMethod ?? null);
        setMfaDestinationHint(result.destinationHint ?? '');
        setMfaCode('');
        setMfaError(null);
        setShowMfaModal(true);
        return;
      }
      startNavigationFeedback();
      router.push('/');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      if (message === 'email_verification_required') {
        const verificationError = err as Error & { email?: string; resendTicket?: string };
        if (verificationError.email && verificationError.resendTicket) {
          savePendingEmailVerificationState({
            email: verificationError.email,
            resend_ticket: verificationError.resendTicket,
          });
        }
        setVerificationBanner({
          tone: 'info',
          message: 'Verify your email before signing in.',
        });
      } else if (message === 'email_verification_check_unavailable') {
        setVerificationBanner({
          tone: 'error',
          message: 'Verification service temporarily unavailable. Please try again shortly.',
        });
      } else {
        setError(message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendVerification = async () => {
    const pendingState = loadPendingEmailVerificationState();
    if (!pendingState?.resend_ticket) {
      setVerificationBanner({
        tone: 'error',
        message: 'Sign in again to request another verification email.',
      });
      return;
    }

    setIsResendingVerification(true);
    try {
      const response = await resendEmailVerification({ resend_ticket: pendingState.resend_ticket });
      savePendingEmailVerificationState({
        email: pendingState.email,
        resend_ticket: response.resend_ticket,
      });
      await deliverFirebaseVerificationEmail(response.firebase_delivery);
      setVerificationBanner({
        tone: 'info',
        message: response.message || 'We sent a fresh verification email.',
      });
    } catch (err) {
      setVerificationBanner({
        tone: 'error',
        message: getErrorMessage(err),
      });
    } finally {
      setIsResendingVerification(false);
    }
  };

  const handleVerifyMfa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mfaTicket) {
      setMfaError('MFA session expired. Sign in again.');
      return;
    }
    setMfaError(null);
    setIsVerifyingMfa(true);
    try {
      await completeMfaLogin(mfaTicket, mfaCode.trim(), rememberMe);
      setShowMfaModal(false);
      startNavigationFeedback();
      router.push('/');
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : 'MFA verification failed');
    } finally {
      setIsVerifyingMfa(false);
    }
  };

  const handleResendMfa = async () => {
    if (!email || !password) {
      setMfaError('Enter your email and password again to resend the code.');
      return;
    }
    setMfaError(null);
    setIsResendingMfa(true);
    try {
      const result = await login(email, password, rememberMe);
      if (!result.mfaRequired || !result.mfaTicket) {
        setShowMfaModal(false);
        startNavigationFeedback();
        router.push('/');
        return;
      }
      setMfaTicket(result.mfaTicket);
      setMfaMethod(result.mfaMethod ?? null);
      setMfaDestinationHint(result.destinationHint ?? '');
      setMfaCode('');
    } catch (err) {
      setMfaError(err instanceof Error ? err.message : 'Unable to resend MFA code');
    } finally {
      setIsResendingMfa(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!forgotEmail) return;

    setForgotError(null);
    setForgotSuccess(null);
    setIsSendingForgot(true);

    try {
      await forgotPassword({ email: forgotEmail });
      setForgotSuccess('If an account exists, a reset link was sent.');
    } catch (err) {
      setForgotError(getErrorMessage(err));
    } finally {
      setIsSendingForgot(false);
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
    <div className="min-h-screen flex">
      {/* Left: Aurora Dark Panel */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden text-white">
        <AuroraBackground className="min-h-full w-full" showRadialGradient dark>
          <div className="relative z-10 flex h-full w-full flex-col justify-center px-12 xl:px-16">
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <h1 className="text-3xl xl:text-4xl font-bold">Welcome back</h1>
              <p className="mt-4 text-lg text-white/90 max-w-md">
                We empower developers and technical teams to create, simulate, and manage
                AWS security workflows—findings, actions, and evidence—in one place.
              </p>
            </motion.div>
            <motion.div
              className="mt-12 p-6 rounded-2xl bg-white/10 backdrop-blur border border-white/20 max-w-md"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.1 }}
            >
              <p className="text-sm text-white/80 italic">
                &ldquo;What used to take hours every week is now fully automated.&rdquo;
              </p>
              <p className="mt-2 text-sm font-medium">— Security & DevOps teams</p>
            </motion.div>
          </div>
        </AuroraBackground>
      </div>

      {/* Right: Neumorphic Form Card */}
      <div className="auth-neumorphic relative w-full lg:w-1/2 flex items-center justify-center p-6 sm:p-10">

        {/* Theme Toggle in Top Right */}
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
            <h2 className="text-2xl font-bold" style={{ color: 'var(--nm-text)' }}>Sign in to your account</h2>
            <p className="mt-1 text-sm" style={{ color: 'var(--nm-text-muted)' }}>AWS Security Autopilot</p>
          </div>

          <div className="nm-raised-lg p-6 sm:p-8">
            <form onSubmit={handleSubmit} className="space-y-5">
              {verificationBanner && (
                <div
                  className={`rounded-xl border p-3 ${
                    verificationBanner.tone === 'error'
                      ? 'border-red-500/20 bg-red-500/10'
                      : verificationBanner.tone === 'success'
                        ? 'border-emerald-500/20 bg-emerald-500/10'
                        : 'border-sky-500/20 bg-sky-500/10'
                  }`}
                >
                  <p
                    className={`text-sm ${
                      verificationBanner.tone === 'error'
                        ? 'text-red-600'
                        : verificationBanner.tone === 'success'
                          ? 'text-emerald-700'
                          : 'text-sky-700'
                    }`}
                  >
                    {verificationBanner.message}
                  </p>
                  {verificationBanner.tone !== 'success' && (
                    <button
                      type="button"
                      onClick={handleResendVerification}
                      disabled={isResendingVerification}
                      className="mt-2 text-sm font-medium transition-colors duration-200"
                      style={{ color: 'var(--nm-accent)' }}
                    >
                      {isResendingVerification ? 'Sending verification email...' : 'Resend verification email'}
                    </button>
                  )}
                </div>
              )}
              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
                  <p className="text-sm text-red-600">{error}</p>
                </div>
              )}
              <AuthFormField
                id="email"
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoComplete="email"
              />
              <AuthFormField
                id="password"
                label="Password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                autoComplete="current-password"
                endAdornment={(
                  <button
                    type="button"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    aria-pressed={showPassword}
                    onClick={() => setShowPassword((value) => !value)}
                    className="rounded-md p-1 transition-colors duration-150 hover:bg-black/5"
                    style={{ color: 'var(--nm-text-muted)' }}
                  >
                    <PasswordVisibilityIcon visible={showPassword} />
                  </button>
                )}
              />
              <div className="flex items-center justify-between -mt-2 mb-2 gap-3">
                <label className="flex items-center gap-2 text-sm" style={{ color: 'var(--nm-text-muted)' }}>
                  <input
                    id="rememberMe"
                    name="rememberMe"
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    className="h-4 w-4 rounded border border-border bg-bg accent-[var(--nm-accent)]"
                  />
                  <span>Remember me</span>
                </label>
                <button
                  type="button"
                  onClick={() => setShowForgotModal(true)}
                  className="text-xs font-medium transition-colors duration-200"
                  style={{ color: 'var(--nm-accent)' }}
                >
                  Forgot password?
                </button>
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="nm-btn-primary w-full py-3"
              >
                {isLoading ? 'Signing in...' : 'Sign in'}
              </button>
            </form>
          </div>

          <p className="mt-6 text-center text-sm" style={{ color: 'var(--nm-text-muted)' }}>
            Don&apos;t have an account?{' '}
            <Link href="/signup" className="font-medium transition-colors duration-200" style={{ color: 'var(--nm-accent)' }}>
              Sign up
            </Link>
          </p>
        </motion.div>
      </div>

      <Modal
        isOpen={showForgotModal}
        onClose={() => {
          setShowForgotModal(false);
          setForgotError(null);
          setForgotSuccess(null);
          setForgotEmail('');
        }}
        title="Reset Password"
      >
        <form onSubmit={handleForgotPassword} className="space-y-4">
          <p className="text-sm text-muted">
            Enter your email address and we&apos;ll send you a link to reset your password.
          </p>

          {forgotError && (
            <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl">
              <p className="text-sm text-danger">{forgotError}</p>
            </div>
          )}
          {forgotSuccess && (
            <div className="p-3 bg-success/10 border border-success/20 rounded-xl">
              <p className="text-sm text-success">{forgotSuccess}</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-text mb-1">
              Email Address
            </label>
            <input
              type="email"
              className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-text focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent transition-all"
              value={forgotEmail}
              onChange={(e) => setForgotEmail(e.target.value)}
              placeholder="you@company.com"
              required
            />
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowForgotModal(false);
                setForgotError(null);
                setForgotSuccess(null);
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={isSendingForgot || !forgotEmail}
            >
              {isSendingForgot ? 'Sending...' : 'Send Reset Link'}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={showMfaModal}
        onClose={() => {
          if (isVerifyingMfa) return;
          setShowMfaModal(false);
          setMfaCode('');
          setMfaError(null);
        }}
        title="Multi-factor Authentication"
      >
        <form onSubmit={handleVerifyMfa} className="space-y-4">
          <p className="text-sm text-muted">
            Enter the 6-digit code sent to your {mfaMethod === 'phone' ? 'phone' : 'email'}{mfaDestinationHint ? ` (${mfaDestinationHint})` : ''}.
          </p>

          {mfaError && (
            <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl">
              <p className="text-sm text-danger">{mfaError}</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-text mb-1">Verification Code</label>
            <input
              type="text"
              className="w-full bg-bg border border-border rounded-xl px-4 py-2.5 text-text text-center font-mono tracking-[0.35em] focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent transition-all"
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
            />
          </div>

          <div className="flex justify-between gap-3 pt-2">
            <Button
              type="button"
              variant="secondary"
              onClick={handleResendMfa}
              disabled={isResendingMfa || isVerifyingMfa}
            >
              {isResendingMfa ? 'Resending...' : 'Resend Code'}
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={isVerifyingMfa || mfaCode.length !== 6}
            >
              {isVerifyingMfa ? 'Verifying...' : 'Verify & Sign In'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="auth-neumorphic min-h-screen flex items-center justify-center">
          <NeumorphicLoader />
        </div>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}
