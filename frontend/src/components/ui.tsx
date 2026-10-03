import type { ButtonHTMLAttributes, ReactNode, TextareaHTMLAttributes, InputHTMLAttributes } from 'react'

const TOUCH_TARGET = 'min-h-12'

export function Card({
  children,
  className = '',
  tone = 'plain',
  ...rest
}: {
  children: ReactNode
  className?: string
  tone?: 'plain' | 'good' | 'warn' | 'danger' | 'info'
} & React.HTMLAttributes<HTMLElement>) {
  const tones = {
    plain: 'border-white/60 bg-white/97',
    good: 'border-emerald-300 bg-emerald-50/97',
    warn: 'border-amber-300 bg-amber-50/97',
    danger: 'border-red-300 bg-red-50/97',
    info: 'border-sky-300 bg-sky-50/97',
  }
  return (
    <section className={`so-card rounded-2xl border p-4 ${tones[tone]} ${className}`} {...rest}>
      {children}
    </section>
  )
}

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: { variant?: 'primary' | 'secondary' | 'danger' } & ButtonHTMLAttributes<HTMLButtonElement>) {
  const variants = {
    primary: 'so-btn-primary text-white disabled:text-slate-500',
    secondary:
      'so-btn-lift border border-slate-300 bg-white text-slate-900 hover:bg-slate-50 disabled:text-slate-400',
    danger: 'so-btn-lift bg-red-700 text-white hover:bg-red-800 disabled:bg-slate-300 disabled:text-slate-500',
  }
  return (
    <button
      type="button"
      className={`${TOUCH_TARGET} rounded-xl px-5 py-2 text-base font-semibold ${variants[variant]} ${className}`}
      {...props}
    />
  )
}

export function Label({ htmlFor, children }: { htmlFor: string; children: ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-1 block text-sm font-semibold text-slate-800">
      {children}
    </label>
  )
}

const FIELD =
  'so-field w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-base text-slate-900 placeholder:text-slate-400'

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${TOUCH_TARGET} ${FIELD}`} {...props} />
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`${FIELD} min-h-28`} {...props} />
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${TOUCH_TARGET} ${FIELD}`} {...props} />
}

export function Spinner({ label }: { label: string }) {
  return (
    <p role="status" className="py-8 text-center text-slate-600">
      {label}
    </p>
  )
}
