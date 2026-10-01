import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { calls } from '../api/calls'
import type { Schemas } from '../api/client'
import { useAction, useAsync } from '../api/hooks'
import { Countdown } from '../components/Countdown'
import { ErrorNotice } from '../components/ErrorNotice'
import { Button, Card, Label, Spinner, TextArea } from '../components/ui'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime } from '../lib/format'
import { useServerNow } from '../lib/serverClock'

const POLL_MS = 5000
const MAX_RESPONSE = 2000
const MAX_EVIDENCE = 4000
const CLOSED: Schemas['DisputeStatus'][] = ['RESOLVED', 'ESCALATED']

/** User-written text is rendered as plain text; React escapes it, and line breaks are kept. */
function UserText({ children }: { children: string }) {
  return <p className="whitespace-pre-wrap break-words">{children}</p>
}

function EvidenceList({ dispute }: { dispute: Schemas['DisputeOut'] }) {
  const { t, lang } = useI18n()
  if (dispute.evidence.length === 0) {
    return <p className="text-slate-600">{t('dispute.noevidence')}</p>
  }
  return (
    <ul className="space-y-3">
      {dispute.evidence.map((item, i) => (
        <li key={i} className="rounded-xl bg-slate-50 p-3">
          <p className="mb-1 text-xs font-bold uppercase text-slate-600">
            {item.party === 'BUYER' ? t('dispute.buyer') : t('dispute.seller')} ·{' '}
            {formatDateTime(item.created_at, lang)}
          </p>
          <UserText>{item.description_text}</UserText>
        </li>
      ))}
    </ul>
  )
}

function SellerForm({
  dispute,
  serverTime,
  onDone,
}: {
  dispute: Schemas['DisputeOut']
  serverTime: string
  onDone: () => void
}) {
  const { t, lang } = useI18n()
  const now = useServerNow(serverTime)
  const [response, setResponse] = useState('')
  const [evidence, setEvidence] = useState('')
  const deadline = dispute.seller_deadline ? Date.parse(dispute.seller_deadline) : undefined
  const expired = deadline !== undefined && now >= deadline
  const submit = useAction(async () => {
    await calls.sellerResponse(dispute.id, {
      response_text: response.trim(),
      evidence_text: evidence.trim(),
    })
    setEvidence('')
    onDone()
  })
  const open = dispute.status === 'OPEN' || dispute.status === 'SELLER_RESPONDED'

  return (
    <Card aria-label="seller-form">
      <h3 className="mb-1 text-lg font-bold">{t('seller.title')}</h3>
      {dispute.seller_deadline && (
        <p className="mb-3">
          {t('seller.deadline')}: <strong>{formatDateTime(dispute.seller_deadline, lang)}</strong>
          {!expired && (
            <>
              {' '}
              · {t('seller.deadline.left')}:{' '}
              <Countdown
                targetIso={dispute.seller_deadline}
                serverTimeIso={serverTime}
                endedText={t('seller.deadline.passed')}
              />
            </>
          )}
        </p>
      )}
      {expired && (
        <p role="alert" className="mb-3 font-bold text-red-800">
          {t('seller.deadline.passed')}
        </p>
      )}
      {dispute.seller_responded_at && (
        <p className="mb-3 rounded-xl bg-emerald-50 p-3 text-emerald-900">✓ {t('seller.done')}</p>
      )}
      {open && !expired && (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault()
            if (response.trim()) void submit.run()
          }}
        >
          <div>
            <Label htmlFor="seller-response">{t('seller.response')}</Label>
            <TextArea
              id="seller-response"
              value={response}
              maxLength={MAX_RESPONSE}
              placeholder={t('seller.response.placeholder')}
              onChange={(e) => setResponse(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="seller-evidence">{t('seller.evidence')}</Label>
            <TextArea
              id="seller-evidence"
              value={evidence}
              maxLength={MAX_EVIDENCE}
              placeholder={t('seller.evidence.placeholder')}
              onChange={(e) => setEvidence(e.target.value)}
            />
          </div>
          {submit.error && <ErrorNotice error={submit.error} />}
          <Button type="submit" disabled={!response.trim() || submit.pending} className="w-full">
            {submit.pending ? t('common.sending') : t('seller.submit')}
          </Button>
        </form>
      )}
    </Card>
  )
}

function BuyerEvidenceForm({ disputeId, onDone }: { disputeId: string; onDone: () => void }) {
  const { t } = useI18n()
  const [text, setText] = useState('')
  const add = useAction(async () => {
    await calls.buyerEvidence(disputeId, text.trim())
    setText('')
    onDone()
  })
  return (
    <Card>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (text.trim()) void add.run()
        }}
      >
        <Label htmlFor="more-evidence">{t('dispute.addEvidence')}</Label>
        <TextArea
          id="more-evidence"
          value={text}
          maxLength={MAX_EVIDENCE}
          placeholder={t('report.evidence.placeholder')}
          onChange={(e) => setText(e.target.value)}
        />
        {add.error && <ErrorNotice error={add.error} />}
        <Button type="submit" variant="secondary" disabled={!text.trim() || add.pending}>
          {t('dispute.addEvidence.send')}
        </Button>
      </form>
    </Card>
  )
}

export function DisputePage() {
  const { id = '' } = useParams()
  const { t, lang } = useI18n()
  const [params, setParams] = useSearchParams()
  const role = params.get('as') === 'seller' ? 'seller' : 'buyer'
  const state = useAsync(
    async () => {
      const dispute = await calls.getDispute(id)
      const order = await calls.getOrder(dispute.order_id)
      return { dispute, order }
    },
    [id],
    POLL_MS,
  )

  if (state.loading && !state.data) return <Spinner label={t('common.loading')} />
  if (state.error && !state.data) return <ErrorNotice error={state.error} onRetry={state.reload} />
  if (!state.data) return null
  const { dispute, order } = state.data
  const closed = CLOSED.includes(dispute.status)

  return (
    <>
      <Card className="space-y-2">
        <h2 className="text-lg font-bold">{t('dispute.title')}</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt className="text-slate-600">{t('dispute.number')}</dt>
          <dd className="font-semibold">{dispute.id}</dd>
          <dt className="text-slate-600">{t('dispute.status')}</dt>
          <dd className="font-bold" data-testid="dispute-status">
            {t(`dispute.status.${dispute.status}`)}
          </dd>
          <dt className="text-slate-600">{t('order.number')}</dt>
          <dd>
            <Link className="text-blue-800 underline" to={`/order/${order.id}`}>
              {order.id}
            </Link>
          </dd>
        </dl>
        <div role="group" aria-label={t('dispute.role')} className="flex gap-2 pt-2">
          {(['buyer', 'seller'] as const).map((r) => (
            <Button
              key={r}
              variant={role === r ? 'primary' : 'secondary'}
              aria-pressed={role === r}
              className="flex-1 text-sm"
              onClick={() => setParams(r === 'seller' ? { as: 'seller' } : {})}
            >
              {t(`dispute.view.${r}`)}
            </Button>
          ))}
        </div>
        <p className="text-xs text-slate-500">{t('dispute.view.note')}</p>
      </Card>

      <Card>
        <h3 className="mb-1 font-bold">{t('dispute.claim')}</h3>
        {dispute.claim_type && (
          <p className="mb-1 text-sm font-semibold text-slate-700">
            {t(`report.type.${dispute.claim_type}`)}
          </p>
        )}
        <UserText>{dispute.claim_text}</UserText>
        <p className="mt-1 text-xs text-slate-500">{formatDateTime(dispute.opened_at, lang)}</p>
      </Card>

      {dispute.seller_response_text && (
        <Card>
          <h3 className="mb-1 font-bold">{t('seller.title')}</h3>
          <UserText>{dispute.seller_response_text}</UserText>
        </Card>
      )}

      <Card>
        <h3 className="mb-2 font-bold">{t('dispute.evidence')}</h3>
        <EvidenceList dispute={dispute} />
      </Card>

      {closed ? (
        <Card tone="info" role="status">
          <p>{t('dispute.resolved')}</p>
        </Card>
      ) : (
        <Card tone="warn" role="status">
          <p>{t('dispute.waiting')}</p>
        </Card>
      )}

      {!closed && role === 'seller' && (
        <SellerForm dispute={dispute} serverTime={order.server_time} onDone={state.reload} />
      )}
      {!closed && role === 'buyer' && (
        <BuyerEvidenceForm disputeId={dispute.id} onDone={state.reload} />
      )}
    </>
  )
}
