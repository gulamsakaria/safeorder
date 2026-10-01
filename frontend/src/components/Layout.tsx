import { Link, NavLink, Outlet } from 'react-router-dom'
import { useI18n } from '../i18n/useI18n'

/** The sandbox banner is part of the layout, so no screen can ever hide it. */
export function Layout() {
  const { t, toggle } = useI18n()
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
      <header className="mx-auto flex max-w-xl items-start justify-between gap-3 px-4 pb-2 pt-5">
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
      <nav className="mx-auto flex max-w-xl gap-1 px-4 pb-3" aria-label="main">
        <NavLink to="/" end className={link}>
          {t('nav.check')}
        </NavLink>
        <NavLink to="/demo" className={link}>
          {t('nav.demo')}
        </NavLink>
      </nav>
      <main className="mx-auto max-w-xl space-y-4 px-4 pb-16">
        <Outlet />
      </main>
    </div>
  )
}
