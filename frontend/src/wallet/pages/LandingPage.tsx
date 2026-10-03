import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useI18n } from '../../i18n/useI18n'
import { useAuth } from '../AuthProvider'
import { Icons } from '../icons'

const REPO = 'https://github.com/gulamsakaria/safeorder'
const NAV = ['problem', 'how', 'ideas', 'app', 'roles', 'tech', 'safety', 'faq'] as const
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
const SHOTS = ['home', 'pay', 'seller', 'order'] as const
const ROLES = ['buyer', 'seller', 'admin'] as const
const TECH = ['trust', 'analyzer', 'money'] as const
const SAFETY = [1, 2, 3, 4, 5, 6] as const
const FAQ = [1, 2, 3, 4, 5, 6, 7, 8] as const
const LATER = [1, 2, 3, 4, 5] as const

function go(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function Section({ id, title, sub, children }: { id: string; title: string; sub?: string; children: ReactNode }) {
  return (
    <section id={id} className="mx-auto max-w-6xl scroll-mt-28 px-4 pt-16">
      <h2 className="text-2xl font-extrabold text-white sm:text-3xl">{title}</h2>
      {sub && <p className="mt-2 max-w-3xl text-indigo-100">{sub}</p>}
      <div className="mt-6">{children}</div>
    </section>
  )
}

function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-white/60 bg-white p-5 text-slate-900 shadow-xl ${className}`}>{children}</div>
}

function Phone({ src, caption }: { src: string; caption?: string }) {
  return (
    <figure className="mx-auto w-full max-w-[250px]">
      <div className="overflow-hidden rounded-[2rem] border-[6px] border-slate-950 bg-slate-950 shadow-2xl">
        <img src={src} alt={caption ?? ''} width={780} height={1560} loading="lazy" className="block h-auto w-full" />
      </div>
      {caption && <figcaption className="mt-3 text-center text-sm font-semibold text-indigo-100">{caption}</figcaption>}
    </figure>
  )
}

/** The public front page: what SafeOrder is, why it is needed, how it works, what is new. */
export function LandingPage() {
  const { t, lang, toggle, num } = useI18n()
  const { me } = useAuth()
  const [menu, setMenu] = useState(false)
  const openTo = me ? '/home' : '/welcome'
  const jump = (id: string) => {
    setMenu(false)
    // scroll after the open menu has been removed, or the target moves while it scrolls
    window.setTimeout(() => go(id), 60)
  }

  return (
    <div className="so-shell min-h-screen pb-16">
      <div
        role="status"
        data-testid="sandbox-banner"
        className="so-banner sticky top-0 z-40 px-4 py-2 text-center text-sm font-bold text-slate-900"
      >
        {t('banner.text')}
      </div>

      {/* menu */}
      <nav aria-label="main" className="sticky top-[37px] z-30 border-b border-white/10 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-2">
          <button type="button" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="text-left">
            <span className="so-title block whitespace-nowrap text-xl font-extrabold">{t('w.brand')}</span>
          </button>
          <div className="hidden items-center gap-1 lg:flex">
            {NAV.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => jump(id)}
                className="min-h-10 whitespace-nowrap rounded-lg px-2.5 text-sm font-semibold text-indigo-100 hover:bg-white/10"
              >
                {t(`lp.nav.${id}`)}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <button type="button" onClick={toggle} className="so-glass-btn min-h-10 rounded-lg px-3 text-sm font-semibold">
              {t('lang.toggle')}
            </button>
            <Link to={openTo} className="so-btn-primary hidden min-h-10 items-center whitespace-nowrap rounded-lg px-4 text-sm font-bold text-white sm:inline-flex">
              {me ? t('lp.cta.open') : t('lp.cta.signin')}
            </Link>
            <button
              type="button"
              aria-label={t('lp.nav.menu')}
              aria-expanded={menu}
              onClick={() => setMenu((v) => !v)}
              className="so-glass-btn grid min-h-10 w-10 place-items-center rounded-lg text-xl lg:hidden"
            >
              {menu ? '✕' : '☰'}
            </button>
          </div>
        </div>
        {menu && (
          <div className="border-t border-white/10 bg-slate-950 px-4 pb-4 lg:hidden">
            <div className="mx-auto grid max-w-6xl gap-1 pt-2">
              {NAV.map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => jump(id)}
                  className="min-h-11 rounded-lg px-3 text-left text-base font-semibold text-indigo-100 hover:bg-white/10"
                >
                  {t(`lp.nav.${id}`)}
                </button>
              ))}
              <Link to="/guide" className="min-h-11 rounded-lg px-3 py-2.5 text-base font-semibold text-indigo-100 hover:bg-white/10">
                {t('lp.cta.guide')}
              </Link>
              <Link to={openTo} className="so-btn-primary mt-2 grid min-h-12 place-items-center rounded-xl font-bold text-white">
                {me ? t('lp.cta.open') : t('lp.cta.signin')}
              </Link>
            </div>
          </div>
        )}
      </nav>

      {/* hero */}
      <header className="mx-auto grid max-w-6xl items-center gap-10 px-4 pt-12 lg:grid-cols-[1.25fr_1fr]">
        <div>
          <span className="inline-block rounded-full border border-white/30 bg-white/10 px-4 py-1 text-xs font-bold text-indigo-100">
            {t('lp.badge')}
          </span>
          <h1 className="mt-4 text-4xl font-extrabold leading-tight text-white sm:text-5xl">{t('lp.hero.title')}</h1>
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
          <ul className="mt-8 grid max-w-xl gap-2 text-sm text-indigo-100 sm:grid-cols-2">
            {[1, 2, 3, 4].map((i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden="true" className="text-emerald-300">✓</span>
                {t(`lp.hero.point.${i}`)}
              </li>
            ))}
          </ul>
        </div>
        <Phone src={`./shots/${lang}_home.webp`} />
      </header>

      <Section id="problem" title={t('lp.problem.title')} sub={t('lp.problem.sub')}>
        <div className="grid gap-4 sm:grid-cols-3">
          {PROBLEMS.map((p) => (
            <Card key={p}>
              <h3 className="font-extrabold">{t(`lp.${p}.title`)}</h3>
              <p className="mt-2 text-sm text-slate-700">{t(`lp.${p}.body`)}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section id="how" title={t('lp.how.title')} sub={t('lp.how.sub')}>
        <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((n) => (
            <li key={n}>
              <Card className="h-full">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-indigo-700 text-sm font-extrabold text-white">{num(n)}</span>
                <h3 className="mt-3 font-extrabold">{t(`lp.step${n}.title`)}</h3>
                <p className="mt-1 text-sm text-slate-700">{t(`lp.step${n}.body`)}</p>
              </Card>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="ideas" title={t('lp.ideas.title')} sub={t('lp.ideas.sub')}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {IDEAS.map((idea) => (
            <Card key={idea.key}>
              <span className={`grid h-12 w-12 place-items-center rounded-2xl ${idea.tone}`}>{idea.icon}</span>
              <h3 className="mt-3 font-extrabold">{t(`lp.idea.${idea.key}.title`)}</h3>
              <p className="mt-1 text-sm text-slate-700">{t(`lp.idea.${idea.key}.body`)}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section id="app" title={t('lp.app.title')} sub={t('lp.app.sub')}>
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {SHOTS.map((s) => (
            <Phone key={s} src={`./shots/${lang}_${s}.webp`} caption={t(`lp.app.${s}`)} />
          ))}
        </div>
      </Section>

      <Section id="roles" title={t('lp.roles.title')} sub={t('lp.roles.sub')}>
        <div className="grid gap-4 sm:grid-cols-3">
          {ROLES.map((r) => (
            <Card key={r}>
              <h3 className="text-lg font-extrabold">{t(`lp.role.${r}.title`)}</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                {[1, 2, 3].map((i) => (
                  <li key={i}>{t(`lp.role.${r}.${i}`)}</li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      </Section>

      <Section id="tech" title={t('lp.tech.title')} sub={t('lp.tech.sub')}>
        <div className="grid gap-4 lg:grid-cols-3">
          {TECH.map((k) => (
            <Card key={k}>
              <h3 className="text-lg font-extrabold">{t(`lp.tech.${k}.title`)}</h3>
              <ul className="mt-2 space-y-2 text-sm text-slate-700">
                {[1, 2, 3, 4].map((i) => (
                  <li key={i} className="flex gap-2">
                    <span aria-hidden="true" className="text-indigo-700">•</span>
                    <span>{t(`lp.tech.${k}.${i}`)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
        <p className="mt-4 text-sm text-indigo-100">{t('lp.tech.note')}</p>
      </Section>

      <Section id="safety" title={t('lp.safety.title')} sub={t('lp.safety.sub')}>
        <Card className="grid gap-3 sm:grid-cols-2">
          {SAFETY.map((i) => (
            <p key={i} className="flex gap-3 text-sm">
              <span aria-hidden="true" className="mt-0.5 text-emerald-700">✓</span>
              <span>{t(`lp.safety.${i}`)}</span>
            </p>
          ))}
        </Card>
        <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm font-semibold text-amber-950">{t('lp.honest')}</p>
      </Section>

      <Section id="faq" title={t('lp.faq.title')}>
        <div className="space-y-3">
          {FAQ.map((i) => (
            <details key={i} className="group rounded-2xl border border-white/60 bg-white p-4 text-slate-900 shadow-lg">
              <summary className="cursor-pointer list-none font-bold">
                <span className="mr-2 text-indigo-700 group-open:hidden">+</span>
                <span className="mr-2 hidden text-indigo-700 group-open:inline">−</span>
                {t(`lp.faq.q${i}`)}
              </summary>
              <p className="mt-2 text-sm text-slate-700">{t(`lp.faq.a${i}`)}</p>
            </details>
          ))}
        </div>
      </Section>

      <Section id="later" title={t('lp.later.title')} sub={t('lp.later.sub')}>
        <Card>
          <ul className="grid gap-2 text-sm sm:grid-cols-2">
            {LATER.map((i) => (
              <li key={i} className="flex gap-2">
                <span aria-hidden="true" className="text-amber-700">○</span>
                {t(`lp.later.${i}`)}
              </li>
            ))}
          </ul>
        </Card>
      </Section>

      <div className="mx-auto mt-16 max-w-6xl px-4">
        <div className="rounded-3xl border border-white/60 bg-white p-8 text-center text-slate-900 shadow-2xl">
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

      <footer className="mx-auto mt-12 max-w-6xl border-t border-white/10 px-4 pt-6 text-sm text-indigo-200">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="so-title text-lg font-extrabold">{t('w.brand')}</p>
          <div className="flex flex-wrap gap-4 font-semibold">
            <Link to="/guide" className="hover:text-white">{t('lp.cta.guide')}</Link>
            <Link to="/metrics" className="hover:text-white">{t('lp.cta.metrics')}</Link>
            <a href={REPO} target="_blank" rel="noreferrer" className="hover:text-white">{t('lp.footer.code')}</a>
            <Link to={openTo} className="hover:text-white">{me ? t('lp.cta.open') : t('lp.cta.signin')}</Link>
          </div>
        </div>
        <p className="mt-4 text-xs">{t('lp.footer.1')}</p>
        <p className="mt-1 text-xs">{t('lp.footer.2')}</p>
      </footer>
    </div>
  )
}
