import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import type { FontSize, Theme } from '../lib/types';

// ── Constants ───────────────────────────────────────────────────

const THEME_KEY = 'app-theme';
const FONT_SIZE_KEY = 'app-font-size';
const BRIGHTNESS_KEY = 'app-brightness';

export type Brightness = 'light' | 'normal' | 'dark' | 'contrast';

// ── Types ───────────────────────────────────────────────────────

interface ThemeContextValue {
  theme: Theme;
  fontSize: FontSize;
  brightness: Brightness;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
  setFontSize: (size: FontSize) => void;
  setBrightness: (b: Brightness) => void;
}

// ── Helpers ─────────────────────────────────────────────────────

const VALID_THEMES: Theme[] = ['light', 'dark', 'ocean', 'mist'];

function loadTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY) as Theme;
    if (VALID_THEMES.includes(stored)) return stored;
  } catch { /* ignore */ }
  if (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'ocean';
  }
  return 'ocean';
}

function loadFontSize(): FontSize {
  try {
    const stored = localStorage.getItem(FONT_SIZE_KEY);
    if (stored === 'small' || stored === 'normal' || stored === 'large') return stored;
  } catch { /* ignore */ }
  return 'normal';
}

function loadBrightness(): Brightness {
  try {
    const stored = localStorage.getItem(BRIGHTNESS_KEY);
    if (['light', 'normal', 'dark', 'contrast'].includes(stored || '')) return stored as Brightness;
  } catch { /* ignore */ }
  return 'normal';
}

function applyTheme(theme: Theme) {
  // data-theme drives CSS token variants (ocean / mist / light / dark)
  document.documentElement.setAttribute('data-theme', theme);
  // Keep a legacy light/dark class for any direct dark: Tailwind utilities
  const isDark = theme === 'dark';
  document.documentElement.classList.toggle('dark', isDark);
}

function applyFontSize(size: FontSize) {
  document.documentElement.setAttribute('data-font-size', size);
  // Apply base font size to root
  const sizes: Record<FontSize, string> = { small: '13px', normal: '16px', large: '20px' };
  document.documentElement.style.fontSize = sizes[size];
}

function applyBrightness(brightness: Brightness) {
  document.documentElement.setAttribute('data-brightness', brightness);
}

// ── Context ─────────────────────────────────────────────────────

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

// ── Provider ────────────────────────────────────────────────────

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(loadTheme);
  const [fontSize, setFontSizeState] = useState<FontSize>(loadFontSize);
  const [brightness, setBrightnessState] = useState<Brightness>(loadBrightness);

  useEffect(() => {
    applyTheme(theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  }, [theme]);

  useEffect(() => {
    applyFontSize(fontSize);
    try { localStorage.setItem(FONT_SIZE_KEY, fontSize); } catch { /* ignore */ }
  }, [fontSize]);

  useEffect(() => {
    applyBrightness(brightness);
    try { localStorage.setItem(BRIGHTNESS_KEY, brightness); } catch { /* ignore */ }
  }, [brightness]);

  const toggleTheme = useCallback(() => {
    // Cycles: ocean → dark → ocean (the two "main" modes)
    setThemeState((prev) => {
      if (prev === 'light' || prev === 'ocean' || prev === 'mist') return 'dark';
      return 'ocean';
    });
  }, []);

  const setTheme = useCallback((t: Theme) => setThemeState(t), []);
  const setFontSize = useCallback((s: FontSize) => setFontSizeState(s), []);
  const setBrightness = useCallback((b: Brightness) => setBrightnessState(b), []);

  return (
    <ThemeContext.Provider value={{ theme, fontSize, brightness, toggleTheme, setTheme, setFontSize, setBrightness }}>
      {children}
    </ThemeContext.Provider>
  );
}

// ── Hook ────────────────────────────────────────────────────────

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (ctx === undefined) throw new Error('useTheme must be used within a ThemeProvider');
  return ctx;
}
