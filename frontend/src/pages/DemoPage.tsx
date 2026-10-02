import { useState } from 'react'
import { Link } from 'react-router-dom'
import { calls } from '../api/calls'
import { DEMO_CODE_KEY } from '../api/client'
import type { Schemas } from '../api/client'
import { useAction } from '../api/hooks'
import { ErrorNotice } from '../components/ErrorNotice'
import { Button, Card, Label, TextInput } from '../components/ui'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime } from '../lib/format'

type Scenario = Schemas['DemoScenarioOut']

const COURIER_EVENTS: Schemas['CourierStatus'][] = ['in_transit', 'delivered', 'lost', 'returned']
const QUICK_HOURS = [24, 72]

/** Sandbox-only controls (BLUEPRINT.md Step 11 extends this page with scenario loading). */
export function DemoPage() {
  const { t, lang } = useI18n()
  const [orderId, setOrderId] = useState('')
  const [hours, setHours] = useState('24')
  const [note, setNote] = useState<string>()
  const [code, setCode] = useState(() => {
    try {
      return sessionStorage.getItem(DEMO_CODE_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const changeCode = (value: string) => {
    setCode(value)
    try {
      sessionStorage.setItem(DEMO_CODE_KEY, value)
    } catch {
      // ignore: the code then lasts only until the next reload
    }
  }
  const [scenarios, setScenarios] = useState<Scenario[] | null>(null)

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
    setScenarios(null)
    setNote(t('demo.reset.done'))
  })
  const load = useAction(async () => {
    const out = await calls.demoReset('demo')
    setScenarios(out.scenarios)
    setNote(t('demo.loaded'))
  })
  const error = courier.error ?? clock.error ?? reset.error ?? load.error

  return (
    <Card className="space-y-4">
      <h2 className="text-lg font-bold">{t('demo.title')}</h2>
      <p className="text-slate-600">{t('demo.note')}</p>

      <div>
        <Label htmlFor="demo-code">{t('demo.code.label')}</Label>
        <TextInput
          id="demo-code"
          type="password"
          autoComplete="off"
          value={code}
          placeholder={t('demo.code.hint')}
          onChange={(e) => changeCode(e.target.value)}
        />
      </div>

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

      <section aria-label={t('demo.scenarios')} className="space-y-3">
        <h3 className="font-bold">{t('demo.scenarios')}</h3>
        <p className="text-sm text-slate-600">{t('demo.scenarios.note')}</p>
        <Button variant="secondary" disabled={load.pending} onClick={() => void load.run()}>
          {t('demo.load')}
        </Button>
        {scenarios && (
          <ol className="space-y-3">
            {scenarios.map((s) => (
              <ScenarioCard key={s.key} scenario={s} />
            ))}
          </ol>
        )}
      </section>

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

function ScenarioCard({ scenario: s }: { scenario: Scenario }) {
  const { t, num } = useI18n()
  const link = 'font-semibold text-blue-800 underline'
  return (
    <li className="rounded-xl border border-slate-200 p-3" data-testid={`scenario-${s.key}`}>
      <p className="font-semibold">
        {num(s.number)}. {t(`demo.scenario.${s.key}.title`)}
      </p>
      <p className="text-sm text-slate-600">{t(`demo.scenario.${s.key}.what`)}</p>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {s.seller_name && (
          <Link className={link} to={`/?q=${encodeURIComponent(s.seller_name)}`}>
            {t('demo.open.check')} ({s.seller_id})
          </Link>
        )}
        {s.order_id && (
          <Link className={link} to={`/order/${s.order_id}`}>
            {t('demo.open.order')} {s.order_id}
          </Link>
        )}
        {s.dispute_id && (
          <Link className={link} to={`/analyst/dispute/${s.dispute_id}`}>
            {t('demo.open.case')} {s.dispute_id}
          </Link>
        )}
        {s.delivery_code && (
          <span>
            {t('demo.code')}: <b className="tabular-nums">{s.delivery_code}</b>
          </span>
        )}
      </div>
      {s.analysis && (
        <p className="mt-1 text-sm text-slate-500">{t(`demo.analysis.${s.analysis}`)}</p>
      )}
    </li>
  )
}
