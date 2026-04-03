import { useState, useRef, useEffect } from 'react';
import { Sun, Moon, Menu, LogOut, User, ChevronDown, AArrowUp, AArrowDown, Settings2, HelpCircle } from 'lucide-react';
import { useAuth } from '../../contexts/AppContext';
import { useTheme, type Brightness } from '../../contexts/ThemeContext';
import { useHelp } from '../../contexts/HelpContext';
import { useTranslation } from 'react-i18next';
import type { Theme } from '../../lib/types';

interface HeaderProps {
  onMenuToggle: () => void;
  helpTopic?: string;
}

export default function Header({ onMenuToggle, helpTopic }: HeaderProps) {
  const { user, logout } = useAuth();
  const { theme, setTheme, toggleTheme, fontSize, setFontSize, brightness, setBrightness } = useTheme();
  const { openHelp } = useHelp();
  const { t, i18n } = useTranslation();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  // Close menus on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setUserMenuOpen(false);
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) setSettingsOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggleLanguage = () => {
    const next = i18n.language === 'en' ? 'he' : 'en';
    i18n.changeLanguage(next);
    document.documentElement.dir = next === 'he' ? 'rtl' : 'ltr';
  };

  const cycleFontSize = (direction: 'up' | 'down') => {
    const sizes: Array<'small' | 'normal' | 'large'> = ['small', 'normal', 'large'];
    const currentIdx = sizes.indexOf(fontSize);
    if (direction === 'up' && currentIdx < sizes.length - 1) {
      setFontSize(sizes[currentIdx + 1]);
    } else if (direction === 'down' && currentIdx > 0) {
      setFontSize(sizes[currentIdx - 1]);
    }
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 bg-header flex items-center justify-between px-4 text-white shadow-md">
      {/* Left section */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="lg:hidden p-1.5 rounded-md hover:bg-white/10 transition-colors"
          aria-label="Toggle menu"
        >
          <Menu size={20} />
        </button>

        <div className="flex items-center gap-2">
          <Sun size={24} className="text-yellow-400" />
          <span className="text-lg font-bold tracking-wide">{t('app.title')}</span>
          <span className="hidden md:inline text-sm text-white/60 ml-1">
            {t('app.tagline')}
          </span>
        </div>
      </div>

      {/* Right section */}
      <div className="flex items-center gap-1.5">
        {/* Language toggle */}
        <button
          onClick={toggleLanguage}
          className="px-2 py-1 text-xs font-semibold rounded-md hover:bg-white/10 transition-colors border border-white/20"
          title="Toggle language"
        >
          {i18n.language === 'en' ? 'HE' : 'EN'}
        </button>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="p-1.5 rounded-md hover:bg-white/10 transition-colors"
          aria-label="Toggle theme"
          title={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>

        {/* Font size buttons */}
        <button
          onClick={() => cycleFontSize('down')}
          className="p-1.5 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30"
          disabled={fontSize === 'small'}
          aria-label="Decrease font size"
          title="Decrease font size"
        >
          <AArrowDown size={18} />
        </button>
        <button
          onClick={() => cycleFontSize('up')}
          className="p-1.5 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30"
          disabled={fontSize === 'large'}
          aria-label="Increase font size"
          title="Increase font size"
        >
          <AArrowUp size={18} />
        </button>

        {/* Help button */}
        <button
          onClick={() => openHelp(helpTopic)}
          className="p-1.5 rounded-md hover:bg-white/10 transition-colors"
          aria-label={t('help.modal.label', 'Help')}
          title={t('help.modal.label', 'Help')}
        >
          <HelpCircle size={18} />
        </button>

        {/* Settings popup */}
        <div className="relative" ref={settingsRef}>
          <button
            onClick={() => setSettingsOpen(prev => !prev)}
            className="p-1.5 rounded-md hover:bg-white/10 transition-colors"
            aria-label="Display settings"
            title="Display settings"
          >
            <Settings2 size={18} />
          </button>
          {settingsOpen && (
            <div className="absolute end-0 top-full mt-1 w-64 bg-surface rounded-lg shadow-lg border border-border py-3 px-3 z-50">
              {/* Theme */}
              <p className="text-xs font-semibold text-text-secondary mb-2">{t('settings.theme', 'Theme')}</p>
              <div className="grid grid-cols-2 gap-1 mb-3">
                {(['ocean', 'mist', 'light', 'dark'] as Theme[]).map(th => (
                  <button
                    key={th}
                    onClick={() => setTheme(th)}
                    className={`px-2 py-1 text-xs rounded capitalize ${
                      theme === th
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {th}
                  </button>
                ))}
              </div>
              {/* Brightness */}
              <p className="text-xs font-semibold text-text-secondary mb-2">{t('settings.brightness', 'Brightness')}</p>
              <div className="flex gap-1 mb-3">
                {(['light', 'normal', 'dark', 'contrast'] as Brightness[]).map(b => (
                  <button
                    key={b}
                    onClick={() => setBrightness(b)}
                    className={`flex-1 px-1.5 py-1 text-[10px] rounded capitalize ${
                      brightness === b
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {b}
                  </button>
                ))}
              </div>
              {/* Font size */}
              <p className="text-xs font-semibold text-text-secondary mb-2">{t('settings.fontSize', 'Font Size')}</p>
              <div className="flex gap-1">
                {(['small', 'normal', 'large'] as const).map(s => (
                  <button
                    key={s}
                    onClick={() => setFontSize(s)}
                    className={`flex-1 px-2 py-1 text-xs rounded capitalize ${
                      fontSize === s
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setUserMenuOpen((prev) => !prev)}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-white/10 transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-sm font-bold">
              {user?.display_name?.charAt(0).toUpperCase() ?? <User size={16} />}
            </div>
            <span className="hidden sm:inline text-sm max-w-[120px] truncate">
              {user?.display_name ?? user?.username}
            </span>
            <ChevronDown size={14} className={`transition-transform ${userMenuOpen ? 'rotate-180' : ''}`} />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 top-full mt-1 w-48 bg-surface rounded-lg shadow-lg border border-border py-1 z-50">
              <div className="px-3 py-2 border-b border-border">
                <p className="text-sm font-medium text-text-primary">{user?.display_name}</p>
                <p className="text-xs text-text-muted capitalize">{user?.role}</p>
              </div>
              <button
                onClick={() => {
                  setUserMenuOpen(false);
                  logout();
                }}
                className="flex items-center gap-2 w-full px-3 py-2 text-sm text-danger hover:bg-danger-light transition-colors"
              >
                <LogOut size={16} />
                {t('auth.logout')}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
