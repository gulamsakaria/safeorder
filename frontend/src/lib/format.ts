import type { Lang } from '../i18n/strings'
import { localizeDigits } from '../i18n/useI18n'

const MS_PER_SECOND = 1000
const SECONDS_PER_MINUTE = 60
const SECONDS_PER_HOUR = 3600
const SECONDS_PER_DAY = 86400

/** "2 din 3 ghonta" style countdown; returns null when the time is up. */
export function formatRemaining(
  ms: number,
  lang: Lang,
  units: { d: string; h: string; m: string; s: string },
): string | null {
  if (ms <= 0) return null
  const total = Math.floor(ms / MS_PER_SECOND)
  const days = Math.floor(total / SECONDS_PER_DAY)
  const hours = Math.floor((total % SECONDS_PER_DAY) / SECONDS_PER_HOUR)
  const minutes = Math.floor((total % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE)
  const seconds = total % SECONDS_PER_MINUTE
  const parts: string[] = []
  if (days) parts.push(`${days} ${units.d}`)
  if (days || hours) parts.push(`${hours} ${units.h}`)
  if (!days) parts.push(`${minutes} ${units.m}`)
  if (!days && !hours) parts.push(`${seconds} ${units.s}`)
  return localizeDigits(parts.join(' '), lang)
}

export function formatDateTime(iso: string | null | undefined, lang: Lang): string {
  if (!iso) return '-'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '-'
  const text = new Intl.DateTimeFormat(lang === 'bn' ? 'bn-BD' : 'en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(date)
  return `${localizeDigits(text, lang)} UTC`
}

export function formatMoney(amount: number, lang: Lang, unit: string): string {
  return `${localizeDigits(amount.toLocaleString('en-US'), lang)} ${unit}`
}
