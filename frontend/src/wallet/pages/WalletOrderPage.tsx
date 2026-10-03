import { useState } from 'react'
import type { ChangeEvent } from 'react'
import { useParams } from 'react-router-dom'
import type { Schemas } from '../../api/client'
import { useAction, useAsync } from '../../api/hooks'
import { Timeline } from '../../components/Timeline'
import { Button, Card, Label, Spinner, TextArea, TextInput } from '../../components/ui'
import { useI18n } from '../../i18n/useI18n'
import { formatDateTime } from '../../lib/format'
import { wallet } from '../calls'
import { photoToDataUrl } from '../image'
import { PageTitle, Problem, Row, StatusChip, useMoney } from '../ui'

const CLAIM_TYPES = ['NOT_RECEIVED', 'WRONG_ITEM', 'DAMAGED', 'NOT_AS_DESCRIBED', 'OTHER'] as const

export function WalletOrderPage() {
  const { id = '' } = useParams()
  const { t, lang } = useI18n()
  const money = useMoney()
  const order = useAsync(() => wallet.order(id), [id], 8000)
  const o = order.data
  const lastDispute = o?.dispute_ids[o.dispute_ids.length - 1]
  const dispute = useAsync(
    () => (lastDispute ? wallet.dispute(lastDispute) : Promise.resolve(undefined)),
    [lastDispute],
    8000,
  )

  if (order.loading) return <Spinner label={t('common.loading')} />
  if (order.error || !o) return <Problem error={order.error!} />
  const isBuyer = o.role === 'BUYER'

  return (
    <>
      <PageTitle back={isBuyer ? '/history?tab=orders' : '/seller'}>
        {t('w.order.title', { id: o.id })}
      </PageTitle>

      <Card>
        <div className="flex items-center justify-between gap-3">
          <p className="text-2xl font-extrabold">{money(o.amount_bdt)}</p>
          <StatusChip status={o.status} />
        </div>
        <p className="mt-1 text-sm text-slate-700">{t(`w.status.${o.status}.about`)}</p>
        <div className="mt-3 divide-y divide-slate-200">
          <Row label={t('w.order.seller')}>
            {o.seller_name} {o.seller_phone ? `· ${o.seller_phone}` : ''}
          </Row>
          <Row label={t('w.order.buyer')}>
            {o.buyer_name} {o.buyer_phone ? `· ${o.buyer_phone}` : ''}
          </Row>
          <Row label={t('w.pay.yourref')}>{o.order_ref ?? '-'}</Row>
          <Row label={t('w.order.placed')}>{formatDateTime(o.placed_at, lang)}</Row>
          <Row label={t('w.order.claimed')}>
            {o.claimed_at ? formatDateTime(o.claimed_at, lang) : t('w.order.notclaimed')}
          </Row>
          {o.claim_deadline && <Row label={t('w.order.claimby')}>{formatDateTime(o.claim_deadline, lang)}</Row>}
        </div>
      </Card>

      {isBuyer && o.can_accept && <AcceptCard id={o.id} onDone={order.reload} />}
      {isBuyer && o.can_report && o.dispute_ids.length === 0 && <ReportCard id={o.id} onDone={order.reload} />}

      {o.proof && <ProofCard order={o} />}
      {!isBuyer && o.can_submit_proof && !o.proof && <ProofForm id={o.id} onDone={order.reload} />}

      {lastDispute && dispute.data && (
        <DisputeCard dispute={dispute.data} role={o.role} onDone={() => dispute.reload()} />
      )}

      <Card>
        <h3 className="mb-2 font-bold">{t('w.order.timeline')}</h3>
        <Timeline events={o.timeline} />
      </Card>
    </>
  )
}

function AcceptCard({ id, onDone }: { id: string; onDone: () => void }) {
  const { t } = useI18n()
  const [sure, setSure] = useState(false)
  const accept = useAction(async () => {
    await wallet.accept(id)
    onDone()
  })
  return (
    <Card tone="warn" className="!border-2">
      <h3 className="mb-1 font-bold text-amber-950">{t('w.accept.title')}</h3>
      <p className="mb-3 text-sm text-amber-950">{t('w.accept.sub')}</p>
      {!sure ? (
        <Button className="w-full" onClick={() => setSure(true)}>
          {t('w.accept.button')}
        </Button>
      ) : (
        <div className="space-y-2">
          <p className="text-sm font-bold text-red-900">{t('w.accept.sure')}</p>
          {accept.error && <Problem error={accept.error} />}
          <div className="grid grid-cols-2 gap-2">
            <Button variant="secondary" onClick={() => setSure(false)}>
              {t('w.cancel')}
            </Button>
            <Button disabled={accept.pending} onClick={() => void accept.run()}>
              {t('w.accept.yes')}
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

function ReportCard({ id, onDone }: { id: string; onDone: () => void }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [type, setType] = useState<(typeof CLAIM_TYPES)[number]>('NOT_RECEIVED')
  const [text, setText] = useState('')
  const report = useAction(async () => {
    await wallet.report(id, { claim_text: text.trim(), claim_type: type, evidence_text: '' })
    onDone()
  })
  if (!open) {
    return (
      <Button variant="secondary" className="w-full" onClick={() => setOpen(true)}>
        {t('w.report.open')}
      </Button>
    )
  }
  return (
    <Card>
      <h3 className="mb-1 font-bold">{t('w.report.title')}</h3>
      <p className="mb-3 text-sm text-slate-600">{t('w.report.sub')}</p>
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {CLAIM_TYPES.map((c) => (
            <button
              key={c}
              type="button"
              aria-pressed={type === c}
              onClick={() => setType(c)}
              className={`min-h-10 rounded-full border px-3 text-sm font-semibold ${
                type === c ? 'border-indigo-700 bg-indigo-700 text-white' : 'border-slate-300 bg-white'
              }`}
            >
              {t(`w.claimtype.${c}`)}
            </button>
          ))}
        </div>
        <div>
          <Label htmlFor="claim">{t('w.report.what')}</Label>
          <TextArea id="claim" value={text} maxLength={2000} onChange={(e) => setText(e.target.value)} />
        </div>
        {report.error && <Problem error={report.error} />}
        <Button className="w-full" disabled={text.trim().length < 10 || report.pending} onClick={() => void report.run()}>
          {report.pending ? t('w.working') : t('w.report.send')}
        </Button>
      </div>
    </Card>
  )
}

function ProofCard({ order }: { order: Schemas['MyOrderOut'] }) {
  const { t, lang } = useI18n()
  const [image, setImage] = useState<string | null>(null)
  const show = useAction(async () => {
    setImage((await wallet.proofImage(order.id)).image ?? null)
  })
  const proof = order.proof!
  return (
    <Card>
      <h3 className="mb-2 font-bold">{t('w.proof.title')}</h3>
      <Row label={t('w.proof.tracking')}>{proof.tracking_no}</Row>
      {proof.note && <Row label={t('w.proof.note')}>{proof.note}</Row>}
      <Row label={t('w.proof.when')}>{formatDateTime(proof.submitted_at, lang)}</Row>
      {proof.flags.length > 0 ? (
        <div className="mt-2 rounded-xl bg-amber-50 p-3">
          <p className="text-sm font-bold text-amber-900">{t('w.proof.flags')}</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-amber-900">
            {proof.flags.map((f) => (
              <li key={f}>{t(`w.flag.${f}`)}</li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-amber-900">{t('w.proof.flags.admin')}</p>
        </div>
      ) : (
        order.silence_deadline && (
          <p className="mt-2 rounded-xl bg-emerald-50 p-3 text-sm font-semibold text-emerald-900">
            {t('w.proof.auto', { time: formatDateTime(order.silence_deadline, lang) })}
          </p>
        )
      )}
      {proof.has_image && (
        <div className="mt-3">
          {image ? (
            <img src={image} alt={t('w.proof.photo')} className="max-h-72 w-full rounded-xl object-contain" />
          ) : (
            <Button variant="secondary" disabled={show.pending} onClick={() => void show.run()}>
              {t('w.proof.show')}
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}

function ProofForm({ id, onDone }: { id: string; onDone: () => void }) {
  const { t } = useI18n()
  const [tracking, setTracking] = useState('')
  const [note, setNote] = useState('')
  const [photo, setPhoto] = useState<string | null>(null)
  const [photoError, setPhotoError] = useState(false)
  const send = useAction(async () => {
    await wallet.proof(id, { tracking_no: tracking.trim(), note: note.trim(), image: photo })
    onDone()
  })
  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    setPhotoError(false)
    if (!file) return
    try {
      setPhoto(await photoToDataUrl(file))
    } catch {
      setPhoto(null)
      setPhotoError(true)
    }
  }
  return (
    <Card>
      <h3 className="mb-1 font-bold">{t('w.proof.form.title')}</h3>
      <p className="mb-3 text-sm text-slate-600">{t('w.proof.form.sub')}</p>
      <div className="space-y-3">
        <div>
          <Label htmlFor="tracking">{t('w.proof.tracking')}</Label>
          <TextInput id="tracking" value={tracking} maxLength={60} onChange={(e) => setTracking(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="pnote">{t('w.proof.note')}</Label>
          <TextInput id="pnote" value={note} maxLength={300} onChange={(e) => setNote(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="photo">{t('w.proof.photo')}</Label>
          <input id="photo" type="file" accept="image/*" onChange={(e) => void onFile(e)} className="block w-full text-sm" />
          {photo && <img src={photo} alt="" className="mt-2 max-h-40 rounded-xl" />}
          {photoError && <p className="mt-1 text-sm font-semibold text-red-800">{t('w.proof.photo.bad')}</p>}
        </div>
        {send.error && <Problem error={send.error} />}
        <Button className="w-full" disabled={tracking.trim().length < 3 || send.pending} onClick={() => void send.run()}>
          {send.pending ? t('w.working') : t('w.proof.send')}
        </Button>
      </div>
    </Card>
  )
}

function DisputeCard({
  dispute,
  role,
  onDone,
}: {
  dispute: Schemas['DisputeOut']
  role: 'BUYER' | 'SELLER'
  onDone: () => void
}) {
  const { t, lang } = useI18n()
  const [text, setText] = useState('')
  const respond = useAction(async () => {
    if (role === 'SELLER') await wallet.sellerResponse(dispute.id, text.trim())
    else await wallet.buyerEvidence(dispute.id, text.trim())
    setText('')
    onDone()
  })
  const resolved = dispute.status === 'RESOLVED'
  const canAnswer = !resolved && (role === 'BUYER' || !dispute.seller_response_text)
  return (
    <Card tone="danger">
      <h3 className="mb-1 font-bold text-red-950">{t('w.dispute.title', { id: dispute.id })}</h3>
      <p className="mb-2 text-sm font-semibold text-red-950">{t(`w.dispute.status.${dispute.status}`)}</p>
      <div className="rounded-xl bg-white/80 p-3 text-sm">
        <p className="font-bold">{t('w.dispute.claim')}</p>
        <p className="whitespace-pre-wrap">{dispute.claim_text}</p>
      </div>
      {dispute.evidence.length > 0 && (
        <ul className="mt-2 space-y-1 text-sm">
          {dispute.evidence.map((e, i) => (
            <li key={i} className="rounded-lg bg-white/70 p-2">
              <span className="font-bold">{t(`w.party.${e.party}`)}: </span>
              {e.description_text}
            </li>
          ))}
        </ul>
      )}
      {dispute.seller_response_text && (
        <div className="mt-2 rounded-xl bg-white/80 p-3 text-sm">
          <p className="font-bold">{t('w.dispute.seller')}</p>
          <p className="whitespace-pre-wrap">{dispute.seller_response_text}</p>
        </div>
      )}
      {dispute.seller_deadline && !dispute.seller_response_text && !resolved && (
        <p className="mt-2 text-xs font-semibold text-red-900">
          {t('w.dispute.deadline', { time: formatDateTime(dispute.seller_deadline, lang) })}
        </p>
      )}
      <p className="mt-2 text-xs text-red-950">{t('w.dispute.ai')}</p>
      {canAnswer && (
        <div className="mt-3 space-y-2">
          <Label htmlFor="answer">{role === 'SELLER' ? t('w.dispute.answer.seller') : t('w.dispute.answer.buyer')}</Label>
          <TextArea id="answer" value={text} maxLength={2000} onChange={(e) => setText(e.target.value)} />
          {respond.error && <Problem error={respond.error} />}
          <Button disabled={text.trim().length < 5 || respond.pending} onClick={() => void respond.run()}>
            {t('w.dispute.send')}
          </Button>
        </div>
      )}
    </Card>
  )
}
