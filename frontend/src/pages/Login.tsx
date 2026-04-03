import { useState } from 'react';
import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Sun, Loader2, AlertCircle } from 'lucide-react';
import { useApp } from '../contexts/AppContext';

export default function Login() {
  const { t } = useTranslation();
  const { login } = useApp();
  const [username,     setUsername]     = useState('');
  const [password,     setPassword]     = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await login(username.trim(), password);
      if (!result.success) setError(result.error ?? 'Login failed.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4"
      style={{ background: 'rgb(var(--theme-content))' }}>
      <div className="max-w-md w-full">

        {/* Logo + title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl shadow-lg mb-4"
            style={{ background: 'rgb(var(--theme-header))' }}>
            <Sun className="w-10 h-10 text-yellow-300" />
          </div>
          <h1 className="text-3xl font-bold mb-1" style={{ color: 'rgb(var(--theme-text-primary))' }}>
            {t('app.title')}
          </h1>
          <p style={{ color: 'rgb(var(--theme-text-muted))', fontSize: 13 }}>
            {t('app.tagline')}
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-200">
          <form onSubmit={handleSubmit} className="space-y-5">

            <div>
              <label htmlFor="username" className="label-base">{t('auth.username')}</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                disabled={loading}
                autoComplete="username"
                autoFocus
                placeholder={t('auth.enter_username')}
                className="input-base"
              />
            </div>

            <div>
              <label htmlFor="password" className="label-base">{t('auth.password')}</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  autoComplete="current-password"
                  placeholder={t('auth.enter_password')}
                  className="input-base pr-14"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  tabIndex={-1}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium focus:outline-none"
                  style={{ color: 'rgb(var(--theme-text-muted))' }}
                >
                  {showPassword ? t('auth.hide_password') : t('auth.show_password')}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !username.trim() || !password}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 text-white text-sm font-semibold rounded-lg shadow-md transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ background: loading ? '#6b7280' : 'rgb(var(--theme-header))' }}
            >
              {loading
                ? <><Loader2 className="w-4 h-4 animate-spin" /><span>{t('auth.signing_in')}</span></>
                : <span>{t('auth.sign_in')}</span>
              }
            </button>
          </form>
        </div>

        <p className="text-center text-xs mt-6" style={{ color: 'rgb(var(--theme-text-muted))' }}>
          {t('app.title')} © {new Date().getFullYear()} · {t('app.positioning')}
        </p>
      </div>
    </div>
  );
}
