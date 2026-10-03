import { useI18n } from '../i18n/useI18n'

type Band = 'TRUSTED' | 'CAUTION' | 'HIGH_RISK' | 'LIMITED_HISTORY'

// Colour is never the only signal: every band also has a symbol and its name.
const STYLE: Record<Band, { symbol: string; classes: string }> = {
  TRUSTED: { symbol: '✓', classes: 'bg-emerald-100 text-emerald-900 border-emerald-400' },
  CAUTION: { symbol: '!', classes: 'bg-amber-100 text-amber-900 border-amber-400' },
  HIGH_RISK: { symbol: '⚠', classes: 'bg-red-100 text-red-900 border-red-400' },
  LIMITED_HISTORY: { symbol: 'i', classes: 'bg-sky-100 text-sky-900 border-sky-400' },
}

export function BandBadge({ band }: { band: Band }) {
  const { t } = useI18n()
  const style = STYLE[band]
  return (
    <span
      className={`so-pop inline-flex items-center gap-2 rounded-full border px-4 py-1 text-lg font-bold ${style.classes}`}
    >
      <span aria-hidden="true">{style.symbol}</span>
      {t(`band.${band}`)}
    </span>
  )
}
