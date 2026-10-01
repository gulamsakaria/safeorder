import { createContext, useContext } from 'react'
import type { Lang } from './strings'

const BN_DIGITS = '০১২৩৪৫৬৭৮৯'

/** Western digits to Bengali digits when the Bangla UI is shown. */
export function localizeDigits(text: string, lang: Lang): string {
  return lang === 'bn' ? text.replace(/\d/g, (d) => BN_DIGITS[Number(d)]) : text
}

export interface I18n {
  lang: Lang
  setLang: (lang: Lang) => void
  toggle: () => void
  /** Translate a key; unknown keys fall back to English, then to the key itself. */
  t: (key: string, vars?: Record<string, string | number>) => string
  /** Has a translation for this key (used for server-driven keys such as event names). */
  has: (key: string) => boolean
  num: (value: number | string) => string
}

export const I18nContext = createContext<I18n | null>(null)

export function useI18n(): I18n {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used inside I18nProvider')
  return ctx
}
