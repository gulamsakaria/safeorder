import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import type { Schemas } from '../../api/client'
import { useAction, useAsync } from '../../api/hooks'
import { Button, Card, Label, Spinner, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { formatDateTime } from '../../lib/format'
import { useAuth } from '../AuthProvider'
import { admin } from '../calls'
import { PageTitle, Problem, Row, Segmented, StatusChip, useMoney } from '../ui'

type Tab = 'orders' | 'users' | 'time'

export function AdminPage() {
  const { t, lang, num } = useI18n()
  const { me } = useAuth()
  const [tab, setTab] = useState<Tab>('orders')
  const overview = useAsync(() => admin.overview(), [], 8000)
  const money = useMoney()
  if (me && me.role !== 'ADMIN') return <Navigate to="/home" replace />
  const o = overview.data

  return (
    <>
      <PageTitle back="/more">{t('w.admin.title')}</PageTitle>
      {o && (
        <div className="grid grid-cols-2 gap-3">
          {(
            [
              ['users', num(o.users)],
              ['sellers', num(o.sellers)],
              ['held', money(o.held_total_bdt)],
              ['proofs', num(o.proofs_waiting)],
              ['disputes', num(o.disputes_open)],
              ['open', num(o.open_orders)],
            ] as const
          ).map(([key, value]) => (
            <div key={key} className="so-card rounded-2xl border border-white/60 bg-white/97 p-3">
              <p className="text-xs font-bold text-slate-600">{t(`w.admin.stat.${key}`)}</p>
              <p className="text-xl font-extrabold">{value}</p>
            </div>
          ))}
        </div>
      )}
      {o && <p className="px-1 text-xs text-indigo-100">{t('w.admin.now', { time: formatDateTime(o.now, lang) })}</p>}
      <Link to="/analyst">
        <Card tone="info" className="!border-2">
          <p className="font-bold">{t('w.admin.disputes')}</p>
          <p className="text-sm">{t('w.admin.disputes.sub')}</p>
        </Card>
      </Link>
      <Segmented<Tab>
        value={tab}
        onChange={setTab}
        options={[
          { value: 'orders', label: t('w.admin.tab.orders') },
          { value: 'users', label: t('w.admin.tab.users') },
          { value: 'time', label: t('w.admin.tab.time') },
        ]}
      />
      {tab === 'orders' && <OrdersTab onChanged={overview.reload} />}
      {tab === 'users' && <UsersTab />}
      {tab === 'time' && <TimeTab onChanged={overview.reload} />}
    </>
  )
}

function OrdersTab({ onChanged }: { onChanged: () => void }) {
  const { t } = useI18n()
  const [onlyOpen, setOnlyOpen] = useState(true)
  const orders = useAsync(() => admin.orders(onlyOpen), [onlyOpen], 8000)
  return (
    <>
      <label className="flex items-center gap-2 px-1 text-sm font-semibold text-white">
        <input type="checkbox" className="h-5 w-5" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} />
        {t('w.admin.onlyopen')}
      </label>
      {orders.loading && <Spinner label={t('common.loading')} />}
      {orders.data?.length === 0 && (
        <Card tone="info">
          <p>{t('w.orders.none')}</p>
        </Card>
      )}
      <ul className="space-y-3">
        {orders.data?.map((o) => (
          <li key={o.id}>
            <AdminOrder order={o} onDone={() => { orders.reload(); onChanged() }} />
          </li>
        ))}
      </ul>
    </>
  )
}

function AdminOrder({ order, onDone }: { order: Schemas['AdminOrderOut']; onDone: () => void }) {
  const { t, lang } = useI18n()
  const money = useMoney()
  const [note, setNote] = useState('')
  const [image, setImage] = useState<string | null>(null)
  const decide = useAction(async (decision: 'RELEASE_TO_SELLER' | 'REFUND_TO_BUYER') => {
    await admin.decide(order.id, decision, note.trim())
    setNote('')
    onDone()
  })
  const show = useAction(async () => setImage((await admin.proofImage(order.id)).image ?? null))
  const open = ['HELD', 'DELIVERED', 'DISPUTABLE'].includes(order.status)
  return (
    <Card tone={order.needs_decision ? 'warn' : 'plain'} className={order.needs_decision ? '!border-2' : ''}>
      <div className="flex items-center justify-between gap-3">
        <p className="font-extrabold">
          {order.id} · {money(order.amount_bdt)}
        </p>
        <StatusChip status={order.status} />
      </div>
      <div className="mt-2 divide-y divide-slate-200">
        <Row label={t('w.order.buyer')}>
          {order.buyer_name} · {order.buyer_phone}
        </Row>
        <Row label={t('w.order.seller')}>
          {order.seller_name} · {order.seller_phone}
        </Row>
        <Row label={t('w.pay.yourref')}>{order.order_ref ?? '-'}</Row>
        <Row label={t('w.order.placed')}>{formatDateTime(order.placed_at, lang)}</Row>
        <Row label={t('w.order.claimed')}>{order.claimed ? t('w.yes') : t('w.no')}</Row>
        {order.dispute_ids.length > 0 && (
          <Row label={t('w.admin.dispute')}>
            <Link className="font-bold text-indigo-700 underline" to={`/analyst/dispute/${order.dispute_ids[order.dispute_ids.length - 1]}`}>
              {order.dispute_ids[order.dispute_ids.length - 1]}
            </Link>
          </Row>
        )}
      </div>
      {order.proof && (
        <div className="mt-2 rounded-xl bg-slate-50 p-3 text-sm">
          <p className="font-bold">
            {t('w.proof.tracking')}: {order.proof.tracking_no}
          </p>
          {order.proof.note && <p>{order.proof.note}</p>}
          {order.proof.flags.length > 0 ? (
            <ul className="mt-1 list-disc pl-5 font-semibold text-amber-900">
              {order.proof.flags.map((f) => (
                <li key={f}>{t(`w.flag.${f}`)}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 font-semibold text-emerald-800">{t('w.admin.noflags')}</p>
          )}
          {order.proof.has_image &&
            (image ? (
              <img src={image} alt={t('w.proof.photo')} className="mt-2 max-h-64 w-full rounded-xl object-contain" />
            ) : (
              <Button variant="secondary" className="mt-2" disabled={show.pending} onClick={() => void show.run()}>
                {t('w.proof.show')}
              </Button>
            ))}
        </div>
      )}
      {open && (
        <div className="mt-3 space-y-2">
          <Label htmlFor={`note-${order.id}`}>{t('w.admin.note')}</Label>
          <TextInput id={`note-${order.id}`} value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} />
          {decide.error && <Problem error={decide.error} />}
          <div className="grid grid-cols-2 gap-2">
            <Button disabled={!note.trim() || decide.pending} onClick={() => void decide.run('RELEASE_TO_SELLER')}>
              {t('w.admin.release')}
            </Button>
            <Button variant="danger" disabled={!note.trim() || decide.pending} onClick={() => void decide.run('REFUND_TO_BUYER')}>
              {t('w.admin.refund')}
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

function UsersTab() {
  const { t, num } = useI18n()
  const money = useMoney()
  const users = useAsync(() => admin.users(), [], 10000)
  const freeze = useAction(async (id: string, frozen: boolean) => {
    await admin.freeze(id, frozen)
    users.reload()
  })
  const grant = useAction(async (id: string) => {
    await admin.grant(id, 1000)
    users.reload()
  })
  return (
    <>
      {users.loading && <Spinner label={t('common.loading')} />}
      {(freeze.error || grant.error) && <Problem error={(freeze.error ?? grant.error)!} />}
      <ul className="space-y-2">
        {users.data?.map((u) => (
          <li key={u.id}>
            <Card className="!p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="font-bold">
                  {u.name} {u.role === 'ADMIN' && <span className="text-xs text-red-700">({t('w.admin.role')})</span>}
                </p>
                {u.frozen && <span className="rounded-full bg-red-100 px-2 text-xs font-bold text-red-800">{t('w.admin.frozen')}</span>}
              </div>
              <p className="text-sm text-slate-600">
                {num(u.phone)} {u.is_seller ? `· ${u.shop_name}` : ''}
              </p>
              <p className="text-sm">
                {money(u.balance_bdt)} · {t('w.wallet.held')}: {money(u.held_bdt)}
              </p>
              {u.role !== 'ADMIN' && (
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <Button variant="secondary" onClick={() => void freeze.run(u.id, !u.frozen)}>
                    {u.frozen ? t('w.admin.unfreeze') : t('w.admin.freeze')}
                  </Button>
                  <Button variant="secondary" onClick={() => void grant.run(u.id)}>
                    {t('w.admin.grant')}
                  </Button>
                </div>
              )}
            </Card>
          </li>
        ))}
      </ul>
    </>
  )
}

function TimeTab({ onChanged }: { onChanged: () => void }) {
  const { t, lang } = useI18n()
  const [last, setLast] = useState<Schemas['ClockResultOut'] | null>(null)
  const go = useAction(async (hours: number) => {
    setLast(await admin.advanceClock(hours))
    onChanged()
  })
  return (
    <Card>
      <h3 className="mb-1 font-bold">{t('w.time.title')}</h3>
      <p className="mb-3 text-sm text-slate-600">{t('w.time.sub')}</p>
      <div className="grid grid-cols-3 gap-2">
        {[1, 24, 72].map((h) => (
          <Button key={h} variant="secondary" disabled={go.pending} onClick={() => void go.run(h)}>
            +{h} {t('w.time.hours')}
          </Button>
        ))}
      </div>
      {go.error && <div className="mt-2"><Problem error={go.error} /></div>}
      {last && (
        <div className="mt-3 text-sm">
          <p className="font-semibold">{t('w.admin.now', { time: formatDateTime(last.now, lang) })}</p>
          {last.fired.length === 0 ? (
            <p className="text-slate-600">{t('w.time.nothing')}</p>
          ) : (
            <ul className="list-disc pl-5">
              {last.fired.map((f) => (
                <li key={f.order_id + f.event}>
                  {f.order_id}: {t(`w.time.event.${f.event}`)}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Card>
  )
}
