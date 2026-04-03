import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, Moon, Palette, Settings as SettingsIcon, Sun } from 'lucide-react';
import * as api from '../../lib/api';
import type { Branding } from '../../lib/types';
import { useTheme } from '../../contexts/ThemeContext';

export default function Settings() {
  const { t, i18n } = useTranslation();
  const { theme, toggleTheme } = useTheme();
  const [branding, setBranding] = useState<Branding | null>(null);
  const [loadingBranding, setLoadingBranding] = useState(true);

  useEffect(() => {
    async function loadBranding() {
      try {
        setLoadingBranding(true);
        const data = await api.getBranding();
        setBranding(data);
      } catch (err) {
        console.error('Failed to load branding:', err);
      } finally {
        setLoadingBranding(false);
      }
    }
    loadBranding();
  }, []);

  function handleLanguageChange(lang: string) {
    i18n.changeLanguage(lang);
    document.documentElement.dir = lang === 'he' ? 'rtl' : 'ltr';
    document.documentElement.lang = lang;
  }

  const currentLang = i18n.language || 'en';

  return (
    <div className="p-6 space-y-6 max-w-3xl">
      <div className="flex items-center gap-2">
        <SettingsIcon className="h-5 w-5 text-gray-500" />
        <h2 className="text-lg font-semibold text-gray-900">
          {t('admin.settings', 'Settings')}
        </h2>
      </div>

      {/* Branding Section */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center gap-2 mb-4">
          <Palette className="h-5 w-5 text-blue-500" />
          <h3 className="text-sm font-semibold text-gray-900">Branding</h3>
        </div>
        {loadingBranding ? (
          <div className="flex items-center justify-center h-16">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
          </div>
        ) : branding ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-500 mb-1">Product Name</p>
                <p className="text-sm font-medium text-gray-900">{branding.name}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Tagline</p>
                <p className="text-sm font-medium text-gray-900">{branding.tagline}</p>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-500 mb-1">Positioning</p>
              <p className="text-sm font-medium text-gray-900">{branding.positioning}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">Unable to load branding information.</p>
        )}
      </div>

      {/* Theme Section */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center gap-2 mb-4">
          {theme === 'dark' ? (
            <Moon className="h-5 w-5 text-indigo-500" />
          ) : (
            <Sun className="h-5 w-5 text-amber-500" />
          )}
          <h3 className="text-sm font-semibold text-gray-900">Theme</h3>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => {
              if (theme !== 'light') toggleTheme();
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              theme === 'light'
                ? 'bg-amber-100 text-amber-800 ring-2 ring-amber-400'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Sun className="h-4 w-4" />
            Light
          </button>
          <button
            onClick={() => {
              if (theme !== 'dark') toggleTheme();
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              theme === 'dark'
                ? 'bg-indigo-100 text-indigo-800 ring-2 ring-indigo-400'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            <Moon className="h-4 w-4" />
            Dark
          </button>
        </div>
      </div>

      {/* Language Section */}
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center gap-2 mb-4">
          <Globe className="h-5 w-5 text-green-500" />
          <h3 className="text-sm font-semibold text-gray-900">
            {t('admin.language', 'Language')}
          </h3>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => handleLanguageChange('en')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              currentLang === 'en'
                ? 'bg-green-100 text-green-800 ring-2 ring-green-400'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            EN - English
          </button>
          <button
            onClick={() => handleLanguageChange('he')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              currentLang === 'he'
                ? 'bg-green-100 text-green-800 ring-2 ring-green-400'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            HE - Hebrew
          </button>
        </div>
      </div>
    </div>
  );
}
