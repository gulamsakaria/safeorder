import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAction } from '../../api/hooks'
import { Button, Card } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { useAuth } from '../AuthProvider'
import { wallet } from '../calls'
import { PageTitle, Problem, useMoney } from '../ui'

const ADD_CHOICES = [500, 1000, 2000, 5000]

export function AccountPage() {
  const { t, num } = useI18n()
  const { me, setMe } = useAuth()
  const money = useMoney()
  const [added, setAdded] = useState<number | null>(null)
  const add = useAction(async (amount: number) => {
    setMe(await wallet.addMoney(amount))
    setAdded(amount)
  })
  if (!me) return null

  return (
    <>
      <PageTitle>{t('w.account.title')}</PageTitle>
      <Card>
        <div className="flex items-center gap-3">
          <span className="grid h-14 w-14 place-items-center rounded-full bg-indigo-700 text-2xl font-extrabold text-white">
            {me.name.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <p className="text-lg font-extrabold">{me.name}</p>
            <p className="text-sm text-slate-600">{num(me.phone)}</p>
            {me.is_seller && <p className="text-xs font-bold text-rose-700">{t('w.account.shop', { name: me.shop_name ?? '' })}</p>}
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3">
        <div className="so-card rounded-2xl border border-sky-200 bg-sky-50/97 p-4">
          <p className="text-sm font-bold text-sky-900">{t('w.wallet.primary')}</p>
          <p className="mt-4 text-2xl font-extrabold text-slate-900">{money(me.balance_bdt)}</p>
        </div>
        <div className="so-card rounded-2xl border border-amber-200 bg-amber-50/97 p-4">
          <p className="text-sm font-bold text-amber-900">{t('w.wallet.held')}</p>
          <p className="mt-4 text-2xl font-extrabold text-slate-900">{money(me.held_bdt)}</p>
        </div>
      </div>
      <p className="px-1 text-xs text-indigo-100">{t('w.wallet.held.explain')}</p>

      <Card id="add">
        <h3 className="mb-1 font-bold">{t('w.add.title')}</h3>
        <p className="mb-3 text-sm text-slate-600">{t('w.add.sub', { left: money(me.add_money_left_bdt) })}</p>
        <div className="grid grid-cols-4 gap-2">
          {ADD_CHOICES.map((a) => (
            <Button
              key={a}
              variant="secondary"
              className="!px-2"
              disabled={add.pending || a > me.add_money_left_bdt}
              onClick={() => void add.run(a)}
            >
              {money(a)}
            </Button>
          ))}
        </div>
        {add.error && <div className="mt-3"><Problem error={add.error} /></div>}
        {added !== null && !add.error && <p className="mt-3 text-sm font-semibold text-emerald-800">{t('w.add.done', { amount: money(added) })}</p>}
      </Card>

      <Card>
        <div className="grid grid-cols-2 gap-2">
          <Link to="/history" className="so-btn-lift grid min-h-12 place-items-center rounded-xl border border-slate-300 bg-white font-bold">
            {t('w.tile.history')}
          </Link>
          <Link to="/seller" className="so-btn-lift grid min-h-12 place-items-center rounded-xl border border-slate-300 bg-white font-bold">
            {t('w.tile.seller')}
          </Link>
        </div>
      </Card>
    </>
  )
}
