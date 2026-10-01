import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { type Lang, STRINGS } from './strings'
import { type I18n, I18nContext, localizeDigits } from './useI18n'

const STORAGE_KEY = 'safeorder.lang'

function readStoredLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'bn' || stored === 'en') return stored
  } catch {
    // storage can be blocked; Bangla is the default anyway
  }
  return 'bn'
}

export function I18nProvider({ children, initial }: { children: ReactNode; initial?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initial ?? readStoredLang())

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // ignore: the choice just will not be remembered
    }
  }, [])

  const value = useMemo<I18n>(() => {
    const t = (key: string, vars?: Record<string, string | number>) => {
      let text = STRINGS[lang][key] ?? STRINGS.en[key] ?? key
      for (const [name, v] of Object.entries(vars ?? {})) text = text.replace(`{${name}}`, String(v))
      return text
    }
    return {
      lang,
      setLang,
      toggle: () => setLang(lang === 'bn' ? 'en' : 'bn'),
      t,
      has: (key) => key in STRINGS[lang] || key in STRINGS.en,
      num: (v) => localizeDigits(String(v), lang),
    }
  }, [lang, setLang])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
