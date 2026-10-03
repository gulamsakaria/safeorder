import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import type { Schemas } from '../../api/client'
import { useAction } from '../../api/hooks'
import { BandBadge } from '../../components/BandBadge'
import { ReasonList } from '../../components/ReasonList'
import { Button, Card, Label, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { useAuth } from '../AuthProvider'
import { wallet } from '../calls'
import { CopyBox, PageTitle, PinField, Problem, Row, useMoney } from '../ui'

const QUICK_AMOUNTS = [100, 300, 500, 1000]

/** Pressing "Pay" again (even while the receipt is shown) starts a fresh payment. */
export function PayPage() {
  const { key } = useLocation()
  return <PayFlow key={key} />
}

function PayFlow() {
  const { t, num } = useI18n()
  const { me, setMe } = useAuth()
  const money = useMoney()
  const [params] = useSearchParams()
  const mode = params.get('mode') === 'send' ? 'send' : 'payment'
  const [phone, setPhone] = useState(params.get('to') ?? '')
  const [target, setTarget] = useState<Schemas['LookupOut'] | null>(null)
  const [amount, setAmount] = useState('')
  const [ref, setRef] = useState('')
  const [pin, setPin] = useState('')
  const [risk, setRisk] = useState(false)
  const [done, setDone] = useState<Schemas['PayOut'] | null>(null)

  const lookup = useAction(async () => {
    setTarget(null)
    setRisk(false)
    setTarget(await wallet.lookup(phone))
  })
  const pay = useAction(async () => {
    const out = await wallet.pay({
      to_phone: target!.phone,
      amount_bdt: Number(amount),
      order_ref: ref.trim() || null,
      pin,
      confirm_risk: risk,
    })
    setMe(out.me)
    setDone(out)
  })

  if (!me) return null

  if (done) {
    const held = done.kind === 'HELD_PAYMENT' && done.order
    return (
      <>
        <PageTitle>{t('w.pay.done')}</PageTitle>
        <Card tone="good">
          <p className="text-lg font-extrabold text-emerald-900">
            {money(done.amount_bdt)} → {done.to_name}
          </p>
          <p className="text-sm text-emerald-900">{num(done.to_phone)}</p>
          {held ? (
            <div className="mt-3 space-y-3">
              <p className="text-sm font-semibold text-slate-900">{t('w.pay.held.note')}</p>
              <div>
                <p className="mb-1 text-sm font-bold text-slate-900">{t('w.pay.ordernumber')}</p>
                <CopyBox text={done.order!.id} />
                <p className="mt-2 text-xs text-slate-700">{t('w.pay.tellseller')}</p>
              </div>
              <Row label={t('w.pay.yourref')}>{done.order!.order_ref ?? '-'}</Row>
              <div className="flex gap-2">
                <Link
                  to={`/orders/${done.order!.id}`}
                  className="so-btn-primary grid min-h-12 flex-1 place-items-center rounded-xl px-4 font-bold text-white"
                >
                  {t('w.pay.vieworder')}
                </Link>
              </div>
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-900">{t('w.pay.sent.note')}</p>
          )}
        </Card>
        <Link to="/home" className="block text-center font-semibold text-indigo-100 underline">
          {t('w.home.back')}
        </Link>
      </>
    )
  }

  const onLookup = (e: FormEvent) => {
    e.preventDefault()
    void lookup.run()
  }
  const amountNumber = Number(amount)
  const amountOk = Number.isInteger(amountNumber) && amountNumber > 0
  const needsRisk = target?.requires_extra_confirmation === true
  const canPay = !!target && !target.is_self && amountOk && pin.length === 5 && (!needsRisk || risk)

  return (
    <>
      <PageTitle back="/home">{mode === 'send' ? t('w.tile.send') : t('w.tile.payment')}</PageTitle>

      <Card>
        <form onSubmit={onLookup} className="space-y-3">
          <div>
            <Label htmlFor="to-phone">{t('w.pay.to')}</Label>
            <TextInput
              id="to-phone"
              type="tel"
              inputMode="numeric"
              placeholder="018XXXXXXXX"
              value={phone}
              maxLength={14}
              onChange={(e) => {
                setPhone(e.target.value)
                setTarget(null)
              }}
            />
          </div>
          <Button type="submit" variant="secondary" disabled={!phone.trim() || lookup.pending}>
            {t('w.pay.check')}
          </Button>
        </form>
        {lookup.error && <div className="mt-3"><Problem error={lookup.error} /></div>}
      </Card>

      {target && (
        <Card>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-lg font-extrabold">{target.name}</p>
              <p className="text-sm text-slate-600">{num(target.phone)}</p>
            </div>
            {target.is_seller && (
              <span className="rounded-full bg-rose-100 px-3 py-1 text-xs font-bold text-rose-800">
                {t('w.pay.seller')}
              </span>
            )}
          </div>
          {target.is_self ? (
            <p className="mt-3 text-sm font-semibold text-red-800">{t('w.pay.self')}</p>
          ) : target.is_seller ? (
            <div className="mt-3 space-y-3">
              {target.trust && (
                <div className="space-y-2 rounded-xl bg-slate-50 p-3">
                  <p className="text-sm font-bold">{t('w.pay.trust')}</p>
                  <BandBadge band={target.trust.band} />
                  {target.trust.score !== null && (
                    <p className="text-sm text-slate-700">{t('w.pay.score', { score: num(target.trust.score) })}</p>
                  )}
                  <ReasonList reasons={target.trust.reasons} />
                </div>
              )}
              <p className="rounded-xl bg-indigo-50 p-3 text-sm font-semibold text-indigo-900">
                {t('w.pay.willhold')}
              </p>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-700">{t('w.pay.notseller')}</p>
          )}
        </Card>
      )}

      {target && !target.is_self && (
        <Card>
          <div className="space-y-3">
            <div>
              <Label htmlFor="amount">{t('w.pay.amount')}</Label>
              <TextInput
                id="amount"
                inputMode="numeric"
                value={amount}
                maxLength={7}
                onChange={(e) => setAmount(e.target.value.replace(/\D/g, ''))}
              />
              <div className="mt-2 flex flex-wrap gap-2">
                {QUICK_AMOUNTS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="so-btn-lift min-h-10 rounded-full border border-slate-300 bg-white px-4 text-sm font-semibold"
                    onClick={() => setAmount(String(q))}
                  >
                    {money(q)}
                  </button>
                ))}
              </div>
              <p className="mt-1 text-xs text-slate-600">{t('w.pay.have', { amount: money(me.balance_bdt) })}</p>
            </div>
            {target.is_seller && (
              <div>
                <Label htmlFor="ref">{t('w.pay.ref')}</Label>
                <TextInput id="ref" value={ref} maxLength={40} placeholder={t('w.pay.ref.hint')} onChange={(e) => setRef(e.target.value)} />
              </div>
            )}
            <PinField id="pay-pin" label={t('w.pay.pin')} value={pin} onChange={setPin} />
            {needsRisk && (
              <label className="flex items-start gap-3 rounded-xl border-2 border-red-300 bg-red-50 p-3 text-sm font-semibold text-red-900">
                <input type="checkbox" className="mt-1 h-5 w-5" checked={risk} onChange={(e) => setRisk(e.target.checked)} />
                {t('w.pay.risk')}
              </label>
            )}
            {pay.error && <Problem error={pay.error} />}
            <Button className="w-full" disabled={!canPay || pay.pending} onClick={() => void pay.run()}>
              {pay.pending ? t('w.working') : t('w.pay.confirm', { amount: amountOk ? money(amountNumber) : '' })}
            </Button>
          </div>
        </Card>
      )}
    </>
  )
}
