/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        /* ── Theme-driven (CSS vars, change with data-theme) ── */
        'theme-header':                'rgb(var(--theme-header) / <alpha-value>)',
        'theme-sidebar':               'rgb(var(--theme-sidebar) / <alpha-value>)',
        'theme-sidebar-hover':         'rgb(var(--theme-sidebar-hover) / <alpha-value>)',
        'theme-sidebar-active':        'rgb(var(--theme-sidebar-active) / <alpha-value>)',
        'theme-sidebar-active-stripe': 'rgb(var(--theme-sidebar-active-stripe) / <alpha-value>)',
        'theme-tab-active':            'rgb(var(--theme-tab-active) / <alpha-value>)',
        'theme-tab-active-hover':      'rgb(var(--theme-tab-active-hover) / <alpha-value>)',
        'theme-tab-active-active':     'rgb(var(--theme-tab-active-active) / <alpha-value>)',
        'theme-nav-bg':                'rgb(var(--theme-nav-bg) / <alpha-value>)',
        'theme-action-accent':         'rgb(var(--theme-action-accent) / <alpha-value>)',
        'theme-action-accent-hover':   'rgb(var(--theme-action-accent-hover) / <alpha-value>)',
        'theme-content':               'rgb(var(--theme-content) / <alpha-value>)',
        'theme-text-primary':          'rgb(var(--theme-text-primary) / <alpha-value>)',
        'theme-text-muted':            'rgb(var(--theme-text-muted) / <alpha-value>)',
        'theme-card-border':           'rgb(var(--theme-card-border) / <alpha-value>)',
        /* ── Static palette ── */
        'app-header':           '#1e3a5f',
        'app-sidebar':          '#162e4a',
        'app-sidebar-hover':    '#1e3f60',
        'app-sidebar-active':   '#1e3f60',
        'app-sidebar-indicator':'#38bdf8',
        'app-accent':           '#2563eb',
        'app-accent-hover':     '#1d4ed8',
        'app-accent-active':    '#1e40af',
        'app-destructive':      '#dc2626',
        'app-tabs-bg':          '#e8edf1',
        'app-bg':               '#f7f9fa',
        'app-input-border':     '#ced4da',
        'app-text-primary':     '#111827',
        'app-text-muted':       '#6b7280',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      fontSize: {
        'theme-base': ['var(--theme-font-size-base)', { lineHeight: '1.5' }],
        'theme-sm':   ['var(--theme-font-size-sm)',   { lineHeight: '1.4' }],
        'theme-xs':   ['var(--theme-font-size-xs)',   { lineHeight: '1.3' }],
      },
      borderRadius: { 'theme-btn': 'var(--theme-btn-radius)' },
    },
  },
  plugins: [],
};
