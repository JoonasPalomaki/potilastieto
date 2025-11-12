import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import type { AuthSession, LoginCredentials } from '../services/authService';
import { authService } from '../services/authService';

interface AuthContextValue {
  session: AuthSession | null;
  initializing: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<AuthSession>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    const storedSession = authService.getSession();
    setSession(storedSession);
    setInitializing(false);
  }, []);

  const logout = useCallback(() => {
    authService.logout();
    setSession(null);
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const newSession = await authService.login(credentials);
    setSession(newSession);
    return newSession;
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }

    if (authService.isExpired(session.expiresAt)) {
      logout();
      return;
    }

    const timeout = window.setTimeout(() => {
      logout();
    }, Math.max(0, session.expiresAt - Date.now()));

    return () => {
      window.clearTimeout(timeout);
    };
  }, [session, logout]);

  const value = useMemo(
    () => ({
      session,
      initializing,
      isAuthenticated: Boolean(session),
      login,
      logout,
    }),
    [session, initializing, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
};
