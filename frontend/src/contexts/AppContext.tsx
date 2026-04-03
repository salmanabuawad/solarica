/**
 * AppContext — unified auth + tabs + appearance for Solarica.
 * Replaces separate AuthContext / TabContext / ThemeContext.
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';
import * as api from '../lib/api';
import type { User } from '../lib/types';
import i18n from '../i18n/i18n';

/* ── Types ─────────────────────────────────────────────────── */

export type ThemeId   = 'ocean';
export type Brightness = 'light' | 'normal' | 'dark' | 'contrast';
export type FontSize   = 'small' | 'normal' | 'large';

export interface Tab {
  id:         string;
  type:       string;
  label:      string;
  icon?:      ReactNode;
  pinned?:    boolean;
  [key: string]: unknown;
}

export type LanguageCode = 'en' | 'he' | 'ar' | 'es' | 'fr' | 'pt';

export interface LanguageOption {
  code: LanguageCode;
  label: string;
  nativeLabel: string;
  flag: string;
}

export const LANGUAGES: LanguageOption[] = [
  { code: 'en', label: 'English',    nativeLabel: 'English',    flag: '🇬🇧' },
  { code: 'he', label: 'Hebrew',     nativeLabel: 'עברית',      flag: '🇮🇱' },
  { code: 'ar', label: 'Arabic',     nativeLabel: 'العربية',    flag: '🇸🇦' },
  { code: 'es', label: 'Spanish',    nativeLabel: 'Español',    flag: '🇪🇸' },
  { code: 'fr', label: 'French',     nativeLabel: 'Français',   flag: '🇫🇷' },
  { code: 'pt', label: 'Portuguese', nativeLabel: 'Português',  flag: '🇧🇷' },
];

interface AppContextValue {
  /* Auth */
  user:            User | null;
  isAuthenticated: boolean;
  login:           (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout:          () => void;
  /* Tabs */
  tabs:        Tab[];
  activeTabId: string;
  openTab:     (tab: Tab) => void;
  closeTab:    (tabId: string) => void;
  /* Appearance */
  brightness:    Brightness;
  fontSize:      FontSize;
  setBrightness: (b: Brightness) => void;
  setFontSize:   (f: FontSize)   => void;
  /* Language */
  language:    LanguageCode;
  setLanguage: (lang: LanguageCode) => void;
  /* Unsaved-changes guard */
  hasUnsavedChanges: React.MutableRefObject<boolean>;
}

const AppContext = createContext<AppContextValue | null>(null);

const SESSION_KEY = 'solarica_session';
const BRIGHT_KEY  = 'solarica_brightness';
const FS_KEY      = 'solarica_fontsize';

/** Decode JWT payload and check expiry (mirrors api.ts isTokenValid — no import needed). */
function jwtExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 <= Date.now();
  } catch {
    return true; // treat unreadable token as expired
  }
}

function loadUser(): User | null {
  try {
    const user = JSON.parse(localStorage.getItem(SESSION_KEY) || 'null') as User | null;
    const token = localStorage.getItem('solarica_token');
    // No token → stale session, clear it
    if (user && !token) {
      localStorage.removeItem(SESSION_KEY);
      localStorage.removeItem('solarica_user');
      return null;
    }
    // Expired token → clear and force re-login
    if (user && token && jwtExpired(token)) {
      localStorage.removeItem(SESSION_KEY);
      localStorage.removeItem('solarica_user');
      localStorage.removeItem('solarica_token');
      return null;
    }
    return user;
  } catch { return null; }
}

const DEFAULT_TAB: Tab = { id: 'dashboard', type: 'dashboard', label: 'Dashboard', pinned: true };

/* ── Provider ───────────────────────────────────────────────── */

export function AppProvider({ children }: { children: ReactNode }) {
  const [user,       setUser]       = useState<User | null>(loadUser);
  const [tabs,       setTabs]       = useState<Tab[]>([DEFAULT_TAB]);
  const [activeTabId,setActiveTabId]= useState('dashboard');
  const [brightness, setBrightnessSt] = useState<Brightness>(() => (localStorage.getItem(BRIGHT_KEY) as Brightness) || 'normal');
  const [fontSize,   setFontSizeSt]   = useState<FontSize>(  () => (localStorage.getItem(FS_KEY)     as FontSize)   || 'normal');
  const [language,   setLanguageSt]   = useState<LanguageCode>(() => (i18n.language as LanguageCode) || 'en');
  const hasUnsavedChanges = useRef(false);
  const tabsRef = useRef<Tab[]>([DEFAULT_TAB]);

  /* Apply brightness */
  useEffect(() => {
    if (brightness === 'normal') {
      document.documentElement.removeAttribute('data-brightness');
      localStorage.removeItem(BRIGHT_KEY);
    } else {
      document.documentElement.setAttribute('data-brightness', brightness);
      localStorage.setItem(BRIGHT_KEY, brightness);
    }
  }, [brightness]);

  /* Apply font-size */
  useEffect(() => {
    if (fontSize === 'normal') {
      document.documentElement.removeAttribute('data-font-size');
      localStorage.removeItem(FS_KEY);
    } else {
      document.documentElement.setAttribute('data-font-size', fontSize);
      localStorage.setItem(FS_KEY, fontSize);
    }
  }, [fontSize]);

  /* Always use ocean theme */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'ocean');
  }, []);

  /* Keep tabsRef in sync so closeTab can compute next-active without nesting setState */
  useEffect(() => { tabsRef.current = tabs; }, [tabs]);

  /* Language change */
  const setLanguage = useCallback((lang: LanguageCode) => {
    i18n.changeLanguage(lang);
    setLanguageSt(lang);
  }, []);

  /* Sync state if i18n changes externally */
  useEffect(() => {
    const handler = (lng: string) => setLanguageSt(lng as LanguageCode);
    i18n.on('languageChanged', handler);
    return () => i18n.off('languageChanged', handler);
  }, []);

  /* ── Listen for api.clearSession() events (e.g. 401 response interceptor) ── */
  useEffect(() => {
    const handleForceLogout = () => {
      setUser(null);
      setTabs([DEFAULT_TAB]);
      setActiveTabId('dashboard');
      hasUnsavedChanges.current = false;
    };
    window.addEventListener('solarica:logout', handleForceLogout);
    return () => window.removeEventListener('solarica:logout', handleForceLogout);
  }, []);

  /* ── Auth ── */
  const login = useCallback(async (username: string, password: string): Promise<{ success: boolean; error?: string }> => {
    if (!username.trim() || !password) return { success: false, error: 'Username and password are required.' };
    try {
      const result = await api.login(username.trim(), password);
      // api.login now returns { user, token }
      const user = (result as any).user ?? result;
      const token = (result as any).token ?? (result as any).access_token;
      if (token) localStorage.setItem('solarica_token', token);
      localStorage.setItem('solarica_user', JSON.stringify(user));
      localStorage.setItem(SESSION_KEY, JSON.stringify(user));
      setUser(user);
      return { success: true };
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Login failed.';
      return { success: false, error: msg };
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem('solarica_token');
    localStorage.removeItem('solarica_user');
    setUser(null);
    setTabs([DEFAULT_TAB]);
    setActiveTabId('dashboard');
    hasUnsavedChanges.current = false;
  }, []);

  /* ── Tabs ── */
  const openTab = useCallback((tab: Tab) => {
    // Never call setState inside another setState updater — React 18 anti-pattern.
    // Both setTabs and setActiveTabId are called at the top level; React 18 batches them.
    setTabs(prev => {
      if (prev.find(t => t.id === tab.id)) return prev; // already open — no change to tabs
      // Replace other tabs of same type (unless pinned)
      const filtered = prev.filter(t => t.type !== tab.type || t.pinned);
      return [...filtered, tab];
    });
    setActiveTabId(tab.id); // always set active — handles both new-tab and existing-tab cases
  }, []);

  const closeTab = useCallback((tabId: string) => {
    // Compute new tabs list from the ref (always current) to avoid nesting setState calls.
    const currentTabs = tabsRef.current;
    const tab = currentTabs.find(t => t.id === tabId);
    if (!tab || tab.pinned) return;

    const remaining = currentTabs.filter(t => t.id !== tabId);
    const newTabs = remaining.length === 0 ? [DEFAULT_TAB] : remaining;
    setTabs(newTabs);

    // Only switch active tab if the closed tab was active
    setActiveTabId(prev => {
      if (prev !== tabId) return prev;
      return newTabs[newTabs.length - 1]?.id ?? 'dashboard';
    });
  }, []);

  return (
    <AppContext.Provider value={{
      user, isAuthenticated: !!user, login, logout,
      tabs, activeTabId, openTab, closeTab,
      brightness, fontSize,
      setBrightness: setBrightnessSt,
      setFontSize: setFontSizeSt,
      language, setLanguage,
      hasUnsavedChanges,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be inside AppProvider');
  return ctx;
}

/* Backwards-compatibility shims for existing page files */
export function useAuth() {
  const { user, isAuthenticated, login, logout } = useApp();
  return { user, isAuthenticated, login, logout };
}
export function useTabs() {
  const { tabs, activeTabId, openTab, closeTab } = useApp();
  return { tabs, activeTabId, openTab, closeTab, setActiveTab: (id: string) => openTab({ id, type: id, label: id }) };
}
