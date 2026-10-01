import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { USE_MOCK } from './api/client'
import { I18nProvider } from './i18n/I18nProvider'

/** With VITE_USE_MOCK=true the in-browser mock server answers; otherwise the real API does. */
async function prepare() {
  if (!USE_MOCK) return
  const { worker } = await import('./mocks/browser')
  await worker.start({ onUnhandledRequest: 'bypass', quiet: true })
}

void prepare().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <BrowserRouter>
        <I18nProvider>
          <App />
        </I18nProvider>
      </BrowserRouter>
    </StrictMode>,
  )
})
