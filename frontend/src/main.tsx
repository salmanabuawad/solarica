import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { AppProvider } from './contexts/AppContext'
import { ThemeProvider } from './contexts/ThemeContext'
import { FieldConfigProvider } from './lib/FieldConfigContext'
import './i18n/i18n'
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <AppProvider>
        <FieldConfigProvider>
          <App />
        </FieldConfigProvider>
      </AppProvider>
    </ThemeProvider>
  </StrictMode>,
)
