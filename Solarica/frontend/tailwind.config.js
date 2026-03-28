/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'theme-header': 'rgb(var(--theme-header) / <alpha-value>)',
        'theme-sidebar': 'rgb(var(--theme-sidebar) / <alpha-value>)',
        'theme-sidebar-hover': 'rgb(var(--theme-sidebar-hover) / <alpha-value>)',
        'theme-sidebar-active': 'rgb(var(--theme-sidebar-active) / <alpha-value>)',
        'theme-sidebar-active-stripe': 'rgb(var(--theme-sidebar-active-stripe) / <alpha-value>)',
        'theme-action-accent': 'rgb(var(--theme-action-accent) / <alpha-value>)',
        'theme-action-accent-hover': 'rgb(var(--theme-action-accent-hover) / <alpha-value>)',
        'theme-nav-bg': 'rgb(var(--theme-nav-bg) / <alpha-value>)',
        'theme-content': 'rgb(var(--theme-content) / <alpha-value>)',
        'theme-text-primary': 'rgb(var(--theme-text-primary) / <alpha-value>)',
        'theme-text-muted': 'rgb(var(--theme-text-muted) / <alpha-value>)',
        'theme-card-border': 'rgb(var(--theme-card-border) / <alpha-value>)',
        'theme-highlight': 'rgb(var(--theme-highlight) / <alpha-value>)',
        'app-header': '#2E62A2',
        'app-sidebar': '#2F4D52',
        'app-sidebar-hover': '#3D6971',
        'app-sidebar-active': '#3D6971',
        'app-sidebar-indicator': '#66CCFF',
        'app-accent': '#2196F3',
        'app-accent-hover': '#1976D2',
        'app-bg': '#F7F9FA',
        'app-panel': '#F0F0F0',
        'app-text-primary': '#333333',
        'app-text-muted': '#6C757D',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      fontSize: {
        'theme-base': ['var(--theme-font-size-base)', { lineHeight: '1.5' }],
        'theme-sm': ['var(--theme-font-size-sm)', { lineHeight: '1.4' }],
        'theme-xs': ['var(--theme-font-size-xs)', { lineHeight: '1.3' }],
      },
    },
  },
  plugins: [],
};
