import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ApiProblem } from '../api/client'
import { useI18n } from '../i18n/useI18n'
import { Card } from '../components/ui'

/** "৳ 1,500" (Bengali digits in the Bangla UI). */
export function useMoney() {
  const { num } = useI18n()
  return (amount: number) => `৳ ${num(amount.toLocaleString('en-US'))}`
}

/** A translated message for an API error. Server messages are English, so known codes are mapped. */
export function Problem({ error }: { error: ApiProblem }) {
  const { t, has } = useI18n()
  const key = `w.err.${error.code}`
  const generic = has(`common.error.${error.code}`) ? t(`common.error.${error.code}`) : null
  return (
    <p role="alert" className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm font-semibold text-red-900">
      {has(key) ? t(key) : (generic ?? t('common.error.generic'))}
    </p>
  )
}

const STATUS_STYLE: Record<string, string> = {
  HELD: 'bg-amber-100 text-amber-900 border-amber-400',
  DELIVERED: 'bg-sky-100 text-sky-900 border-sky-400',
  DISPUTABLE: 'bg-amber-100 text-amber-900 border-amber-400',
  DISPUTED: 'bg-red-100 text-red-900 border-red-400',
  ESCALATED: 'bg-red-100 text-red-900 border-red-400',
  RELEASED: 'bg-emerald-100 text-emerald-900 border-emerald-400',
  REFUNDED: 'bg-slate-100 text-slate-800 border-slate-400',
}

export function StatusChip({ status }: { status: string }) {
  const { t, has } = useI18n()
  const key = `w.status.${status}`
  return (
    <span
      className={`inline-block rounded-full border px-3 py-0.5 text-xs font-bold ${STATUS_STYLE[status] ?? 'bg-slate-100 text-slate-800 border-slate-300'}`}
    >
      {has(key) ? t(key) : status}
    </span>
  )
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T
  onChange: (value: T) => void
  options: { value: T; label: string }[]
}) {
  return (
    <div role="tablist" className="grid auto-cols-fr grid-flow-col gap-1 rounded-2xl bg-slate-200 p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={`min-h-11 rounded-xl px-3 text-sm font-bold transition ${
            value === o.value ? 'bg-white text-indigo-800 shadow' : 'text-slate-600'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function PageTitle({ children, back }: { children: ReactNode; back?: string }) {
  const { t } = useI18n()
  return (
    <div className="flex items-center gap-3 px-1 pt-1">
      {back && (
        <Link to={back} className="rounded-lg px-2 py-1 text-sm font-semibold text-indigo-200" aria-label={t('w.back')}>
          ←
        </Link>
      )}
      <h2 className="text-xl font-bold text-white">{children}</h2>
    </div>
  )
}

/** A number the user must copy (the order number): large, with a copy button. */
export function CopyBox({ text }: { text: string }) {
  const { t } = useI18n()
  const [copied, setCopied] = useState(false)
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border-2 border-dashed border-indigo-300 bg-indigo-50 p-3">
      <span className="text-2xl font-extrabold tracking-wide text-indigo-900">{text}</span>
      <button
        type="button"
        className="min-h-11 rounded-lg bg-indigo-700 px-4 text-sm font-bold text-white"
        onClick={() => {
          void navigator.clipboard?.writeText(text).then(() => setCopied(true))
        }}
      >
        {copied ? t('w.copied') : t('w.copy')}
      </button>
    </div>
  )
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' | 'good' }) {
  return <Card tone={tone === 'info' ? 'info' : tone === 'warn' ? 'warn' : 'good'}>{children}</Card>
}

export function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5 text-sm">
      <span className="text-slate-600">{label}</span>
      <span className="text-right font-semibold text-slate-900">{children}</span>
    </div>
  )
}

/** The five-digit PIN field: digits only, hidden. */
export function PinField({
  id,
  value,
  onChange,
  label,
}: {
  id: string
  value: string
  onChange: (v: string) => void
  label: string
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-semibold text-slate-800">
        {label}
      </label>
      <input
        id={id}
        type="password"
        inputMode="numeric"
        autoComplete="off"
        maxLength={5}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, '').slice(0, 5))}
        className="so-field min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-center text-xl tracking-[0.6em] text-slate-900"
      />
    </div>
  )
}
