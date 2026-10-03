import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAction, useAsync } from '../../api/hooks'
import { Button, Card, Label, Select, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { formatDateTime } from '../../lib/format'
import { useAuth } from '../AuthProvider'
import { wallet } from '../calls'
import { PageTitle, Problem, StatusChip, useMoney } from '../ui'

const CATEGORIES = ['clothing', 'electronics', 'cosmetics', 'household', 'food', 'shoes', 'books', 'accessories']

export function SellerHubPage() {
  const { t, lang, num } = useI18n()
  const { me, setMe } = useAuth()
  const money = useMoney()
  const navigate = useNavigate()
  const [shop, setShop] = useState('')
  const [category, setCategory] = useState(CATEGORIES[0])
  const [orderNo, setOrderNo] = useState('')
  const orders = useAsync(() => wallet.orders('SELLER'), [me?.is_seller], 10000)

  const enable = useAction(async () => {
    setMe(await wallet.sellerMode({ shop_name: shop, category }))
  })
  const claim = useAction(async () => {
    const order = await wallet.claim(orderNo)
    setOrderNo('')
    orders.reload()
    navigate(`/orders/${order.id}`)
  })

  if (!me) return null

  if (!me.is_seller) {
    const onSubmit = (e: FormEvent) => {
      e.preventDefault()
      void enable.run()
    }
    return (
      <>
        <PageTitle back="/home">{t('w.seller.become')}</PageTitle>
        <Card>
          <p className="mb-3 text-sm text-slate-700">{t('w.seller.become.sub')}</p>
          <form onSubmit={onSubmit} className="space-y-3">
            <div>
              <Label htmlFor="shop">{t('w.seller.shop')}</Label>
              <TextInput id="shop" value={shop} maxLength={40} onChange={(e) => setShop(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="cat">{t('w.seller.category')}</Label>
              <Select id="cat" value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {t(`w.cat.${c}`)}
                  </option>
                ))}
              </Select>
            </div>
            {enable.error && <Problem error={enable.error} />}
            <Button type="submit" className="w-full" disabled={shop.trim().length < 2 || enable.pending}>
              {t('w.seller.turnon')}
            </Button>
          </form>
        </Card>
      </>
    )
  }

  const rows = orders.data ?? []
  const waiting = rows.filter((o) => o.id === 'UNCLAIMED')
  const mine = rows.filter((o) => o.id !== 'UNCLAIMED')
  const onClaim = (e: FormEvent) => {
    e.preventDefault()
    void claim.run()
  }

  return (
    <>
      <PageTitle back="/home">{t('w.seller.hub')}</PageTitle>
      <Card>
        <p className="font-extrabold">{me.shop_name}</p>
        <p className="text-sm text-slate-600">
          {t('w.seller.held', { held: money(me.held_bdt), balance: money(me.balance_bdt) })}
        </p>
      </Card>

      <Card>
        <h3 className="mb-1 font-bold">{t('w.claim.title')}</h3>
        <p className="mb-3 text-sm text-slate-600">{t('w.claim.sub')}</p>
        <form onSubmit={onClaim} className="space-y-3">
          <div>
            <Label htmlFor="order-no">{t('w.claim.label')}</Label>
            <TextInput id="order-no" value={orderNo} maxLength={40} placeholder="O-0001" onChange={(e) => setOrderNo(e.target.value)} />
          </div>
          {claim.error && <Problem error={claim.error} />}
          <Button type="submit" className="w-full" disabled={!orderNo.trim() || claim.pending}>
            {t('w.claim.go')}
          </Button>
        </form>
      </Card>

      {waiting.length > 0 && (
        <Card tone="warn">
          <h3 className="mb-2 font-bold text-amber-950">{t('w.claim.waiting', { n: num(waiting.length) })}</h3>
          <ul className="space-y-2">
            {waiting.map((o) => (
              <li key={o.row_key} className="rounded-xl bg-white/70 p-3 text-sm">
                <p className="text-lg font-extrabold">{money(o.amount_bdt)}</p>
                <p>
                  {o.buyer_name} · {o.buyer_phone}
                </p>
                <p className="text-xs text-slate-600">{formatDateTime(o.placed_at, lang)}</p>
                {o.claim_deadline && (
                  <p className="text-xs font-semibold text-red-800">
                    {t('w.claim.deadline', { time: formatDateTime(o.claim_deadline, lang) })}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <h3 className="px-1 font-bold text-white">{t('w.orders.sold')}</h3>
      {mine.length === 0 && (
        <Card tone="info">
          <p>{t('w.orders.none')}</p>
        </Card>
      )}
      <ul className="space-y-2">
        {mine.map((o) => (
          <li key={o.row_key}>
            <Link to={`/orders/${o.id}`}>
              <Card className="!p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-bold">{o.buyer_name}</p>
                  <StatusChip status={o.status} />
                </div>
                <p className="mt-1 text-lg font-extrabold">{money(o.amount_bdt)}</p>
                <p className="text-xs text-slate-500">
                  {o.id} · {formatDateTime(o.placed_at, lang)}
                </p>
                {o.can_submit_proof && !o.proof && (
                  <p className="mt-1 text-sm font-bold text-indigo-800">{t('w.orders.action.proof')}</p>
                )}
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </>
  )
}
