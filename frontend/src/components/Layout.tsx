import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useBackendStatus } from '../api/backendStatus'
import { useI18n } from '../i18n/useI18n'

/** The sandbox banner is part of the layout, so no screen can ever hide it. */
export function Layout() {
  const { t, toggle } = useI18n()
  const backend = useBackendStatus()
  // the analyst console needs room for side-by-side columns; the buyer screens stay phone-sized
  const path = useLocation().pathname
  const wide = path.startsWith('/analyst') || path.startsWith('/metrics')
  const width = wide ? 'max-w-5xl' : 'max-w-xl'
  const link = ({ isActive }: { isActive: boolean }) =>
    `rounded-lg px-3 py-2 text-sm font-semibold ${isActive ? 'bg-blue-100 text-blue-900' : 'text-slate-700'}`
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div
        role="status"
        data-testid="sandbox-banner"
        className="sticky top-0 z-20 bg-amber-400 px-4 py-2 text-center text-sm font-bold text-slate-900"
      >
        {t('banner.text')}
      </div>
      <header className={`mx-auto flex ${width} items-start justify-between gap-3 px-4 pb-2 pt-5`}>
        <Link to="/" className="block">
          <h1 className="text-2xl font-bold">{t('app.title')}</h1>
          <p className="text-sm text-slate-600">{t('app.tagline')}</p>
        </Link>
        <button
          type="button"
          onClick={toggle}
          className="min-h-11 shrink-0 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold"
        >
          {t('lang.toggle')}
        </button>
      </header>
      <nav className={`mx-auto flex ${width} gap-1 px-4 pb-3`} aria-label="main">
        <NavLink to="/" end className={link}>
          {t('nav.check')}
        </NavLink>
        <NavLink to="/analyst" className={link}>
          {t('nav.analyst')}
        </NavLink>
        <NavLink to="/metrics" className={link}>
          {t('nav.metrics')}
        </NavLink>
        <NavLink to="/demo" className={link}>
          {t('nav.demo')}
        </NavLink>
      </nav>
      <main className={`mx-auto ${width} space-y-4 px-4 pb-16`}>
        {backend !== 'ready' && (
          <p role="status" data-testid="backend-status" className="rounded-xl border border-sky-300 bg-sky-50 p-3 text-sm">
            {t(backend === 'waking' ? 'backend.waking' : 'backend.down')}
          </p>
        )}
        <Outlet />
      </main>
    </div>
  )
}
