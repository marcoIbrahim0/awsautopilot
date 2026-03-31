'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'motion/react';
import { useAuth } from '@/contexts/AuthContext';
import { AuthFormField } from '@/components/auth';
import { ThemeToggle } from '@/components/ui';
import { NeumorphicLoader } from '@/components/ui/NeumorphicLoader';
import { startNavigationFeedback } from '@/lib/navigation-feedback';
import { savePendingEmailVerificationState } from '@/lib/verification-email';

export default function SignupPage() {
  const router = useRouter();
  const { signup, isAuthenticated, isLoading: authLoading } = useAuth();

  const [companyName, setCompanyName] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    router.replace('/');
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    setIsLoading(true);
    try {
      const result = await signup(companyName, name, email, password);
      if ('resend_ticket' in result && result.firebase_delivery) {
        savePendingEmailVerificationState({
          email: result.email,
          resend_ticket: result.resend_ticket,
          firebase_delivery: result.firebase_delivery,
        });
      }
      startNavigationFeedback();
      router.push(`/verify-email/pending?email=${encodeURIComponent(result.email)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed');
    } finally {
      setIsLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="auth-neumorphic min-h-screen flex items-center justify-center">
        <NeumorphicLoader />
      </div>
    );
  }

  if (isAuthenticated) {
    return null;
  }

  return (
    <div className="auth-neumorphic relative min-h-screen flex items-center justify-center p-6 sm:p-10">

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
          <h2 className="text-2xl font-bold" style={{ color: 'var(--nm-text)' }}>Sign up for an account</h2>
          <p className="mt-1 text-sm" style={{ color: 'var(--nm-text-muted)' }}>Get started with AWS Security Autopilot</p>
        </div>

        <div className="nm-raised-lg p-6 sm:p-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}
            <AuthFormField
              id="companyName"
              label="Company name"
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Acme Inc."
              required
            />
            <AuthFormField
              id="name"
              label="Full name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Doe"
              required
              autoComplete="name"
            />
            <AuthFormField
              id="email"
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@acme.com"
              required
              autoComplete="email"
            />
            <AuthFormField
              id="password"
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              required
              autoComplete="new-password"
              minLength={8}
            />
            <AuthFormField
              id="confirmPassword"
              label="Confirm password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm your password"
              required
              autoComplete="new-password"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="nm-btn-primary w-full py-3"
            >
              {isLoading ? 'Creating account...' : 'Sign Up'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm" style={{ color: 'var(--nm-text-muted)' }}>
            Already have an account?{' '}
            <Link href="/login" className="font-medium transition-colors duration-200" style={{ color: 'var(--nm-accent)' }}>
              Sign in
            </Link>
          </p>

          <p className="mt-6 text-center text-xs max-w-sm mx-auto" style={{ color: 'var(--nm-text-muted)' }}>
            By clicking Sign Up, you agree to our{' '}
            <Link href="/legal/terms" className="underline hover:opacity-80 transition-opacity">
              Terms of Service
            </Link>{' '}
            and{' '}
            <Link href="/legal/privacy" className="underline hover:opacity-80 transition-opacity">
              Privacy Policy
            </Link>
            , and acknowledge our{' '}
            <Link href="/legal/cookies" className="underline hover:opacity-80 transition-opacity">
              Cookie Policy
            </Link>
            .
          </p>
        </div>
      </motion.div>
    </div>
  );
}
