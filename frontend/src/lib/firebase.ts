'use client';

import { FirebaseApp, getApp, getApps, initializeApp } from 'firebase/app';
import { Auth, getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? '',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? '',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? '',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? '',
};

function hasFirebaseConfig(): boolean {
  return Object.values(firebaseConfig).every((value) => Boolean(value.trim()));
}

function getFirebaseApp(): FirebaseApp {
  if (!hasFirebaseConfig()) {
    throw new Error('Firebase client configuration is missing.');
  }
  return getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
}

export const firebaseConfigured = hasFirebaseConfig();
export const auth: Auth | null = firebaseConfigured ? getAuth(getFirebaseApp()) : null;

export function getFirebaseAuth(): Auth {
  if (!auth) {
    throw new Error('Firebase client configuration is missing.');
  }
  return auth;
}
