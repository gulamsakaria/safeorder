import type { Schemas } from '../api/client'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime } from '../lib/format'
import { BandBadge } from './BandBadge'
import { ReasonList } from './ReasonList'
import { Card } from './ui'

const PERCENT = 100

export function RouteBadge({ route }: { route: string | null }) {
  const { t } = useI18n()
  const key = route ?? 'NOT_ANALYZED'
  const style =
    key === 'HUMAN_REVIEW'
      ? 'border-red-400 bg-red-50 text-red-900'
      : key === 'FAST_LANE_CONFIRM'
        ? 'border-emerald-400 bg-emerald-50 text-emerald-900'
        : 'border-slate-400 bg-slate-100 text-slate-800'
  const symbol = key === 'HUMAN_REVIEW' ? '👤' : key === 'FAST_LANE_CONFIRM' ? '⚡' : '…'
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-bold ${style}`}>
      <span aria-hidden="true">{symbol}</span>
      {t(`analyst.route.${key}`)}
    </span>
  )
}

export function FlagChips({ flags }: { flags: string[] }) {
  const { t, has } = useI18n()
  if (flags.length === 0) return <span className="text-sm text-slate-600">{t('case.flags.none')}</span>
  return (
    <ul className="flex flex-wrap gap-2" aria-label={t('case.flags')}>
      {flags.map((flag) => (
        <li
          key={flag}
          className="rounded-lg border border-amber-400 bg-amber-50 px-2 py-1 text-sm font-semibold text-amber-900"
        >
          <span aria-hidden="true">⚑ </span>
          {has(`flag.${flag}`) ? t(`flag.${flag}`) : flag}
        </li>
      ))}
    </ul>
  )
}

/** The four class probabilities as labelled bars. A suggestion for the analyst, never a verdict. */
export function ProbabilityBars({ probs }: { probs: Record<string, number> }) {
  const { t, num } = useI18n()
  const rows = Object.entries(probs).sort((a, b) => b[1] - a[1])
  return (
    <ul className="space-y-2" aria-label={t('case.probs')}>
      {rows.map(([name, p], index) => (
        <li key={name}>
          <div className="flex justify-between text-sm">
            <span className={index === 0 ? 'font-bold' : ''}>{t(`class.${name}`)}</span>
            <span className="tabular-nums">{num(Math.round(p * PERCENT))}%</span>
          </div>
          <div className="h-3 rounded-full bg-slate-200">
            <div
              className={`h-3 rounded-full ${index === 0 ? 'bg-blue-700' : 'bg-slate-500'}`}
              style={{ width: `${Math.round(p * PERCENT)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function SnapshotCard({
  snapshot,
  heading,
}: {
  snapshot: Schemas['SnapshotOut']
  heading: string
}) {
  const { t, num, lang } = useI18n()
  return (
    <Card className="space-y-2" aria-label={heading}>
      <p className="text-sm font-bold uppercase text-slate-600">{heading}</p>
      <BandBadge band={snapshot.band} />
      <p className="text-3xl font-bold tabular-nums" data-testid="snapshot-score">
        {snapshot.score === null ? (
          <span className="text-base font-semibold text-slate-600">{t('score.hidden')}</span>
        ) : (
          num(snapshot.score)
        )}
      </p>
      <p className="text-xs text-slate-600">
        {t(`score.trigger.${snapshot.trigger}`)} · {formatDateTime(snapshot.created_at, lang)}
      </p>
      <ReasonList reasons={snapshot.reasons} />
    </Card>
  )
}

/** Score update view: the seller's trust snapshot before and after a decision. */
export function TrustChangeView({ change }: { change: Schemas['TrustChange'] }) {
  const { t, num } = useI18n()
  const { before, after } = change
  let delta: string
  if (before.score === null || after.score === null) delta = t('score.hidden')
  else if (after.score === before.score) delta = t('score.unchanged')
  else {
    const diff = after.score - before.score
    delta = `${diff < 0 ? '▼ −' : '▲ +'}${num(Math.abs(diff))}`
  }
  return (
    <div className="space-y-3" aria-label={t('score.title')}>
      <h3 className="text-lg font-bold">{t('score.title')}</h3>
      <div className="grid gap-3 md:grid-cols-2">
        <SnapshotCard snapshot={before} heading={t('score.before')} />
        <SnapshotCard snapshot={after} heading={t('score.after')} />
      </div>
      <p className="text-lg font-bold" data-testid="score-change">
        {t('score.change')}: {delta}
      </p>
    </div>
  )
}
