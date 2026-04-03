import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import he from './he.json'
import ar from './ar.json'
import es from './es.json'
import fr from './fr.json'
import pt from './pt.json'

const LANG_KEY = 'solarica_language'
const supported = ['en', 'he', 'ar', 'es', 'fr', 'pt']

function detectLanguage(): string {
  const saved = localStorage.getItem(LANG_KEY)
  if (saved && supported.includes(saved)) return saved
  const browser = navigator.language.split('-')[0]
  return supported.includes(browser) ? browser : 'en'
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    he: { translation: he },
    ar: { translation: ar },
    es: { translation: es },
    fr: { translation: fr },
    pt: { translation: pt },
  },
  lng: detectLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

i18n.on('languageChanged', (lng) => {
  localStorage.setItem(LANG_KEY, lng)
})

export default i18n
