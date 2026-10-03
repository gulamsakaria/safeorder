import { Link, useSearchParams } from 'react-router-dom'
import { useAsync } from '../../api/hooks'
import { Card, Spinner } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { formatDateTime } from '../../lib/format'
import { useAuth } from '../AuthProvider'
import { wallet } from '../calls'
import { PageTitle, Problem, Segmented, StatusChip, useMoney } from '../ui'

type Tab = 'all' | 'orders'

export function HistoryPage() {
  const { t, lang, num } = useI18n()
  const { me } = useAuth()
  const money = useMoney()
  const [params, setParams] = useSearchParams()
  const tab: Tab = params.get('tab') === 'orders' ? 'orders' : 'all'
  const history = useAsync(() => wallet.history(), [], 15000)
  const bought = useAsync(() => wallet.orders('BUYER'), [], 15000)
  const sold = useAsync(() => wallet.orders('SELLER'), [me?.is_seller], 15000)

  return (
    <>
      <PageTitle>{t('w.history.title')}</PageTitle>
      <Segmented
        value={tab}
        onChange={(v) => setParams(v === 'orders' ? { tab: 'orders' } : {})}
        options={[
          { value: 'all', label: t('w.history.tx') },
          { value: 'orders', label: t('w.history.orders') },
        ]}
      />

      {tab === 'all' && (
        <>
          {history.loading && <Spinner label={t('common.loading')} />}
          {history.error && <Problem error={history.error} />}
          {history.data?.length === 0 && (
            <Card tone="info">
              <p>{t('w.history.empty')}</p>
            </Card>
          )}
          <ul className="space-y-2">
            {history.data?.map((tx) => {
              const positive = tx.amount_bdt >= 0
              const body = (
                <Card className="flex items-center justify-between gap-3 !p-3">
                  <div className="min-w-0">
                    <p className="font-bold">{t(`w.tx.${tx.kind}`)}</p>
                    <p className="truncate text-sm text-slate-600">
                      {tx.counterparty_name ?? tx.note ?? ''}
                      {tx.counterparty_phone ? ` ${num(tx.counterparty_phone)}` : ''}
                    </p>
                    <p className="text-xs text-slate-500">{formatDateTime(tx.created_at, lang)}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className={`text-lg font-extrabold ${positive ? 'text-emerald-700' : 'text-red-700'}`}>
                      {positive ? '+' : '-'}
                      {money(Math.abs(tx.amount_bdt))}
                    </p>
                    <p className="text-xs text-slate-500">{t('w.history.balance', { amount: money(tx.balance_after) })}</p>
                  </div>
                </Card>
              )
              return (
                <li key={tx.id}>
                  {tx.order_id ? <Link to={`/orders/${tx.order_id}`}>{body}</Link> : body}
                </li>
              )
            })}
          </ul>
        </>
      )}

      {tab === 'orders' && (
        <>
          <h3 className="px-1 font-bold text-white">{t('w.orders.bought')}</h3>
          {bought.loading && <Spinner label={t('common.loading')} />}
          {bought.data?.length === 0 && (
            <Card tone="info">
              <p>{t('w.orders.none')}</p>
            </Card>
          )}
          <ul className="space-y-2">
            {bought.data?.map((o) => (
              <li key={o.row_key}>
                <Link to={`/orders/${o.id}`}>
                  <Card className="!p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-bold">{o.seller_name}</p>
                      <StatusChip status={o.status} />
                    </div>
                    <p className="mt-1 text-lg font-extrabold">{money(o.amount_bdt)}</p>
                    <p className="text-xs text-slate-500">
                      {o.id} · {formatDateTime(o.placed_at, lang)}
                    </p>
                    {o.can_accept && <p className="mt-1 text-sm font-bold text-indigo-800">{t('w.orders.action.confirm')}</p>}
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
          {me?.is_seller && (
            <>
              <h3 className="px-1 pt-2 font-bold text-white">{t('w.orders.sold')}</h3>
              <ul className="space-y-2">
                {sold.data?.map((o) => (
                  <li key={o.row_key}>
                    {o.id === 'UNCLAIMED' ? (
                      <Link to="/seller">
                        <Card tone="warn" className="!p-3">
                          <p className="font-bold">{t('w.orders.unclaimed')}</p>
                          <p className="text-lg font-extrabold">{money(o.amount_bdt)}</p>
                        </Card>
                      </Link>
                    ) : (
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
                        </Card>
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </>
  )
}
