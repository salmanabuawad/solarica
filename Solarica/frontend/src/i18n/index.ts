import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en";
import he from "./he";

export type Language = "en" | "he";

export const LANGUAGES: { code: Language; label: string; dir: "ltr" | "rtl" }[] = [
  { code: "en", label: "English", dir: "ltr" },
  { code: "he", label: "עברית", dir: "rtl" },
];

// To add a new language:
// 1. Create src/i18n/<lang>.ts with translations (copy en.ts as template)
// 2. Import it here and add to `resources`
// 3. Add an entry to LANGUAGES above

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    he: { translation: he },
  },
  lng: ((): string => {
    try { return localStorage.getItem("solarica.language") || "en"; } catch { return "en"; }
  })(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
