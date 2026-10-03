import { Link, NavLink, Navigate, Outlet, useLocation } from 'react-router-dom'
import { Scene3D } from '../components/Scene3D'
import { useI18n } from '../i18n/useI18n'
import { useAuth } from './AuthProvider'
import { Icons } from './icons'

const NAV = [
  { to: '/home', label: 'w.nav.home', icon: Icons.home },
  { to: '/account', label: 'w.nav.account', icon: Icons.wallet },
  { to: '/history', label: 'w.nav.history', icon: Icons.clock },
  { to: '/more', label: 'w.nav.more', icon: Icons.more },
] as const

/** The phone-style frame of the wallet: sandbox banner, content, and the bottom navigation. */
export function WalletShell() {
  const { t, toggle } = useI18n()
  const { me, ready } = useAuth()
  const location = useLocation()
  const signedOutArea = ['/welcome', '/guide'].includes(location.pathname)

  if (!ready) {
    return (
      <div className="so-shell grid min-h-screen place-items-center">
        <p role="status" className="text-indigo-100">
          {t('common.loading')}
        </p>
      </div>
    )
  }
  if (!me && !signedOutArea) return <Navigate to="/welcome" replace />

  return (
    <>
      <Scene3D />
      <div className="so-shell min-h-screen">
        <div
          role="status"
          data-testid="sandbox-banner"
          className="so-banner sticky top-0 z-20 px-4 py-2 text-center text-sm font-bold text-slate-900"
        >
          {t('banner.text')}
        </div>
        <div className="mx-auto max-w-md px-4 pb-32 pt-4">
          <header className="so-rise mb-3 flex items-center justify-between gap-3">
            <Link to={me ? '/home' : '/welcome'} className="block">
              <h1 className="so-title text-2xl font-bold">{t('w.brand')}</h1>
              <p className="text-xs text-indigo-200">{t('w.tagline')}</p>
            </Link>
            <button
              type="button"
              onClick={toggle}
              className="so-glass-btn min-h-11 shrink-0 rounded-lg px-4 text-sm font-semibold"
            >
              {t('lang.toggle')}
            </button>
          </header>
          <main className="so-stagger space-y-4">
            <Outlet />
          </main>
        </div>

        {me && (
          <nav
            aria-label="main"
            className="fixed inset-x-0 bottom-0 z-30 border-t border-white/20 bg-white/95 backdrop-blur"
          >
            <div className="mx-auto grid max-w-md grid-cols-5 items-end px-2 pb-2 pt-1">
              {NAV.slice(0, 2).map((item) => (
                <NavItem key={item.to} to={item.to} label={item.label} icon={item.icon} />
              ))}
              <Link
                to="/pay"
                aria-label={t('w.nav.pay')}
                className="so-btn-primary mx-auto -mt-7 grid h-16 w-16 place-items-center rounded-full text-white ring-4 ring-white"
              >
                {Icons.scan}
              </Link>
              {NAV.slice(2).map((item) => (
                <NavItem key={item.to} to={item.to} label={item.label} icon={item.icon} />
              ))}
            </div>
          </nav>
        )}
      </div>
    </>
  )
}

function NavItem({ to, label, icon }: { to: string; label: string; icon: React.ReactNode }) {
  const { t } = useI18n()
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-bold ${
          isActive ? 'text-indigo-700' : 'text-slate-500'
        }`
      }
    >
      {icon}
      {t(label)}
    </NavLink>
  )
}
