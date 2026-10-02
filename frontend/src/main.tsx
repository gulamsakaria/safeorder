import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, HashRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { STATIC, USE_MOCK } from './api/client'
import { I18nProvider } from './i18n/I18nProvider'

/** With VITE_USE_MOCK=true the in-browser mock server answers; otherwise the real API does. */
async function prepare() {
  if (STATIC) {
    // No backend: load the exported models and data that sit next to the page.
    const { loadEngine } = await import('./engine/engine')
    await loadEngine('./engine/')
    const { installSellers } = await import('./static/handlers')
    installSellers()
    return
  }
  if (!USE_MOCK) return
  const { worker } = await import('./mocks/browser')
  await worker.start({ onUnhandledRequest: 'bypass', quiet: true })
}

// Hash routes (#/order/O-0001) need no server rewrite rules, so the site works on any static host.
const Router = STATIC ? HashRouter : BrowserRouter

void prepare().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <Router>
        <I18nProvider>
          <App />
        </I18nProvider>
      </Router>
    </StrictMode>,
  )
})
