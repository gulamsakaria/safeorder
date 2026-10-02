import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { calls } from '../api/calls'
import { DEMO_BUYER_ID } from '../api/client'
import type { Schemas } from '../api/client'
import { useAction } from '../api/hooks'
import { BandBadge } from '../components/BandBadge'
import { ErrorNotice } from '../components/ErrorNotice'
import { ReasonList } from '../components/ReasonList'
import { Button, Card, Label, Select, TextInput } from '../components/ui'
import { useI18n } from '../i18n/useI18n'
import { rememberCode } from '../lib/codeStore'

const CATEGORIES = [
  'clothing',
  'cosmetics',
  'electronics',
  'household',
  'food',
  'shoes',
  'books',
  'accessories',
]
const SCORE_MAX = 100

function ScoreMeter({ score }: { score: number }) {
  const { t, num } = useI18n()
  return (
    <div>
      <p className="text-sm font-semibold text-slate-700">{t('check.score')}</p>
      <p className="text-4xl font-bold tabular-nums" data-testid="score">
        {num(score)}
        <span className="text-lg font-semibold text-slate-500"> / {num(SCORE_MAX)}</span>
      </p>
      <div
        className="mt-2 h-3 w-full rounded-full bg-slate-200"
        role="meter"
        aria-label={t('check.score')}
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={SCORE_MAX}
      >
        <div className="h-3 rounded-full bg-blue-700" style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

export function TrustCheckPage() {
  const { t, num } = useI18n()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const linked = params.get('q')?.slice(0, 40) ?? ''
  const [query, setQuery] = useState(linked)
  const [results, setResults] = useState<Schemas['SellerPublic'][] | null>(null)
  const [seller, setSeller] = useState<Schemas['SellerPublic'] | null>(null)
  const [result, setResult] = useState<Schemas['TrustCheckResponse'] | null>(null)
  const [accepted, setAccepted] = useState(false)
  const [paying, setPaying] = useState(false)
  const [amount, setAmount] = useState('')
  const [category, setCategory] = useState(CATEGORIES[0])

  const search = useAction(async (q: string) => {
    const found = await calls.searchSellers(q)
    setResults(found)
    return found
  })
  const check = useAction(async (picked: Schemas['SellerPublic']) => {
    setSeller(picked)
    setResult(null)
    setAccepted(false)
    setPaying(false)
    setResult(await calls.trustCheck(picked.id))
  })
  const order = useAction(async () => {
    const created = await calls.createOrder({
      buyer_id: DEMO_BUYER_ID,
      seller_id: seller!.id,
      amount_bdt: Number(amount),
      product_category: category,
    })
    if (created.delivery_code) rememberCode(created.id, created.delivery_code)
    navigate(`/order/${created.id}`)
  })

  // A link such as /?q=Synthetic%20Shop%200001 (used by the demo page) searches once on arrival,
  // and runs the Trust Check straight away when exactly one seller matches.
  const linkedRun = useRef(false)
  useEffect(() => {
    if (!linked || linkedRun.current) return
    linkedRun.current = true
    void (async () => {
      const found = await search.run(linked)
      if (found?.length === 1) await check.run(found[0])
    })()
  })

  const onSearch = (e: FormEvent) => {
    e.preventDefault()
    if (query.trim()) void search.run(query.trim())
  }
  const needsWarning = result?.requires_extra_confirmation === true
  const canPay = result !== null && (!needsWarning || accepted)
  const amountValid = Number.isInteger(Number(amount)) && Number(amount) > 0

  return (
    <>
      <Card>
        <h2 className="mb-3 text-lg font-bold">{t('check.title')}</h2>
        <form onSubmit={onSearch} className="space-y-3">
          <div>
            <Label htmlFor="seller-search">{t('check.search.label')}</Label>
            <TextInput
              id="seller-search"
              value={query}
              placeholder={t('check.search.placeholder')}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={40}
            />
          </div>
          <Button type="submit" disabled={!query.trim() || search.pending}>
            {t('common.search')}
          </Button>
        </form>
      </Card>

      {search.error && <ErrorNotice error={search.error} />}

      {results && results.length === 0 && (
        <Card tone="info">
          <p>{t('check.search.none')}</p>
        </Card>
      )}

      {results && results.length > 0 && (
        <ul className="space-y-2" aria-label="sellers">
          {results.map((s) => (
            <li key={s.id}>
              <Card className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-bold">{s.display_name}</p>
                  <p className="text-sm text-slate-600">{s.wallet_no}</p>
                </div>
                <Button variant="secondary" onClick={() => void check.run(s)} disabled={check.pending}>
                  {t('check.pick')}
                </Button>
              </Card>
            </li>
          ))}
        </ul>
      )}

      {check.error && <ErrorNotice error={check.error} />}

      {result && seller && (
        <Card aria-label="trust-result" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-lg font-bold">{seller.display_name}</p>
              <p className="text-sm text-slate-600">{seller.wallet_no}</p>
            </div>
            <BandBadge band={result.band} />
          </div>

          {result.limited_history && result.score === null ? (
            <Card tone="info">
              <p className="font-bold">{t('check.limited.title')}</p>
              <p>{t('check.limited.body')}</p>
            </Card>
          ) : (
            result.score !== null && <ScoreMeter score={result.score} />
          )}

          <div>
            <h3 className="mb-2 font-bold">{t('check.reasons')}</h3>
            <ReasonList reasons={result.reasons} />
          </div>
          <p className="text-xs text-slate-500">
            {t('check.sandbox.note')} {t('check.model')}: {result.model_version}
          </p>

          {needsWarning && (
            <Card tone="danger" role="alert">
              <p className="text-lg font-bold text-red-900">{t('check.warning.title')}</p>
              <p className="mb-3">{t('check.warning.body')}</p>
              <label className="flex min-h-12 items-center gap-3 font-semibold">
                <input
                  type="checkbox"
                  className="h-6 w-6"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                />
                {t('check.warning.confirm')}
              </label>
            </Card>
          )}

          {!paying && (
            <Button disabled={!canPay} onClick={() => setPaying(true)} className="w-full">
              {t('check.pay')}
            </Button>
          )}
        </Card>
      )}

      {paying && seller && (
        <Card aria-label="order-form">
          <h2 className="mb-3 text-lg font-bold">{t('check.order.title')}</h2>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              if (amountValid) void order.run()
            }}
          >
            <div>
              <Label htmlFor="amount">
                {t('check.order.amount')} ({t('common.bdt')})
              </Label>
              <TextInput
                id="amount"
                inputMode="numeric"
                value={amount}
                onChange={(e) => setAmount(e.target.value.replace(/\D/g, ''))}
                placeholder={num(2800)}
              />
            </div>
            <div>
              <Label htmlFor="category">{t('check.order.category')}</Label>
              <Select id="category" value={category} onChange={(e) => setCategory(e.target.value)}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {t(`category.${c}`)}
                  </option>
                ))}
              </Select>
            </div>
            {order.error && <ErrorNotice error={order.error} />}
            <Button type="submit" disabled={!amountValid || order.pending} className="w-full">
              {t('check.order.submit')}
            </Button>
          </form>
        </Card>
      )}
    </>
  )
}
