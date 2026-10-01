import type { Schemas } from '../api/client'
import { useI18n } from '../i18n/useI18n'

const SYMBOL: Record<string, string> = { risk: '▲', protective: '▼', neutral: '•' }

/** Plain-language reasons in the chosen language. The text comes from fixed server templates. */
export function ReasonList({ reasons }: { reasons: Schemas['ReasonOut'][] }) {
  const { lang } = useI18n()
  return (
    <ul className="space-y-2">
      {reasons.map((reason) => (
        <li key={reason.key + reason.text_en} className="flex gap-3 text-base">
          <span
            aria-hidden="true"
            className={
              reason.direction === 'risk'
                ? 'text-red-700'
                : reason.direction === 'protective'
                  ? 'text-emerald-700'
                  : 'text-sky-700'
            }
          >
            {SYMBOL[reason.direction] ?? '•'}
          </span>
          <span>{lang === 'bn' ? reason.text_bn : reason.text_en}</span>
        </li>
      ))}
    </ul>
  )
}
