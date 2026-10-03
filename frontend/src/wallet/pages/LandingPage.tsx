import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Scene3D } from '../../components/Scene3D'
import { useI18n } from '../../i18n/useI18n'
import { useAuth } from '../AuthProvider'
import { Icons } from '../icons'

const PROBLEMS = ['p1', 'p2', 'p3'] as const
const STEPS = [1, 2, 3, 4, 5] as const
const IDEAS: { key: string; icon: ReactNode; tone: string }[] = [
  { key: 'hold', icon: Icons.lock, tone: 'bg-indigo-100 text-indigo-700' },
  { key: 'trust', icon: Icons.shield, tone: 'bg-emerald-100 text-emerald-700' },
  { key: 'fair', icon: Icons.user, tone: 'bg-amber-100 text-amber-700' },
  { key: 'analyzer', icon: Icons.guide, tone: 'bg-violet-100 text-violet-700' },
  { key: 'proof', icon: Icons.orders, tone: 'bg-rose-100 text-rose-700' },
  { key: 'human', icon: Icons.admin, tone: 'bg-sky-100 text-sky-700' },
]
const ROLES = ['buyer', 'seller', 'admin'] as const

function Section({ id, title, sub, children }: { id?: string; title: string; sub?: string; children: ReactNode }) {
  return (
    <section id={id} className="so-rise mx-auto mt-14 max-w-5xl px-4">
      <h2 className="text-2xl font-extrabold text-white sm:text-3xl">{title}</h2>
      {sub && <p className="mt-2 max-w-3xl text-indigo-100">{sub}</p>}
      <div className="mt-6">{children}</div>
    </section>
  )
}

/** The public front page: what SafeOrder is, why it is needed, how it works, what is new. */
export function LandingPage() {
  const { t, toggle, num } = useI18n()
  const { me } = useAuth()
  const openTo = me ? '/home' : '/welcome'

  return (
    <>
      <Scene3D />
      <div className="so-shell min-h-screen pb-16">
        <div
          role="status"
          data-testid="sandbox-banner"
          className="so-banner sticky top-0 z-20 px-4 py-2 text-center text-sm font-bold text-slate-900"
        >
          {t('banner.text')}
        </div>

        <header className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 pt-5">
          <div>
            <p className="so-title text-2xl font-extrabold">{t('w.brand')}</p>
            <p className="text-xs text-indigo-200">{t('w.tagline')}</p>
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={toggle} className="so-glass-btn min-h-11 rounded-lg px-4 text-sm font-semibold">
              {t('lang.toggle')}
            </button>
            <Link to={openTo} className="so-btn-primary hidden min-h-11 items-center rounded-lg px-5 text-sm font-bold text-white sm:inline-flex">
              {me ? t('lp.cta.open') : t('lp.cta.signin')}
            </Link>
          </div>
        </header>

        {/* hero */}
        <div className="so-rise mx-auto mt-10 max-w-5xl px-4">
          <span className="inline-block rounded-full border border-white/30 bg-white/10 px-4 py-1 text-xs font-bold text-indigo-100 backdrop-blur">
            {t('lp.badge')}
          </span>
          <h1 className="mt-4 max-w-3xl text-4xl font-extrabold leading-tight text-white sm:text-5xl">{t('lp.hero.title')}</h1>
          <p className="mt-4 max-w-2xl text-lg text-indigo-100">{t('lp.hero.sub')}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to={openTo} className="so-btn-primary inline-flex min-h-12 items-center rounded-xl px-6 text-base font-bold text-white">
              {me ? t('lp.cta.open') : t('lp.cta.start')}
            </Link>
            <Link to="/guide" className="so-glass-btn inline-flex min-h-12 items-center rounded-xl px-6 text-base font-bold">
              {t('lp.cta.guide')}
            </Link>
            <Link to="/metrics" className="so-glass-btn inline-flex min-h-12 items-center rounded-xl px-6 text-base font-bold">
              {t('lp.cta.metrics')}
            </Link>
          </div>
        </div>

        {/* the problem */}
        <Section title={t('lp.problem.title')} sub={t('lp.problem.sub')}>
          <div className="grid gap-4 sm:grid-cols-3">
            {PROBLEMS.map((p) => (
              <div key={p} className="so-card rounded-2xl border border-white/60 bg-white/95 p-5">
                <h3 className="font-extrabold">{t(`lp.${p}.title`)}</h3>
                <p className="mt-2 text-sm text-slate-700">{t(`lp.${p}.body`)}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* how it works */}
        <Section id="how" title={t('lp.how.title')} sub={t('lp.how.sub')}>
          <ol className="grid gap-4 sm:grid-cols-5">
            {STEPS.map((n) => (
              <li key={n} className="so-card relative rounded-2xl border border-white/60 bg-white/95 p-4">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-indigo-700 text-sm font-extrabold text-white">{num(n)}</span>
                <h3 className="mt-3 font-extrabold">{t(`lp.step${n}.title`)}</h3>
                <p className="mt-1 text-sm text-slate-700">{t(`lp.step${n}.body`)}</p>
              </li>
            ))}
          </ol>
        </Section>

        {/* what is new */}
        <Section title={t('lp.ideas.title')} sub={t('lp.ideas.sub')}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {IDEAS.map((idea) => (
              <div key={idea.key} className="so-card rounded-2xl border border-white/60 bg-white/95 p-5">
                <span className={`grid h-12 w-12 place-items-center rounded-2xl ${idea.tone}`}>{idea.icon}</span>
                <h3 className="mt-3 font-extrabold">{t(`lp.idea.${idea.key}.title`)}</h3>
                <p className="mt-1 text-sm text-slate-700">{t(`lp.idea.${idea.key}.body`)}</p>
              </div>
            ))}
          </div>
        </Section>

        {/* roles */}
        <Section title={t('lp.roles.title')} sub={t('lp.roles.sub')}>
          <div className="grid gap-4 sm:grid-cols-3">
            {ROLES.map((r) => (
              <div key={r} className="so-card rounded-2xl border border-white/60 bg-white/95 p-5">
                <h3 className="text-lg font-extrabold">{t(`lp.role.${r}.title`)}</h3>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                  {[1, 2, 3].map((i) => (
                    <li key={i}>{t(`lp.role.${r}.${i}`)}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Section>

        {/* responsible AI */}
        <Section title={t('lp.ai.title')} sub={t('lp.ai.sub')}>
          <div className="so-card grid gap-3 rounded-2xl border border-white/60 bg-white/95 p-5 sm:grid-cols-2">
            {[1, 2, 3, 4].map((i) => (
              <p key={i} className="flex gap-3 text-sm text-slate-800">
                <span aria-hidden="true" className="mt-0.5 text-emerald-700">✓</span>
                <span>{t(`lp.ai.${i}`)}</span>
              </p>
            ))}
          </div>
          <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50/95 p-4 text-sm font-semibold text-amber-950">{t('lp.honest')}</p>
        </Section>

        {/* closing call */}
        <div className="so-rise mx-auto mt-14 max-w-5xl px-4">
          <div className="so-card rounded-3xl border border-white/60 bg-white/95 p-8 text-center">
            <h2 className="text-2xl font-extrabold">{t('lp.final.title')}</h2>
            <p className="mx-auto mt-2 max-w-xl text-slate-700">{t('lp.final.sub')}</p>
            <div className="mt-5 flex flex-wrap justify-center gap-3">
              <Link to={openTo} className="so-btn-primary inline-flex min-h-12 items-center rounded-xl px-6 font-bold text-white">
                {me ? t('lp.cta.open') : t('lp.cta.start')}
              </Link>
              <Link to="/guide" className="inline-flex min-h-12 items-center rounded-xl border border-slate-300 bg-white px-6 font-bold text-slate-900">
                {t('lp.cta.guide')}
              </Link>
            </div>
          </div>
        </div>

        <footer className="mx-auto mt-10 max-w-5xl px-4 text-center text-xs text-indigo-200">
          <p>{t('lp.footer.1')}</p>
          <p className="mt-1">{t('lp.footer.2')}</p>
        </footer>
      </div>
    </>
  )
}
