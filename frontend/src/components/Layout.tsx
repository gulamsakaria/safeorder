import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useBackendStatus } from '../api/backendStatus'
import { useI18n } from '../i18n/useI18n'
import { Scene3D } from './Scene3D'

const TILT_DEGREES = 7
const TILT_TARGET = 'main > .so-card'

/** Cards lean towards the pointer. One delegated listener, so re-renders cost nothing. */
function useCardTilt() {
  useEffect(() => {
    if (!window.matchMedia?.('(hover: hover)').matches) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let current: HTMLElement | null = null
    const reset = (el: HTMLElement) => {
      el.style.setProperty('--rx', '0deg')
      el.style.setProperty('--ry', '0deg')
    }
    const onMove = (e: PointerEvent) => {
      const card = (e.target as Element | null)?.closest<HTMLElement>(TILT_TARGET) ?? null
      if (current && current !== card) reset(current)
      current = card
      if (!card) return
      const r = card.getBoundingClientRect()
      const x = (e.clientX - r.left) / r.width
      const y = (e.clientY - r.top) / r.height
      card.style.setProperty('--ry', `${((x - 0.5) * TILT_DEGREES).toFixed(2)}deg`)
      card.style.setProperty('--rx', `${((0.5 - y) * TILT_DEGREES).toFixed(2)}deg`)
      card.style.setProperty('--mx', `${(x * 100).toFixed(1)}%`)
      card.style.setProperty('--my', `${(y * 100).toFixed(1)}%`)
    }
    document.addEventListener('pointermove', onMove, { passive: true })
    return () => document.removeEventListener('pointermove', onMove)
  }, [])
}

/** The sandbox banner is part of the layout, so no screen can ever hide it. */
export function Layout() {
  const { t, toggle } = useI18n()
  const backend = useBackendStatus()
  useCardTilt()
  // the analyst console needs room for side-by-side columns; the buyer screens stay phone-sized
  const path = useLocation().pathname
  const wide = path.startsWith('/analyst') || path.startsWith('/metrics')
  const width = wide ? 'max-w-5xl' : 'max-w-xl'
  const link = ({ isActive }: { isActive: boolean }) =>
    `so-tab rounded-lg px-3 py-2 text-sm font-semibold ${isActive ? 'text-white' : ''}`
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
        <header className={`so-rise mx-auto flex ${width} items-start justify-between gap-3 px-4 pb-2 pt-5`}>
          <Link to="/" className="block">
            <h1 className="so-title text-3xl font-bold">{t('app.title')}</h1>
            <p className="text-sm text-indigo-200">{t('app.tagline')}</p>
          </Link>
          <button
            type="button"
            onClick={toggle}
            className="so-glass-btn min-h-11 shrink-0 rounded-lg px-4 text-sm font-semibold"
          >
            {t('lang.toggle')}
          </button>
        </header>
        <nav className={`so-rise mx-auto flex ${width} flex-wrap gap-1 px-4 pb-3`} aria-label="main">
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
        <main className={`so-stagger mx-auto ${width} space-y-4 px-4 pb-16`}>
          {backend !== 'ready' && (
            <p role="status" data-testid="backend-status" className="rounded-xl border border-sky-300 bg-sky-50 p-3 text-sm text-slate-900">
              {t(backend === 'waking' ? 'backend.waking' : 'backend.down')}
            </p>
          )}
          <Outlet />
        </main>
      </div>
    </>
  )
}
