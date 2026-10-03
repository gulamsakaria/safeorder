import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useAsync } from '../../api/hooks'
import { Card } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { useAuth } from '../AuthProvider'
import { wallet } from '../calls'
import { Icons } from '../icons'
import { useMoney } from '../ui'

function Tile({ to, icon, label, tone, badge }: { to: string; icon: ReactNode; label: string; tone: string; badge?: number }) {
  return (
    <Link
      to={to}
      className="so-btn-lift relative flex min-h-24 flex-col items-center justify-center gap-2 rounded-2xl p-2 text-center"
    >
      <span className={`grid h-14 w-14 place-items-center rounded-2xl ${tone}`}>{icon}</span>
      <span className="text-xs font-bold text-slate-800">{label}</span>
      {badge ? (
        <span className="absolute right-2 top-1 grid h-6 min-w-6 place-items-center rounded-full bg-red-600 px-1 text-xs font-bold text-white">
          {badge}
        </span>
      ) : null}
    </Link>
  )
}

export function HomePage() {
  const { t, num } = useI18n()
  const { me } = useAuth()
  const money = useMoney()
  const [showBalance, setShowBalance] = useState(false)
  const buyerOrders = useAsync(() => wallet.orders('BUYER'), [], 15000)
  const sellerOrders = useAsync(() => wallet.orders('SELLER'), [me?.is_seller], 15000)
  if (!me) return null

  const toConfirm = (buyerOrders.data ?? []).filter((o) => o.can_accept).length
  const waiting = (sellerOrders.data ?? []).filter((o) => o.id === 'UNCLAIMED').length

  return (
    <>
      <Card className="!bg-gradient-to-br !from-amber-300 !to-amber-400">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="grid h-14 w-14 place-items-center rounded-full bg-white text-2xl font-extrabold text-indigo-800">
              {me.name.slice(0, 1).toUpperCase()}
            </span>
            <div>
              <p className="text-lg font-extrabold text-slate-900">{me.name}</p>
              <p className="text-sm text-slate-800">{num(me.phone)}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowBalance((v) => !v)}
            className="so-btn-primary min-h-11 rounded-full px-4 text-sm font-bold text-white"
          >
            {showBalance ? money(me.balance_bdt) : t('w.balance')}
          </button>
        </div>
        {me.held_bdt > 0 && showBalance && (
          <p className="mt-2 text-sm font-semibold text-slate-900">
            {t('w.held.line', { amount: money(me.held_bdt) })}
          </p>
        )}
      </Card>

      {toConfirm > 0 && (
        <Link to="/history?tab=orders">
          <Card tone="warn" className="!border-2">
            <p className="font-bold text-amber-950">{t('w.todo.confirm', { n: num(toConfirm) })}</p>
          </Card>
        </Link>
      )}
      {waiting > 0 && (
        <Link to="/seller">
          <Card tone="warn" className="!border-2">
            <p className="font-bold text-amber-950">{t('w.todo.claim', { n: num(waiting) })}</p>
          </Card>
        </Link>
      )}

      <Card>
        <div className="grid grid-cols-4 gap-1">
          <Tile to="/pay?mode=send" icon={Icons.send} label={t('w.tile.send')} tone="bg-sky-100 text-sky-700" />
          <Tile to="/pay?mode=payment" icon={Icons.pay} label={t('w.tile.payment')} tone="bg-indigo-100 text-indigo-700" />
          <Tile to="/account#add" icon={Icons.add} label={t('w.tile.add')} tone="bg-emerald-100 text-emerald-700" />
          <Tile to="/history" icon={Icons.history} label={t('w.tile.history')} tone="bg-slate-200 text-slate-700" />
          <Tile to="/history?tab=orders" icon={Icons.orders} label={t('w.tile.orders')} tone="bg-amber-100 text-amber-700" badge={toConfirm} />
          <Tile to="/seller" icon={Icons.shop} label={t('w.tile.seller')} tone="bg-rose-100 text-rose-700" badge={waiting} />
          <Tile to="/check" icon={Icons.shield} label={t('w.tile.check')} tone="bg-violet-100 text-violet-700" />
          <Tile to="/guide" icon={Icons.guide} label={t('w.tile.guide')} tone="bg-teal-100 text-teal-700" />
        </div>
      </Card>

      <Card>
        <h3 className="mb-2 font-bold">{t('w.how.title')}</h3>
        <ol className="space-y-2 text-sm">
          {[1, 2, 3, 4].map((n) => (
            <li key={n} className="flex gap-3">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-indigo-700 text-xs font-bold text-white">
                {num(n)}
              </span>
              <span>{t(`w.how.${n}`)}</span>
            </li>
          ))}
        </ol>
      </Card>
    </>
  )
}
