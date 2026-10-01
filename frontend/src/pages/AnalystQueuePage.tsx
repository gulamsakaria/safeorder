import { useState } from 'react'
import { Link } from 'react-router-dom'
import { calls } from '../api/calls'
import { useAsync } from '../api/hooks'
import { RouteBadge, FlagChips } from '../components/analyst'
import { ErrorNotice } from '../components/ErrorNotice'
import { Card, Label, Select, Spinner } from '../components/ui'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime, formatMoney } from '../lib/format'

const POLL_MS = 5000
const ROUTES = ['', 'HUMAN_REVIEW', 'NOT_ANALYZED', 'FAST_LANE_CONFIRM']

export function AnalystQueuePage() {
  const { t, lang } = useI18n()
  const [route, setRoute] = useState('')
  const queue = useAsync(() => calls.analystQueue(route ? { route } : {}), [route], POLL_MS)

  return (
    <>
      <Card>
        <h2 className="text-lg font-bold">{t('analyst.queue.title')}</h2>
        <p className="mb-3 text-slate-700">{t('analyst.queue.intro')}</p>
        <Label htmlFor="route-filter">{t('analyst.queue.filter')}</Label>
        <Select id="route-filter" value={route} onChange={(e) => setRoute(e.target.value)}>
          {ROUTES.map((r) => (
            <option key={r} value={r}>
              {r ? t(`analyst.route.${r}`) : t('analyst.queue.all')}
            </option>
          ))}
        </Select>
      </Card>

      {queue.loading && !queue.data && <Spinner label={t('common.loading')} />}
      {queue.error && !queue.data && <ErrorNotice error={queue.error} onRetry={queue.reload} />}

      {queue.data && queue.data.length === 0 && (
        <Card tone="info" role="status">
          <p>{t('analyst.queue.empty')}</p>
        </Card>
      )}

      <ul className="space-y-3" aria-label="queue">
        {queue.data?.map((item) => (
          <li key={item.dispute_id}>
            <Card className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-lg font-bold">
                  {item.dispute_id} · {formatMoney(item.amount_bdt, lang, t('common.bdt'))}
                </p>
                <RouteBadge route={item.route} />
              </div>
              <p className="text-sm text-slate-600">
                {item.order_id} · {t(`dispute.status.${item.status}`)} ·{' '}
                {formatDateTime(item.opened_at, lang)}
              </p>
              {item.recommendation && (
                <p className="font-semibold">{t(`rec.${item.recommendation}`)}</p>
              )}
              <FlagChips flags={item.flags} />
              <Link
                to={`/analyst/dispute/${item.dispute_id}`}
                className="inline-flex min-h-12 items-center rounded-xl bg-blue-700 px-5 font-semibold text-white"
              >
                {t('analyst.queue.open')}
              </Link>
            </Card>
          </li>
        ))}
      </ul>
    </>
  )
}
