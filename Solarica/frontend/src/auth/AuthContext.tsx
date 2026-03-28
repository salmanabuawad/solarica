import React, { createContext, useContext, useEffect, useState } from "react";
import { loadLanguageFromServer } from "../contexts/AppConfigContext";
import i18n, { type Language, LANGUAGES } from "../i18n";

export interface CurrentUser {
  id: number;
  full_name: string;
  email: string;
  global_roles: string[];
}

interface AuthContextValue {
  token: string | null;
  user: CurrentUser | null;
  loading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
  isManager: boolean;
}

const AuthContext = createContext<AuthContextValue>({} as AuthContextValue);

const TOKEN_KEY = "solarica.token";
const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

async function applyServerLanguage(): Promise<void> {
  const lang = await loadLanguageFromServer();
  if (!lang) return;
  try { localStorage.setItem("solarica.language", lang); } catch {}
  const langDef = LANGUAGES.find((l) => l.code === lang);
  document.documentElement.setAttribute("lang", lang);
  document.documentElement.setAttribute("dir", langDef?.dir ?? "ltr");
  i18n.changeLanguage(lang as Language);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState<boolean>(!!localStorage.getItem(TOKEN_KEY));

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  const fetchMe = async (t: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${t}` },
      });
      if (!res.ok) { logout(); return; }
      setUser(await res.json());
      // Apply language from user preferences (non-blocking)
      applyServerLanguage();
    } catch {
      logout();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) fetchMe(token);
    else setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = async (t: string) => {
    localStorage.setItem(TOKEN_KEY, t);
    setToken(t);
    await fetchMe(t);
  };

  return (
    <AuthContext.Provider
      value={{
        token, user, loading, login, logout,
        isManager: user?.global_roles.includes("manager") ?? false,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

/** Read the stored token outside React (for API calls). */
export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
