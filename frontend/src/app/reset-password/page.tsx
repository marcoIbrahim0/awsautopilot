'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'motion/react';
import { AuthFormField } from '@/components/auth';
import { Button } from '@/components/ui/Button';
import { resetPassword } from '@/lib/api';
import { getErrorMessage } from '@/lib/api';

function ResetPasswordForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const token = searchParams.get('token');

    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (!token) {
            setError('Invalid or missing password reset token.');
        }
    }, [token]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!token) return;

        setError(null);
        setSuccess(null);

        if (password !== confirmPassword) {
            setError('Passwords do not match.');
            return;
        }

        if (password.length < 8) {
            setError('Password must be at least 8 characters long.');
            return;
        }

        setIsLoading(true);
        try {
            const res = await resetPassword({ token, new_password: password });
            setSuccess(res.message || 'Password has been successfully reset. Redirecting...');
            setTimeout(() => {
                router.push('/login');
            }, 3000);
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-bg flex items-center justify-center p-6 pb-24">
            <motion.div
                className="w-full max-w-md"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
            >
                <div className="text-center mb-8">
                    <Link href="/login" className="text-accent text-sm hover:underline mb-4 block">
                        &larr; Back to login
                    </Link>
                    <h2 className="text-2xl font-bold text-text">Reset Password</h2>
                    <p className="text-muted mt-1 text-sm">Enter your new password below.</p>
                </div>

                <div className="bg-surface border border-border rounded-2xl p-6 sm:p-8 shadow-sm">
                    {!token ? (
                        <div className="p-4 bg-danger/10 border border-danger/20 rounded-xl text-center">
                            <p className="text-sm text-danger">{error}</p>
                        </div>
                    ) : success ? (
                        <div className="p-6 bg-success/10 border border-success/20 rounded-xl text-center">
                            <p className="text-sm text-success font-medium">{success}</p>
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {error && (
                                <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl">
                                    <p className="text-sm text-danger">{error}</p>
                                </div>
                            )}
                            <AuthFormField
                                id="password"
                                label="New Password"
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                required
                                minLength={8}
                            />
                            <AuthFormField
                                id="confirmPassword"
                                label="Confirm New Password"
                                type="password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="••••••••"
                                required
                                minLength={8}
                            />
                            <Button
                                type="submit"
                                variant="primary"
                                className="w-full mt-2 inline-flex items-center justify-center gap-2 py-3 rounded-xl font-medium"
                                disabled={isLoading}
                                isLoading={isLoading}
                            >
                                {isLoading ? 'Resetting...' : 'Reset Password'}
                            </Button>
                        </form>
                    )}
                </div>
            </motion.div>
        </div>
    );
}

export default function ResetPasswordPage() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-bg flex items-center justify-center">
                <div className="animate-pulse text-muted">Loading...</div>
            </div>
        }>
            <ResetPasswordForm />
        </Suspense>
    );
}
