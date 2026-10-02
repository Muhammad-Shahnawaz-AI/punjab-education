'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import {
  getCurrentUser,
  loginUser,
  logoutUser,
  refreshUserSession,
  registerUser,
  setAuthTokens,
  setTokenUpdateListener,
  type AuthTokenResponse,
  type AuthUser,
} from '../lib/api';

type AuthContextValue = {
  user: AuthUser | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);

  function persistTokens(tokens: AuthTokenResponse): void {
    setAuthTokens(tokens.access_token, tokens.refresh_token);
    setUser(tokens.user);
    const expiry = Date.now() + tokens.access_expires_in * 1000;
    setExpiresAt(expiry);
    sessionStorage.setItem('access_token', tokens.access_token);
    sessionStorage.setItem('refresh_token', tokens.refresh_token);
    sessionStorage.setItem('access_expires_at', String(expiry));
  }

  function clearSession(): void {
    setAuthTokens(null, null);
    setUser(null);
    setExpiresAt(null);
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('refresh_token');
    sessionStorage.removeItem('access_expires_at');
  }

  useEffect(() => {
    setTokenUpdateListener(persistTokens);
    const access = sessionStorage.getItem('access_token');
    const refresh = sessionStorage.getItem('refresh_token');
    const expiry = sessionStorage.getItem('access_expires_at');
    setAuthTokens(access, refresh);
    setExpiresAt(expiry === null ? null : Number(expiry));

    async function restoreSession(): Promise<void> {
      if (refresh === null) {
        setIsLoading(false);
        return;
      }
      try {
        if (access === null) {
          const tokens = await refreshUserSession();
          persistTokens(tokens);
        } else {
          setUser(await getCurrentUser());
        }
      } catch {
        clearSession();
      } finally {
        setIsLoading(false);
      }
    }

    void restoreSession();
    return () => setTokenUpdateListener(null);
  }, []);

  useEffect(() => {
    if (user === null || expiresAt === null) return;
    const timeout = window.setTimeout(() => {
      void refreshUserSession().catch(() => {
        clearSession();
        router.replace('/login');
      });
    }, Math.max(expiresAt - Date.now() - 30_000, 1_000));
    return () => window.clearTimeout(timeout);
  }, [expiresAt, router, user]);

  async function login(email: string, password: string): Promise<void> {
    persistTokens(await loginUser(email, password));
  }

  async function register(email: string, password: string): Promise<void> {
    persistTokens(await registerUser(email, password));
  }

  async function logout(): Promise<void> {
    const refresh = sessionStorage.getItem('refresh_token');
    if (refresh !== null) await logoutUser(refresh).catch(() => undefined);
    clearSession();
    router.replace('/login');
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}