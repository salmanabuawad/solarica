import { createContext, useContext, useEffect, useState } from "react";
import i18n, { type Language, LANGUAGES } from "../i18n";
import { getStoredToken } from "../auth/AuthContext";

type Theme = "ocean" | "mist";
type FontSize = "small" | "normal" | "large";
type Brightness = "light" | "dark" | "contrast";

interface AppConfig {
  theme: Theme;
  fontSize: FontSize;
  brightness: Brightness;
  language: Language;
  setTheme: (t: Theme) => void;
  setFontSize: (f: FontSize) => void;
  setBrightness: (b: Brightness) => void;
  setLanguage: (l: Language, persist?: boolean) => void;
}

const AppConfigContext = createContext<AppConfig>({
  theme: "ocean",
  fontSize: "normal",
  brightness: "light",
  language: "en",
  setTheme: () => {},
  setFontSize: () => {},
  setBrightness: () => {},
  setLanguage: () => {},
});

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || "/api";

function persist(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch {}
}
function load(key: string, fallback: string): string {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}

async function saveLanguageToServer(language: string): Promise<void> {
  const token = getStoredToken();
  if (!token) return;
  try {
    await fetch(`${API_BASE}/preferences`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ language }),
    });
  } catch {
    // silently ignore — localStorage is the fallback
  }
}

export async function loadLanguageFromServer(): Promise<string | null> {
  const token = getStoredToken();
  if (!token) return null;
  try {
    const res = await fetch(`${API_BASE}/preferences`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.language ?? null;
  } catch {
    return null;
  }
}

export function AppConfigProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => load("solarica.theme", "ocean") as Theme);
  const [fontSize, setFontSizeState] = useState<FontSize>(() => load("solarica.fontSize", "normal") as FontSize);
  const [brightness, setBrightnessState] = useState<Brightness>(() => load("solarica.brightness", "light") as Brightness);
  const [language, setLanguageState] = useState<Language>(() => load("solarica.language", "en") as Language);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    persist("solarica.theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute("data-font-size", fontSize);
    persist("solarica.fontSize", fontSize);
  }, [fontSize]);

  useEffect(() => {
    document.documentElement.setAttribute("data-brightness", brightness);
    persist("solarica.brightness", brightness);
  }, [brightness]);

  useEffect(() => {
    const lang = LANGUAGES.find((l) => l.code === language);
    document.documentElement.setAttribute("lang", language);
    document.documentElement.setAttribute("dir", lang?.dir ?? "ltr");
    i18n.changeLanguage(language);
    persist("solarica.language", language);
  }, [language]);

  // setLanguage: always updates state+DOM; optionally saves to server (default true)
  const setLanguage = (l: Language, persistToServer = true) => {
    setLanguageState(l);
    if (persistToServer) saveLanguageToServer(l);
  };

  return (
    <AppConfigContext.Provider value={{
      theme, fontSize, brightness, language,
      setTheme: setThemeState,
      setFontSize: setFontSizeState,
      setBrightness: setBrightnessState,
      setLanguage,
    }}>
      {children}
    </AppConfigContext.Provider>
  );
}

export function useAppConfig() {
  return useContext(AppConfigContext);
}
