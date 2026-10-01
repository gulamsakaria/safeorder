import { useState } from 'react'
import { calls } from '../api/calls'
import type { Schemas } from '../api/client'
import { useAction } from '../api/hooks'
import { ErrorNotice } from '../components/ErrorNotice'
import { Button, Card, Label, TextInput } from '../components/ui'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime } from '../lib/format'

const COURIER_EVENTS: Schemas['CourierStatus'][] = ['in_transit', 'delivered', 'lost', 'returned']
const QUICK_HOURS = [24, 72]

/** Sandbox-only controls (BLUEPRINT.md Step 11 extends this page with scenario loading). */
export function DemoPage() {
  const { t, lang } = useI18n()
  const [orderId, setOrderId] = useState('')
  const [hours, setHours] = useState('24')
  const [note, setNote] = useState<string>()

  const courier = useAction(async (status: Schemas['CourierStatus']) => {
    const out = await calls.courierEvent(orderId.trim(), status)
    setNote(`${out.id}: ${t(`status.${out.status}`)}`)
  })
  const clock = useAction(async (h: number) => {
    const out = await calls.advanceClock(h)
    const fired = out.fired.map((f) => `${f.order_id} ${f.event}`).join(', ') || '-'
    setNote(`${t('demo.now')}: ${formatDateTime(out.now, lang)} · ${t('demo.fired')}: ${fired}`)
  })
  const reset = useAction(async () => {
    await calls.demoReset()
    setNote(t('demo.reset.done'))
  })
  const error = courier.error ?? clock.error ?? reset.error

  return (
    <Card className="space-y-4">
      <h2 className="text-lg font-bold">{t('demo.title')}</h2>
      <p className="text-slate-600">{t('demo.note')}</p>

      <div>
        <Label htmlFor="demo-order">{t('demo.order')}</Label>
        <TextInput
          id="demo-order"
          value={orderId}
          placeholder="O-0001"
          onChange={(e) => setOrderId(e.target.value)}
        />
      </div>

      <div>
        <p className="mb-2 text-sm font-semibold">{t('demo.courier')}</p>
        <div className="flex flex-wrap gap-2">
          {COURIER_EVENTS.map((status) => (
            <Button
              key={status}
              variant="secondary"
              disabled={!orderId.trim() || courier.pending}
              onClick={() => void courier.run(status)}
            >
              {t(`courier.${status}`)}
            </Button>
          ))}
        </div>
      </div>

      <div>
        <p className="mb-2 text-sm font-semibold">{t('demo.clock')}</p>
        <div className="flex flex-wrap items-center gap-2">
          {QUICK_HOURS.map((h) => (
            <Button key={h} variant="secondary" disabled={clock.pending} onClick={() => void clock.run(h)}>
              +{h} {t('demo.hours')}
            </Button>
          ))}
          <TextInput
            aria-label={t('demo.hours')}
            className="max-w-24"
            inputMode="numeric"
            value={hours}
            onChange={(e) => setHours(e.target.value.replace(/\D/g, ''))}
          />
          <Button disabled={!hours || clock.pending} onClick={() => void clock.run(Number(hours))}>
            {t('demo.hours')}
          </Button>
        </div>
      </div>

      <Button variant="danger" disabled={reset.pending} onClick={() => void reset.run()}>
        {t('demo.reset')}
      </Button>

      {error && <ErrorNotice error={error} />}
      {note && (
        <p role="status" className="rounded-xl bg-slate-100 p-3 text-sm" data-testid="demo-note">
          {note}
        </p>
      )}
    </Card>
  )
}
