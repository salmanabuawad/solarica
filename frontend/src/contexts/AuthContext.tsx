import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { User, UserRole } from '../lib/types';

// ── Types ───────────────────────────────────────────────────────

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  login: (username: string, password: string, role?: UserRole) => Promise<void>;
  logout: () => void;
}

// ── Context ─────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const SESSION_KEY = 'solarica_user';

// Mock user IDs (will be replaced with real auth later)
let nextMockId = 1;

function restoreUser(): User | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (raw) return JSON.parse(raw) as User;
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
  }
  return null;
}

// ── Provider ────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(restoreUser);

  // Keep sessionStorage in sync
  useEffect(() => {
    if (user) {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
    } else {
      sessionStorage.removeItem(SESSION_KEY);
    }
  }, [user]);

  const login = useCallback(
    async (username: string, _password: string, role: UserRole = 'manager') => {
      // Mock login: accept any credentials, use the provided role.
      // Replace with real API call when backend auth is ready.
      const mockUser: User = {
        id: nextMockId++,
        username,
        role,
        display_name: username.charAt(0).toUpperCase() + username.slice(1),
      };
      setUser(mockUser);
    },
    [],
  );

  const logout = useCallback(() => {
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: user !== null,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ── Hook ────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
