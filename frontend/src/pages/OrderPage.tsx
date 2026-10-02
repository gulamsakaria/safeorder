import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { calls } from '../api/calls'
import { useAction, useAsync } from '../api/hooks'
import { Countdown } from '../components/Countdown'
import { ErrorNotice } from '../components/ErrorNotice'
import { Timeline } from '../components/Timeline'
import { Button, Card, Label, Spinner, TextInput } from '../components/ui'
import { useI18n } from '../i18n/useI18n'
import { recallCode } from '../lib/codeStore'
import { formatMoney } from '../lib/format'

const POLL_MS = 4000
const CONFIRMED_EVENT = 'DELIVERY_CODE_CONFIRMED'

export function OrderPage() {
  const { id = '' } = useParams()
  const { t, lang, num } = useI18n()
  const navigate = useNavigate()
  const order = useAsync(() => calls.getOrder(id), [id], POLL_MS)
  const [code, setCode] = useState('')
  const confirm = useAction(async () => {
    await calls.confirmDelivery(id, code.trim())
    setCode('')
    order.reload()
  })

  if (order.loading && !order.data) return <Spinner label={t('common.loading')} />
  if (order.error && !order.data) return <ErrorNotice error={order.error} onRetry={order.reload} />
  const o = order.data
  if (!o) return null

  const sandboxCode = recallCode(o.id)
  const codeDone = o.timeline.some((e) => e.event === CONFIRMED_EVENT)
  const canConfirm = (o.status === 'HELD' || o.status === 'DELIVERED') && !codeDone
  const finished = o.status === 'RELEASED' || o.status === 'REFUNDED'

  return (
    <>
      <Card className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-bold">{t('order.title')}</h2>
          <Button variant="secondary" className="min-h-10 px-3 text-sm" onClick={order.reload}>
            {t('order.refresh')}
          </Button>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-base">
          <dt className="text-slate-600">{t('order.number')}</dt>
          <dd className="font-semibold">{o.id}</dd>
          <dt className="text-slate-600">{t('order.amount')}</dt>
          <dd className="font-semibold">{formatMoney(o.amount_bdt, lang, t('common.bdt'))}</dd>
          <dt className="text-slate-600">{t('order.seller')}</dt>
          <dd>{o.seller_id}</dd>
          <dt className="text-slate-600">{t('order.status')}</dt>
          <dd className="font-bold" data-testid="order-status">
            {t(`status.${o.status}`)}
          </dd>
          <dt className="text-slate-600">{t('order.courier')}</dt>
          <dd data-testid="courier-status">{t(`courier.${o.courier_status}`)}</dd>
        </dl>
      </Card>

      {o.status === 'HELD' && (
        <Card tone="good">
          <p>{t('order.held')}</p>
        </Card>
      )}

      {finished && (
        <Card tone={o.status === 'REFUNDED' ? 'good' : 'info'} role="status">
          <p className="font-bold">{t(`order.done.${o.status}`)}</p>
        </Card>
      )}

      {sandboxCode && !finished && (
        <Card tone="warn" aria-label="delivery-code">
          <p className="font-bold">{t('order.code.title')}</p>
          <p className="text-3xl font-bold tracking-widest tabular-nums" data-testid="sandbox-code">
            {num(sandboxCode)}
          </p>
          <p className="text-sm">{t('order.code.sandbox')}</p>
        </Card>
      )}

      {canConfirm && (
        <Card>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (code.trim()) void confirm.run()
            }}
          >
            <Label htmlFor="delivery-code">{t('order.code.enter')}</Label>
            <TextInput
              id="delivery-code"
              inputMode="numeric"
              value={code}
              maxLength={20}
              placeholder={t('order.code.placeholder')}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            />
            {confirm.error && <ErrorNotice error={confirm.error} />}
            <Button type="submit" disabled={!code.trim() || confirm.pending}>
              {t('order.code.confirm')}
            </Button>
          </form>
        </Card>
      )}

      {o.status === 'DELIVERED' && o.hold_until && (
        <Card aria-label="hold-timer">
          <p className="font-bold">{t('order.hold.title')}</p>
          <p className="text-sm text-slate-600">{t('order.hold.explain')}</p>
          <p className="mt-2">
            {t('order.hold.remaining')}:{' '}
            <Countdown
              targetIso={o.hold_until}
              serverTimeIso={o.server_time}
              endedText={t('order.hold.ended')}
            />
          </p>
        </Card>
      )}

      {o.dispute_ids.length > 0 ? (
        <Card tone="warn">
          <p className="mb-2 font-bold">{t('order.report.disputed')}</p>
          <Link
            to={`/dispute/${o.dispute_ids[0]}`}
            className="inline-flex min-h-12 items-center rounded-xl bg-blue-700 px-5 font-semibold text-white"
          >
            {t('order.dispute.open')}
          </Link>
        </Card>
      ) : (
        o.can_report_problem && (
          <Button variant="danger" className="w-full" onClick={() => navigate(`/order/${o.id}/report`)}>
            {t('order.report')}
          </Button>
        )
      )}

      <Card>
        <h3 className="mb-3 font-bold">{t('order.timeline')}</h3>
        <Timeline events={o.timeline} />
      </Card>

      <Card>
        <h3 className="mb-2 font-bold">{t('order.ledger')}</h3>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="text-slate-600">
              <th className="py-1"><span className="sr-only">{t('ledger.entry')}</span></th>
              <th className="py-1">{t('ledger.debit')}</th>
              <th className="py-1">{t('ledger.credit')}</th>
            </tr>
          </thead>
          <tbody>
            {o.ledger.map((entry, i) => (
              <tr key={i} className="border-t border-slate-100">
                <td className="py-1">{t(`ledger.${entry.account}`)}</td>
                <td className="py-1">{entry.debit ? num(entry.debit) : '-'}</td>
                <td className="py-1">{entry.credit ? num(entry.credit) : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {o.ledger_balanced && (
          <p className="mt-2 text-sm text-emerald-800">✓ {t('order.ledger.balanced')}</p>
        )}
      </Card>
    </>
  )
}
