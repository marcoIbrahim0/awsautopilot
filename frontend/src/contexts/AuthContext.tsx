'use client';

import { createContext, useContext, useEffect, useState, useCallback, useRef, ReactNode } from 'react';
import { getApiBaseUrl } from '@/lib/api-base-url';
import {
  buildCloudFormationLaunchStackUrl,
  extractTemplateUrlFromLaunchUrl,
} from './launchStackUrl';

// ============================================
// Types
// ============================================

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'member';
  onboarding_completed_at: string | null;
  is_saas_admin?: boolean;
  phone_number: string | null;
  phone_verified: boolean;
  email_verified: boolean;
  mfa_enabled?: boolean;
  mfa_method?: 'email' | 'phone' | null;
}

export interface AuthTenant {
  id: string;
  name: string;
  external_id: string;
}

interface AuthState {
  user: AuthUser | null;
  tenant: AuthTenant | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  /** SaaS AWS account ID for Launch Stack params (from GET /api/auth/me) */
  saas_account_id: string | null;
  /** One-click CloudFormation Launch Stack URL when template URL is configured (default stack name) */
  read_role_launch_stack_url: string | null;
  /** For building Launch Stack URL with custom stack name (e.g. SecurityAutopilotReadRole-2) */
  read_role_template_url: string | null;
  read_role_region: string | null;
  read_role_default_stack_name: string;
  write_role_launch_stack_url: string | null;
  write_role_template_url: string | null;
  write_role_default_stack_name: string;
  /** One-time revealed token for EventBridge API Destination calls (tenant admin only). */
  control_plane_token: string | null;
  control_plane_token_fingerprint: string | null;
  control_plane_token_created_at: string | null;
  control_plane_token_revoked_at: string | null;
  control_plane_token_active: boolean;
  control_plane_forwarder_launch_stack_url: string | null;
  /** CloudFormation template URL for deploying the control-plane forwarder (when configured). */
  control_plane_forwarder_template_url: string | null;
  /** Public SaaS ingest URL to prefill as SaaSIngestUrl param in the CloudFormation stack. */
  control_plane_ingest_url: string | null;
  control_plane_forwarder_default_stack_name: string;
}

interface AuthApiPayload {
  access_token?: string;
  token_type?: string;
  user: AuthUser;
  tenant: AuthTenant;
  saas_account_id?: string | null;
  read_role_launch_stack_url?: string | null;
  read_role_template_url?: string | null;
  read_role_region?: string | null;
  read_role_default_stack_name?: string;
  write_role_launch_stack_url?: string | null;
  write_role_template_url?: string | null;
  write_role_default_stack_name?: string;
  control_plane_token?: string | null;
  control_plane_token_fingerprint?: string | null;
  control_plane_token_created_at?: string | null;
  control_plane_token_revoked_at?: string | null;
  control_plane_token_active?: boolean;
  control_plane_forwarder_launch_stack_url?: string | null;
  control_plane_forwarder_template_url?: string | null;
  control_plane_ingest_url?: string | null;
  control_plane_forwarder_default_stack_name?: string;
}

interface RefreshTokenPayload {
  access_token: string;
  token_type: string;
}

interface MfaChallengePayload {
  mfa_required: true;
  mfa_ticket: string;
  mfa_method: 'email' | 'phone';
  destination_hint: string;
}

interface FirebaseDeliveryPayload {
  custom_token: string;
  continue_url: string;
}

interface SignupPendingPayload {
  message: string;
  email: string;
  resend_ticket: string;
  firebase_delivery: FirebaseDeliveryPayload;
}

export interface LoginResult {
  mfaRequired: boolean;
  mfaTicket?: string;
  mfaMethod?: 'email' | 'phone';
  destinationHint?: string;
}

type VerificationRequiredError = Error & {
  email: string;
  resendTicket: string;
};

interface AuthContextValue extends AuthState {
  login: (email: string, password: string, rememberMe?: boolean) => Promise<LoginResult>;
  completeMfaLogin: (mfaTicket: string, code: string, rememberMe?: boolean) => Promise<void>;
  signup: (
    companyName: string,
    name: string,
    email: string,
    password: string
  ) => Promise<SignupPendingPayload | { email: string }>;
  acceptInvite: (token: string, name: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  markOnboardingComplete: () => Promise<void>;
  rotateControlPlaneToken: () => Promise<string>;
  revokeControlPlaneToken: () => Promise<void>;
  /** Build Launch Stack URL with custom stack name (if name is already in use, use e.g. SecurityAutopilotReadRole-2) */
  buildReadRoleLaunchStackUrl: (stackName: string) => string | null;
  /** Build WriteRole Launch Stack URL with custom stack name (must differ from ReadRole stack name). */
  buildWriteRoleLaunchStackUrl: (stackName: string) => string | null;
  /** Build control-plane forwarder Launch Stack URL for a given region + stack name. */
  buildControlPlaneForwarderLaunchStackUrl: (
    region: string,
    stackName: string,
    tokenOverride?: string | null
  ) => string | null;
  mutateUser: (partialUser: Partial<AuthUser>) => void;
}

// ============================================
// Context
// ============================================

const AuthContext = createContext<AuthContextValue | null>(null);

const SESSION_EXPIRED_PATH = '/session-expired';
const CSRF_COOKIE_NAME = 'csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const LEGACY_AUTH_TOKEN_KEY = 'auth_token';
const DEFAULT_READ_ROLE_STACK_NAME = 'SecurityAutopilotReadRole';
const DEFAULT_WRITE_ROLE_STACK_NAME = 'SecurityAutopilotWriteRole';
const DEFAULT_CONTROL_PLANE_FORWARDER_STACK_NAME = 'SecurityAutopilotControlPlaneForwarder';
const TOKEN_REFRESH_LEAD_TIME_MS = 10 * 60 * 1000;

function getCookieValue(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const cookieEntry = document.cookie
    .split(';')
    .map(token => token.trim())
    .find(token => token.startsWith(`${name}=`));
  if (!cookieEntry) return null;
  return decodeURIComponent(cookieEntry.slice(name.length + 1));
}

function buildCsrfHeader(): Record<string, string> {
  const csrfToken = getCookieValue(CSRF_COOKIE_NAME);
  if (!csrfToken) return {};
  return { [CSRF_HEADER_NAME]: csrfToken };
}

function getApiUrl(endpoint: string): string {
  return `${getApiBaseUrl()}${endpoint}`;
}

function decodeBase64Url(value: string): string {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
  return atob(padded);
}

function getTokenExpiryMs(token?: string | null): number | null {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    const payload = JSON.parse(decodeBase64Url(parts[1])) as { exp?: unknown };
    const exp = payload.exp;
    return typeof exp === 'number' ? exp * 1000 : null;
  } catch {
    return null;
  }
}

function unauthenticatedState(isLoading: boolean): AuthState {
  return {
    user: null,
    tenant: null,
    isLoading,
    isAuthenticated: false,
    saas_account_id: null,
    read_role_launch_stack_url: null,
    read_role_template_url: null,
    read_role_region: null,
    read_role_default_stack_name: DEFAULT_READ_ROLE_STACK_NAME,
    write_role_launch_stack_url: null,
    write_role_template_url: null,
    write_role_default_stack_name: DEFAULT_WRITE_ROLE_STACK_NAME,
    control_plane_token: null,
    control_plane_token_fingerprint: null,
    control_plane_token_created_at: null,
    control_plane_token_revoked_at: null,
    control_plane_token_active: false,
    control_plane_forwarder_launch_stack_url: null,
    control_plane_forwarder_template_url: null,
    control_plane_ingest_url: null,
    control_plane_forwarder_default_stack_name: DEFAULT_CONTROL_PLANE_FORWARDER_STACK_NAME,
  };
}

function authenticatedState(payload: AuthApiPayload): AuthState {
  return {
    user: payload.user,
    tenant: payload.tenant,
    isLoading: false,
    isAuthenticated: true,
    saas_account_id: payload.saas_account_id ?? null,
    read_role_launch_stack_url: payload.read_role_launch_stack_url ?? null,
    read_role_template_url: payload.read_role_template_url ?? null,
    read_role_region: payload.read_role_region ?? null,
    read_role_default_stack_name: payload.read_role_default_stack_name ?? DEFAULT_READ_ROLE_STACK_NAME,
    write_role_launch_stack_url: payload.write_role_launch_stack_url ?? null,
    write_role_template_url: payload.write_role_template_url ?? null,
    write_role_default_stack_name: payload.write_role_default_stack_name ?? DEFAULT_WRITE_ROLE_STACK_NAME,
    control_plane_token: payload.control_plane_token ?? null,
    control_plane_token_fingerprint: payload.control_plane_token_fingerprint ?? null,
    control_plane_token_created_at: payload.control_plane_token_created_at ?? null,
    control_plane_token_revoked_at: payload.control_plane_token_revoked_at ?? null,
    control_plane_token_active: payload.control_plane_token_active ?? false,
    control_plane_forwarder_launch_stack_url: payload.control_plane_forwarder_launch_stack_url ?? null,
    control_plane_forwarder_template_url: payload.control_plane_forwarder_template_url ?? null,
    control_plane_ingest_url: payload.control_plane_ingest_url ?? null,
    control_plane_forwarder_default_stack_name:
      payload.control_plane_forwarder_default_stack_name ?? DEFAULT_CONTROL_PLANE_FORWARDER_STACK_NAME,
  };
}

function isMfaChallengePayload(payload: unknown): payload is MfaChallengePayload {
  if (typeof payload !== 'object' || payload === null) return false;
  const candidate = payload as Record<string, unknown>;
  return (
    candidate.mfa_required === true &&
    typeof candidate.mfa_ticket === 'string' &&
    (candidate.mfa_method === 'email' || candidate.mfa_method === 'phone') &&
    typeof candidate.destination_hint === 'string'
  );
}

// ============================================
// Provider
// ============================================

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => unauthenticatedState(true));
  const [tokenExpiryMs, setTokenExpiryMs] = useState<number | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const markSessionExpired = useCallback(() => {
    setState(unauthenticatedState(false));
    setTokenExpiryMs(null);
    if (typeof window !== 'undefined') {
      window.location.href = SESSION_EXPIRED_PATH;
    }
  }, []);

  // Load current cookie-backed session on mount.
  useEffect(() => {
    const initAuth = async () => {
      if (typeof window !== 'undefined') {
        // One-time migration cleanup from pre-cookie auth storage.
        localStorage.removeItem(LEGACY_AUTH_TOKEN_KEY);
      }

      try {
        const response = await fetch(getApiUrl('/api/auth/me'), {
          credentials: 'include',
        });

        if (!response.ok) {
          setState(unauthenticatedState(false));
          return;
        }

        const data = (await response.json()) as AuthApiPayload;
        setState(authenticatedState(data));
        const loginTokenExpiry = getTokenExpiryMs(data.access_token);
        if (loginTokenExpiry !== null) {
          setTokenExpiryMs(loginTokenExpiry);
          return;
        }

        const refreshResponse = await fetch(getApiUrl('/api/auth/refresh'), {
          method: 'POST',
          headers: buildCsrfHeader(),
          credentials: 'include',
        });
        if (refreshResponse.status === 401) {
          markSessionExpired();
          return;
        }
        if (!refreshResponse.ok) return;

        const refreshPayload = (await refreshResponse.json()) as RefreshTokenPayload;
        setTokenExpiryMs(getTokenExpiryMs(refreshPayload.access_token));
      } catch {
        setState(unauthenticatedState(false));
      }
    };

    initAuth();
  }, [markSessionExpired]);

  const parseError = useCallback(async (response: Response, fallback: string) => {
    try {
      const error = await response.json();
      if (typeof error.detail === 'string') return error.detail;
      if (error.detail?.msg) return error.detail.msg;
      if (error.message) return error.message;
      return fallback;
    } catch {
      return response.statusText || fallback;
    }
  }, []);

  const refreshAccessToken = useCallback(async () => {
    const response = await fetch(getApiUrl('/api/auth/refresh'), {
      method: 'POST',
      headers: buildCsrfHeader(),
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 401) {
        markSessionExpired();
        return;
      }
      const message = await parseError(response, 'Failed to refresh session');
      throw new Error(message);
    }

    const payload = (await response.json()) as RefreshTokenPayload;
    setTokenExpiryMs(getTokenExpiryMs(payload.access_token));
  }, [markSessionExpired, parseError]);

  useEffect(() => {
    if (refreshTimerRef.current !== null) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    if (!state.isAuthenticated || tokenExpiryMs === null) return;

    const refreshDelay = Math.max(tokenExpiryMs - Date.now() - TOKEN_REFRESH_LEAD_TIME_MS, 0);
    refreshTimerRef.current = setTimeout(() => {
      void refreshAccessToken();
    }, refreshDelay);

    return () => {
      if (refreshTimerRef.current !== null) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [refreshAccessToken, state.isAuthenticated, tokenExpiryMs]);

  const login = useCallback(async (
    email: string,
    password: string,
    rememberMe = true,
  ): Promise<LoginResult> => {
    const response = await fetch(getApiUrl('/api/auth/login'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password, remember_me: rememberMe }),
    });

    if (!response.ok) {
      try {
        const error = await response.json();
        if (
          error?.detail === 'email_verification_required' &&
          typeof error.email === 'string' &&
          typeof error.resend_ticket === 'string'
        ) {
          const verificationError = new Error('email_verification_required') as VerificationRequiredError;
          verificationError.email = error.email;
          verificationError.resendTicket = error.resend_ticket;
          throw verificationError;
        }
      } catch (error) {
        if (error instanceof Error && error.message === 'email_verification_required') {
          throw error;
        }
      }
      const message = await parseError(response, 'Login failed');
      throw new Error(message);
    }

    const data = (await response.json()) as AuthApiPayload | MfaChallengePayload;
    if (isMfaChallengePayload(data)) {
      return {
        mfaRequired: true,
        mfaTicket: data.mfa_ticket,
        mfaMethod: data.mfa_method,
        destinationHint: data.destination_hint,
      };
    }

    setState(authenticatedState(data));
    setTokenExpiryMs(getTokenExpiryMs(data.access_token));
    return { mfaRequired: false };
  }, [parseError]);

  const completeMfaLogin = useCallback(async (
    mfaTicket: string,
    code: string,
    rememberMe = true,
  ): Promise<void> => {
    const response = await fetch(getApiUrl('/api/auth/login/mfa'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ mfa_ticket: mfaTicket, code, remember_me: rememberMe }),
    });

    if (!response.ok) {
      const message = await parseError(response, 'MFA verification failed');
      throw new Error(message);
    }

    const data = (await response.json()) as AuthApiPayload;
    setState(authenticatedState(data));
    setTokenExpiryMs(getTokenExpiryMs(data.access_token));
  }, [parseError]);

  const signup = useCallback(async (
    companyName: string,
    name: string,
    email: string,
    password: string
  ): Promise<SignupPendingPayload | { email: string }> => {
    const response = await fetch(getApiUrl('/api/auth/signup'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        company_name: companyName,
        name,
        email,
        password,
      }),
    });

    if (!response.ok) {
      const message = await parseError(response, 'Signup failed');
      throw new Error(message);
    }

    if (response.status === 202) {
      const data = (await response.json()) as SignupPendingPayload;
      // Flush any stale in-memory auth state so the old tenant is not visible
      // after signup while email verification is pending.
      setState(unauthenticatedState(false));
      setTokenExpiryMs(null);
      return data;
    }

    const data = (await response.json()) as AuthApiPayload;
    setState(authenticatedState(data));
    setTokenExpiryMs(getTokenExpiryMs(data.access_token));
    return { email: data.user.email };
  }, [parseError]);

  const acceptInvite = useCallback(async (inviteToken: string, name: string, password: string) => {
    const response = await fetch(getApiUrl('/api/users/accept-invite'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        token: inviteToken,
        name,
        password,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to accept invite');
    }

    const data = (await response.json()) as AuthApiPayload;
    setState(authenticatedState(data));
    setTokenExpiryMs(getTokenExpiryMs(data.access_token));
  }, []);

  const logout = useCallback(() => {
    void fetch(getApiUrl('/api/auth/logout'), {
      method: 'POST',
      headers: buildCsrfHeader(),
      credentials: 'include',
    });

    setState(unauthenticatedState(false));
    setTokenExpiryMs(null);
    if (refreshTimerRef.current !== null) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    if (typeof window !== 'undefined') window.location.href = '/landing';
  }, []);

  const refreshUser = useCallback(async () => {
    const response = await fetch(getApiUrl('/api/auth/me'), {
      credentials: 'include',
    });

    if (response.ok) {
      const data = (await response.json()) as AuthApiPayload;
      setState(prev => ({
        ...prev,
        ...authenticatedState(data),
      }));
      return;
    }

    if (response.status === 401) {
      markSessionExpired();
    }
  }, [markSessionExpired]);

  const buildReadRoleLaunchStackUrl = useCallback((stackName: string) => {
    const {
      read_role_launch_stack_url,
      read_role_template_url,
      read_role_region,
      saas_account_id,
      tenant,
      read_role_default_stack_name,
    } = state;

    const name = (stackName || '').trim().replace(/[^a-zA-Z0-9-]/g, '-').slice(0, 128) || DEFAULT_READ_ROLE_STACK_NAME;
    const defaultName = (read_role_default_stack_name || DEFAULT_READ_ROLE_STACK_NAME);

    // Prefer the backend-provided launch URL when the default stack name is used.
    if (read_role_launch_stack_url && name === defaultName) {
      return read_role_launch_stack_url;
    }

    // Reuse the backend-provided pre-signed template URL when available so custom names still
    // work against private S3 buckets. Fall back to the raw template URL only if needed.
    return buildCloudFormationLaunchStackUrl({
      existingLaunchUrl: read_role_launch_stack_url,
      fallbackTemplateUrl: read_role_template_url,
      region: read_role_region,
      stackName: name,
      fallbackStackName: DEFAULT_READ_ROLE_STACK_NAME,
      fallbackParams: {
        param_SaaSAccountId: saas_account_id,
        param_ExternalId: tenant?.external_id,
      },
    });
  }, [state]);

  const buildWriteRoleLaunchStackUrl = useCallback((stackName: string) => {
    const { write_role_launch_stack_url, write_role_template_url, read_role_region, saas_account_id, tenant } = state;
    const name = (stackName || '').trim().replace(/[^a-zA-Z0-9-]/g, '-').slice(0, 128) || DEFAULT_WRITE_ROLE_STACK_NAME;
    return buildCloudFormationLaunchStackUrl({
      existingLaunchUrl: write_role_launch_stack_url,
      fallbackTemplateUrl: write_role_template_url,
      region: read_role_region,
      stackName: name,
      fallbackStackName: DEFAULT_WRITE_ROLE_STACK_NAME,
      fallbackParams: {
        param_SaaSAccountId: saas_account_id,
        param_ExternalId: tenant?.external_id,
      },
    });
  }, [state]);

  const buildControlPlaneForwarderLaunchStackUrl = useCallback(
    (region: string, stackName: string, tokenOverride?: string | null) => {
      const {
        control_plane_forwarder_launch_stack_url,
        control_plane_forwarder_template_url,
        control_plane_ingest_url,
        control_plane_token,
      } = state;
      const token = tokenOverride ?? control_plane_token;
      const templateUrl =
        extractTemplateUrlFromLaunchUrl(control_plane_forwarder_launch_stack_url) || control_plane_forwarder_template_url;
      if (!templateUrl || !control_plane_ingest_url || !token) return null;
      const r = (region || '').trim();
      if (!r) return null;
      const name =
        (stackName || '').trim().replace(/[^a-zA-Z0-9-]/g, '-').slice(0, 128) || DEFAULT_CONTROL_PLANE_FORWARDER_STACK_NAME;
      const base = `https://${r}.console.aws.amazon.com/cloudformation/home?region=${r}`;
      const params = new URLSearchParams({
        templateURL: templateUrl,
        stackName: name,
        param_SaaSIngestUrl: control_plane_ingest_url,
        param_ControlPlaneToken: token,
      });
      return `${base}#/stacks/create/review?${params.toString()}`;
    },
    [state]
  );

  const rotateControlPlaneToken = useCallback(async (): Promise<string> => {
    if (!state.isAuthenticated) throw new Error('Not authenticated');
    const response = await fetch(getApiUrl('/api/auth/control-plane-token/rotate'), {
      method: 'POST',
      headers: buildCsrfHeader(),
      credentials: 'include',
    });
    if (!response.ok) {
      const message = await parseError(response, 'Failed to rotate control-plane token');
      throw new Error(message);
    }
    const payload = (await response.json()) as Partial<AuthApiPayload>;
    const revealed = payload.control_plane_token ?? null;
    setState((prev) => ({
      ...prev,
      control_plane_token: revealed,
      control_plane_token_fingerprint: payload.control_plane_token_fingerprint ?? prev.control_plane_token_fingerprint,
      control_plane_token_created_at: payload.control_plane_token_created_at ?? prev.control_plane_token_created_at,
      control_plane_token_revoked_at: payload.control_plane_token_revoked_at ?? null,
      control_plane_token_active: payload.control_plane_token_active ?? true,
    }));
    if (!revealed) {
      throw new Error('Token rotation completed but no token was returned.');
    }
    return revealed;
  }, [parseError, state.isAuthenticated]);

  const revokeControlPlaneToken = useCallback(async (): Promise<void> => {
    if (!state.isAuthenticated) throw new Error('Not authenticated');
    const response = await fetch(getApiUrl('/api/auth/control-plane-token/revoke'), {
      method: 'POST',
      headers: buildCsrfHeader(),
      credentials: 'include',
    });
    if (!response.ok) {
      const message = await parseError(response, 'Failed to revoke control-plane token');
      throw new Error(message);
    }
    const payload = (await response.json()) as Partial<AuthApiPayload>;
    setState((prev) => ({
      ...prev,
      control_plane_token: null,
      control_plane_token_fingerprint: payload.control_plane_token_fingerprint ?? prev.control_plane_token_fingerprint,
      control_plane_token_created_at: payload.control_plane_token_created_at ?? prev.control_plane_token_created_at,
      control_plane_token_revoked_at: payload.control_plane_token_revoked_at ?? prev.control_plane_token_revoked_at,
      control_plane_token_active: payload.control_plane_token_active ?? false,
    }));
  }, [parseError, state.isAuthenticated]);

  const markOnboardingComplete = useCallback(async () => {
    if (!state.isAuthenticated) throw new Error('Not authenticated');

    const response = await fetch(getApiUrl('/api/users/me'), {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...buildCsrfHeader(),
      },
      credentials: 'include',
      body: JSON.stringify({ onboarding_completed: true }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to complete onboarding');
    }

    // Refresh user data
    await refreshUser();
  }, [refreshUser, state.isAuthenticated]);

  const mutateUser = useCallback((partialUser: Partial<AuthUser>) => {
    setState((prev) => {
      if (!prev.user) return prev;
      return {
        ...prev,
        user: {
          ...prev.user,
          ...partialUser,
        }
      };
    });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        completeMfaLogin,
        signup,
        acceptInvite,
        logout,
        refreshUser,
        markOnboardingComplete,
        rotateControlPlaneToken,
        revokeControlPlaneToken,
        buildReadRoleLaunchStackUrl,
        buildWriteRoleLaunchStackUrl,
        buildControlPlaneForwarderLaunchStackUrl,
        mutateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ============================================
// Hook
// ============================================

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
