import { useState } from 'react'
import { type Lang, strings } from './i18n'

export default function App() {
  const [lang, setLang] = useState<Lang>('bn')
  const t = strings[lang]

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div
        role="status"
        className="sticky top-0 z-10 bg-amber-400 px-4 py-2 text-center text-sm font-semibold"
      >
        {t.banner}
      </div>
      <header className="mx-auto flex max-w-3xl items-center justify-between px-4 py-6">
        <div>
          <h1 className="text-2xl font-bold">{t.title}</h1>
          <p className="text-slate-600">{t.subtitle}</p>
        </div>
        <button
          type="button"
          className="min-h-11 rounded-lg border border-slate-300 px-4"
          onClick={() => setLang(lang === 'bn' ? 'en' : 'bn')}
        >
          {t.toggle}
        </button>
      </header>
    </div>
  )
}
