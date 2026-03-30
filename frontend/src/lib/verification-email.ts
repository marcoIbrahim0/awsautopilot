'use client';

import { sendEmailVerification, signInWithCustomToken, signOut } from 'firebase/auth';

import { getFirebaseAuth } from '@/lib/firebase';

const STORAGE_KEY = 'pending_email_verification';

export interface FirebaseVerificationDelivery {
  custom_token: string;
  continue_url: string;
}

export interface PendingEmailVerificationState {
  email: string;
  resend_ticket: string;
  firebase_delivery?: FirebaseVerificationDelivery | null;
}

export function loadPendingEmailVerificationState(): PendingEmailVerificationState | null {
  if (typeof window === 'undefined') return null;
  const raw = window.sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PendingEmailVerificationState;
  } catch {
    window.sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function savePendingEmailVerificationState(state: PendingEmailVerificationState): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function clearPendingEmailVerificationState(): void {
  if (typeof window === 'undefined') return;
  window.sessionStorage.removeItem(STORAGE_KEY);
}

export async function deliverFirebaseVerificationEmail(
  delivery: FirebaseVerificationDelivery
): Promise<void> {
  const auth = getFirebaseAuth();
  try {
    await signInWithCustomToken(auth, delivery.custom_token);
    if (!auth.currentUser) {
      throw new Error('Firebase sign-in did not return a user.');
    }
    await sendEmailVerification(auth.currentUser, {
      url: delivery.continue_url,
      handleCodeInApp: true,
    });
  } finally {
    await signOut(auth).catch(() => undefined);
  }
}
