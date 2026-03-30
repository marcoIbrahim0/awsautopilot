'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { remediationInsetClass } from '@/components/ui/remediation-surface';
import { useAuth, type AuthUser } from '@/contexts/AuthContext';
import {
    updateMe,
    sendVerification,
    confirmVerification,
    getMfaSettings,
    patchMfaSettings,
    type MfaSettingsResponse,
    changePassword,
    forgotPassword,
    deleteMe,
    getErrorMessage,
} from '@/lib/api';

export function ProfileTab() {
    const { user, mutateUser } = useAuth();
    const isAdmin = user?.role === 'admin';

    const [formData, setFormData] = useState({
        name: '',
        phone_number: '',
    });

    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [mfaSettings, setMfaSettings] = useState<MfaSettingsResponse | null>(null);
    const [mfaMethodChoice, setMfaMethodChoice] = useState<'email' | 'phone'>('email');
    const [isSavingMfa, setIsSavingMfa] = useState(false);
    const [mfaError, setMfaError] = useState<string | null>(null);
    const [mfaSuccess, setMfaSuccess] = useState<string | null>(null);

    // Verification state
    const [showVerifyModal, setShowVerifyModal] = useState(false);
    const [verifyType, setVerifyType] = useState<'email' | 'phone'>('email');
    const [verifyCode, setVerifyCode] = useState('');
    const [isSendingCode, setIsSendingCode] = useState(false);
    const [isVerifying, setIsVerifying] = useState(false);
    const [verifyError, setVerifyError] = useState<string | null>(null);
    const [verifySuccess, setVerifySuccess] = useState<string | null>(null);

    // Password state
    const [showPasswordModal, setShowPasswordModal] = useState(false);
    const [passwordData, setPasswordData] = useState({ old_password: '', new_password: '', confirm_password: '' });
    const [isPasswordSaving, setIsPasswordSaving] = useState(false);
    const [passwordError, setPasswordError] = useState<string | null>(null);
    const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
    const [forgotPasswordEmailSent, setForgotPasswordEmailSent] = useState(false);

    // Delete account state
    const [showDeleteModal, setShowDeleteModal] = useState(false);
    const [deleteConfirmText, setDeleteConfirmText] = useState('');
    const [isDeleting, setIsDeleting] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);

    // Initialize form
    useEffect(() => {
        if (user) {
            setFormData({
                name: user.name || '',
                phone_number: user.phone_number || '',
            });
        }
    }, [user]);

    useEffect(() => {
        let cancelled = false;
        const loadMfaSettings = async () => {
            if (!user) return;
            try {
                const settings = await getMfaSettings();
                if (cancelled) return;
                setMfaSettings(settings);
                setMfaMethodChoice(settings.mfa_method === 'phone' ? 'phone' : 'email');
            } catch {
                if (cancelled) return;
                setMfaSettings({
                    mfa_enabled: Boolean(user.mfa_enabled),
                    mfa_method: (user.mfa_method as 'email' | 'phone' | null) ?? null,
                    email_verified: Boolean(user.email_verified),
                    phone_verified: Boolean(user.phone_verified),
                    phone_number: user.phone_number ?? null,
                });
            }
        };
        void loadMfaSettings();
        return () => {
            cancelled = true;
        };
    }, [user]);

    // Clear success messages after a few seconds
    useEffect(() => {
        if (success) {
            const t = setTimeout(() => setSuccess(null), 4000);
            return () => clearTimeout(t);
        }
    }, [success]);

    const handleSaveProfile = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSaving(true);
        setError(null);
        setSuccess(null);

        try {
            const res = await updateMe({
                name: formData.name.trim() || undefined,
                phone_number: formData.phone_number.trim() || undefined,
            });
            // Update global context with the fresh user data
            if (mutateUser) {
                mutateUser(res.user as unknown as AuthUser);
            }
            setMfaSettings((prev) => prev ? {
                ...prev,
                phone_number: res.user.phone_number ?? prev.phone_number,
                phone_verified: Boolean(res.user.phone_verified),
                email_verified: Boolean(res.user.email_verified),
                mfa_enabled: Boolean(res.user.mfa_enabled ?? prev.mfa_enabled),
                mfa_method: (res.user.mfa_method as 'email' | 'phone' | null | undefined) ?? prev.mfa_method,
            } : prev);
            setSuccess('Profile updated successfully.');
        } catch (err) {
            setError(getErrorMessage(err));
        } finally {
            setIsSaving(false);
        }
    };

    const currentEmailVerified = user?.email_verified ?? false;
    const currentPhoneVerified = user?.phone_verified ?? false;
    const currentPhone = user?.phone_number ?? '';

    const handleSendCode = async (type: 'email' | 'phone') => {
        setVerifyType(type);
        setIsSendingCode(true);
        setError(null);
        setVerifyError(null);
        setVerifySuccess(null);
        setVerifyCode('');

        try {
            if (type === 'email') {
                setError('Email verification resend is available only during signup or after a sign-in attempt.');
                setShowVerifyModal(false);
                return;
            }
            setShowVerifyModal(true);
            const response = await sendVerification({ verification_type: type });
            setVerifySuccess(response.message);
        } catch (err) {
            if (type === 'email') {
                setError(getErrorMessage(err));
            } else {
                setVerifyError(getErrorMessage(err));
            }
        } finally {
            setIsSendingCode(false);
        }
    };

    const handleVerifyCode = async (e: React.FormEvent) => {
        e.preventDefault();
        if (verifyCode.length !== 6) {
            setVerifyError('Code must be exactly 6 digits.');
            return;
        }
        setIsVerifying(true);
        setVerifyError(null);
        setVerifySuccess(null);

        try {
            await confirmVerification({
                verification_type: verifyType,
                code: verifyCode,
            });
            setShowVerifyModal(false);

            // Update local context
            if (user && mutateUser) {
                mutateUser({
                    ...user,
                    email_verified: verifyType === 'email' ? true : user.email_verified,
                    phone_verified: verifyType === 'phone' ? true : user.phone_verified,
                });
            }
            setMfaSettings((prev) => prev ? {
                ...prev,
                email_verified: verifyType === 'email' ? true : prev.email_verified,
                phone_verified: verifyType === 'phone' ? true : prev.phone_verified,
                phone_number: formData.phone_number || prev.phone_number,
            } : prev);
            setSuccess(`${verifyType === 'email' ? 'Email' : 'Phone'} verified successfully.`);
        } catch (err) {
            setVerifyError(getErrorMessage(err));
        } finally {
            setIsVerifying(false);
        }
    };

    const handleToggleMfa = async (enable: boolean) => {
        setMfaError(null);
        setMfaSuccess(null);
        setIsSavingMfa(true);
        try {
            const updated = await patchMfaSettings({
                mfa_enabled: enable,
                ...(enable ? { mfa_method: mfaMethodChoice } : {}),
            });
            setMfaSettings(updated);
            if (mutateUser) {
                mutateUser({
                    mfa_enabled: updated.mfa_enabled,
                    mfa_method: updated.mfa_method,
                    email_verified: updated.email_verified,
                    phone_verified: updated.phone_verified,
                    phone_number: updated.phone_number,
                });
            }
            setMfaSuccess(enable ? `MFA enabled (${updated.mfa_method || mfaMethodChoice}).` : 'MFA disabled.');
        } catch (err) {
            setMfaError(getErrorMessage(err));
        } finally {
            setIsSavingMfa(false);
        }
    };

    const handleUpdatePassword = async (e: React.FormEvent) => {
        e.preventDefault();
        setPasswordError(null);
        setPasswordSuccess(null);

        if (passwordData.new_password !== passwordData.confirm_password) {
            setPasswordError('New passwords do not match.');
            return;
        }

        if (passwordData.new_password.length < 8) {
            setPasswordError('Password must be at least 8 characters long.');
            return;
        }

        setIsPasswordSaving(true);

        try {
            await changePassword({
                old_password: passwordData.old_password,
                new_password: passwordData.new_password,
            });
            setPasswordSuccess('Password updated successfully.');
            setPasswordData({ old_password: '', new_password: '', confirm_password: '' });
            setTimeout(() => {
                setShowPasswordModal(false);
                setPasswordSuccess(null);
            }, 2000);
        } catch (err) {
            setPasswordError(getErrorMessage(err));
        } finally {
            setIsPasswordSaving(false);
        }
    };

    const handleForgotPassword = async () => {
        if (!user?.email) return;
        try {
            await forgotPassword({ email: user.email });
            setForgotPasswordEmailSent(true);
            setTimeout(() => setForgotPasswordEmailSent(false), 5000);
        } catch (err) {
            setPasswordError(getErrorMessage(err));
        }
    };

    const handleDeleteAccount = async () => {
        if (deleteConfirmText !== 'DELETE') return;
        setIsDeleting(true);
        setDeleteError(null);

        try {
            await deleteMe();
            // On success, redirect to login page
            window.location.href = '/login?deleted=true';
        } catch (err) {
            setDeleteError(getErrorMessage(err));
            setIsDeleting(false);
        }
    };

    return (
        <div className="space-y-8">
            {/* PROFILE SECTION */}
            <div>
                <div>
                    <h2 className="text-lg font-semibold text-text">Profile Info</h2>
                    <p className="text-sm text-muted">Update your personal details and contact info.</p>
                </div>

                <form onSubmit={handleSaveProfile} className={remediationInsetClass('default', 'mt-4 space-y-4 p-6')}>
                    {error && (
                        <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl">
                            <p className="text-sm text-danger">{error}</p>
                        </div>
                    )}
                    {success && (
                        <div className="p-3 bg-success/10 border border-success/20 rounded-xl">
                            <p className="text-sm text-success">{success}</p>
                        </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-text mb-1">
                                Full Name
                            </label>
                            <Input
                                value={formData.name}
                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                placeholder="e.g. Jane Doe"
                                maxLength={255}
                                required
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-text mb-1">
                                Role
                            </label>
                            <Input
                                value={user?.role || ''}
                                disabled
                                className="bg-bg text-muted cursor-not-allowed uppercase text-xs font-semibold"
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-2">
                        <div>
                            <div className="flex justify-between items-center mb-1">
                                <label className="block text-sm font-medium text-text">
                                    Email Address
                                </label>
                                {currentEmailVerified ? (
                                    <Badge variant="success">Verified</Badge>
                                ) : (
                                    <button
                                        type="button"
                                        onClick={() => handleSendCode('email')}
                                        className="text-xs text-accent hover:underline font-medium"
                                    >
                                        Resend Link
                                    </button>
                                )}
                            </div>
                            <Input
                                value={user?.email || ''}
                                disabled
                                className="bg-bg text-muted cursor-not-allowed"
                            />
                            <p className="text-xs text-muted mt-1">
                                Your email address is managed by your organization and cannot be changed here. Email verification is handled by the secure link sent to your inbox.
                            </p>
                        </div>
                        <div>
                            <div className="flex justify-between items-center mb-1">
                                <label className="block text-sm font-medium text-text">
                                    Phone Number (optional)
                                </label>
                                {currentPhone && (
                                    currentPhoneVerified ? (
                                        <Badge variant="success">Verified</Badge>
                                    ) : (
                                        <button
                                            type="button"
                                            onClick={() => handleSendCode('phone')}
                                            className="text-xs text-accent hover:underline font-medium"
                                        >
                                            Verify Now
                                        </button>
                                    )
                                )}
                            </div>
                            <Input
                                value={formData.phone_number}
                                onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                                placeholder="+1234567890"
                                maxLength={20}
                            />
                            <p className="text-xs text-muted mt-1">
                                Include country code (e.g., +1 for US). Keep this verified to receive OTPs via SMS.
                            </p>
                        </div>
                    </div>

                    <div className="flex justify-end pt-4">
                        <Button type="submit" variant="primary" disabled={isSaving}>
                            {isSaving ? 'Saving...' : 'Save Profile'}
                        </Button>
                    </div>
                </form>
            </div>

            {/* SECURITY SECTION */}
            <div>
                <h2 className="text-lg font-semibold text-text">Security</h2>
                <p className="text-sm text-muted">Update your password to keep your account secure.</p>
                <div className={remediationInsetClass('default', 'mt-4 flex items-center justify-between p-6')}>
                    <div>
                        <h3 className="text-base font-semibold text-text">Password</h3>
                        <p className="text-sm text-muted hidden md:block">A secure password helps protect your AWS environments.</p>
                    </div>
                    <Button variant="secondary" onClick={() => setShowPasswordModal(true)}>Change Password</Button>
                </div>
                <div className={remediationInsetClass('default', 'mt-4 space-y-4 p-6')}>
                    <div className="flex items-center justify-between gap-3">
                        <div>
                            <h3 className="text-base font-semibold text-text">Multi-factor authentication</h3>
                            <p className="text-sm text-muted">Require a one-time code after password sign-in.</p>
                        </div>
                        <Badge variant={mfaSettings?.mfa_enabled ? 'success' : 'info'}>
                            {mfaSettings?.mfa_enabled ? `Enabled (${mfaSettings.mfa_method || 'email'})` : 'Disabled'}
                        </Badge>
                    </div>

                    {mfaError && (
                        <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl">
                            <p className="text-sm text-danger">{mfaError}</p>
                        </div>
                    )}
                    {mfaSuccess && (
                        <div className="p-3 bg-success/10 border border-success/20 rounded-xl">
                            <p className="text-sm text-success">{mfaSuccess}</p>
                        </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <label className="text-sm font-medium text-text">
                            Preferred factor
                            <select
                                value={mfaMethodChoice}
                                onChange={(e) => setMfaMethodChoice((e.target.value === 'phone' ? 'phone' : 'email'))}
                                disabled={Boolean(mfaSettings?.mfa_enabled) || isSavingMfa}
                                className="mt-1 w-full rounded-2xl border border-border bg-[var(--control-bg)] px-4 py-3 text-sm text-text"
                            >
                                <option value="email">Email code</option>
                                <option value="phone">Phone code</option>
                            </select>
                        </label>
                        <div className="text-xs text-muted flex items-end">
                            Email must be verified for email MFA. Phone MFA additionally requires a verified phone number.
                        </div>
                    </div>

                    <div className="flex justify-end gap-2">
                        {mfaSettings?.mfa_enabled ? (
                            <Button
                                variant="secondary"
                                onClick={() => handleToggleMfa(false)}
                                disabled={isSavingMfa}
                            >
                                {isSavingMfa ? 'Updating...' : 'Disable MFA'}
                            </Button>
                        ) : (
                            <Button
                                variant="primary"
                                onClick={() => handleToggleMfa(true)}
                                disabled={isSavingMfa}
                            >
                                {isSavingMfa ? 'Enabling...' : 'Enable MFA'}
                            </Button>
                        )}
                    </div>
                </div>
            </div>

            {/* DANGER ZONE SECTION */}
            <div>
                <h2 className="text-lg font-semibold text-danger">Danger Zone</h2>
                <p className="text-sm text-muted">Irreversible actions for your account.</p>
                <div className={remediationInsetClass('danger', 'mt-4 flex items-center justify-between p-6')}>
                    <div>
                        <h3 className="text-base font-semibold text-text">Delete Account</h3>
                        <p className="text-sm text-muted hidden md:block">
                            Permanently delete your account and remove your access. Accounts are soft-deleted and can be recovered within a 30-day grace period.
                        </p>
                    </div>
                    <Button variant="danger" onClick={() => setShowDeleteModal(true)}>Delete Account</Button>
                </div>
            </div>


            {/* Verification Modal */}
            <Modal
                isOpen={showVerifyModal}
                onClose={() => setShowVerifyModal(false)}
                title={`Verify ${verifyType === 'email' ? 'Email' : 'Phone'}`}
            >
                <form onSubmit={handleVerifyCode} className="space-y-4">
                    <p className="text-sm text-muted">
                        {isSendingCode
                            ? 'Sending code...'
                            : `Enter the 6-digit code we sent to your ${verifyType === 'email' ? 'email' : 'phone number'}.`}
                    </p>

                    {verifyError && (
                        <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl">
                            <p className="text-sm text-danger">{verifyError}</p>
                        </div>
                    )}
                    {verifySuccess && !verifyError && (
                        <div className="p-3 bg-success/10 border border-success/20 rounded-xl">
                            <p className="text-sm text-success">{verifySuccess}</p>
                        </div>
                    )}

                    <div>
                        <Input
                            value={verifyCode}
                            onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                            disabled={isSendingCode || isVerifying}
                            placeholder="000000"
                            className="text-center font-mono text-lg tracking-[0.5em]"
                            maxLength={6}
                        />
                    </div>

                    <div className="flex justify-between items-center pt-2">
                        <button
                            type="button"
                            onClick={() => handleSendCode(verifyType)}
                            disabled={isSendingCode || isVerifying}
                            className="text-sm text-accent hover:underline disabled:opacity-50"
                        >
                            Resend Code
                        </button>
                        <div className="flex gap-2">
                            <Button type="button" variant="secondary" onClick={() => setShowVerifyModal(false)}>
                                Cancel
                            </Button>
                            <Button type="submit" variant="primary" disabled={isSendingCode || isVerifying || verifyCode.length !== 6}>
                                {isVerifying ? 'Verifying...' : 'Verify'}
                            </Button>
                        </div>
                    </div>
                </form>
            </Modal>

            {/* Change Password Modal */}
            <Modal
                isOpen={showPasswordModal}
                onClose={() => {
                    setShowPasswordModal(false);
                    setPasswordError(null);
                    setPasswordSuccess(null);
                    setPasswordData({ old_password: '', new_password: '', confirm_password: '' });
                }}
                title="Change Password"
            >
                <form onSubmit={handleUpdatePassword} className="space-y-4">
                    {passwordError && (
                        <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl">
                            <p className="text-sm text-danger">{passwordError}</p>
                        </div>
                    )}
                    {passwordSuccess && (
                        <div className="p-3 bg-success/10 border border-success/20 rounded-xl">
                            <p className="text-sm text-success">{passwordSuccess}</p>
                        </div>
                    )}
                    {forgotPasswordEmailSent && (
                        <div className="p-3 bg-success/10 border border-success/20 rounded-xl">
                            <p className="text-sm text-success">A password reset link has been sent to your email.</p>
                        </div>
                    )}

                    <div className="space-y-3">
                        <div>
                            <div className="flex justify-between items-center mb-1">
                                <label className="block text-sm font-medium text-text">Current Password</label>
                                <button
                                    type="button"
                                    onClick={handleForgotPassword}
                                    className="text-xs text-accent hover:underline font-medium"
                                >
                                    Forgot Password?
                                </button>
                            </div>
                            <Input
                                type="password"
                                value={passwordData.old_password}
                                onChange={(e) => setPasswordData({ ...passwordData, old_password: e.target.value })}
                                required
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-text mb-1">New Password</label>
                            <Input
                                type="password"
                                value={passwordData.new_password}
                                onChange={(e) => setPasswordData({ ...passwordData, new_password: e.target.value })}
                                minLength={8}
                                required
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-text mb-1">Confirm New Password</label>
                            <Input
                                type="password"
                                value={passwordData.confirm_password}
                                onChange={(e) => setPasswordData({ ...passwordData, confirm_password: e.target.value })}
                                minLength={8}
                                required
                            />
                        </div>
                    </div>

                    <div className="flex justify-end gap-3 pt-4">
                        <Button type="button" variant="secondary" onClick={() => setShowPasswordModal(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" variant="primary" disabled={isPasswordSaving || !passwordData.old_password || !passwordData.new_password || !passwordData.confirm_password}>
                            {isPasswordSaving ? 'Updating...' : 'Update Password'}
                        </Button>
                    </div>
                </form>
            </Modal>

            {/* Delete Account Modal */}
            <Modal
                isOpen={showDeleteModal}
                onClose={() => {
                    setShowDeleteModal(false);
                    setDeleteConfirmText('');
                    setDeleteError(null);
                }}
                title="Delete Account"
            >
                <div className="space-y-4">
                    <p className="text-sm text-muted">
                        Are you sure you want to delete your account <strong>({user?.email})</strong>?
                    </p>
                    <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl">
                        <p className="text-sm text-danger font-medium">
                            Warning: This action will schedule your account for deletion.
                            {isAdmin && ' If you are the sole admin, it will also disable all tenant data and access for other users.'}
                        </p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-text mb-1">
                            To confirm, type <strong>DELETE</strong> below:
                        </label>
                        <Input
                            value={deleteConfirmText}
                            onChange={(e) => setDeleteConfirmText(e.target.value)}
                            placeholder="DELETE"
                        />
                    </div>

                    {deleteError && (
                        <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl">
                            <p className="text-sm text-danger">{deleteError}</p>
                        </div>
                    )}

                    <div className="flex justify-end gap-3 pt-4">
                        <Button
                            variant="secondary"
                            onClick={() => {
                                setShowDeleteModal(false);
                                setDeleteConfirmText('');
                            }}
                            disabled={isDeleting}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="danger"
                            onClick={handleDeleteAccount}
                            disabled={isDeleting || deleteConfirmText !== 'DELETE'}
                        >
                            {isDeleting ? 'Deleting...' : 'Yes, Delete Account'}
                        </Button>
                    </div>
                </div>
            </Modal>
        </div>
    );
}
