import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { calls } from '../api/calls'
import type { Schemas } from '../api/client'
import { useAction, useAsync } from '../api/hooks'
import { ErrorNotice } from '../components/ErrorNotice'
import { Button, Card, Label, Select, Spinner, TextArea } from '../components/ui'
import { useI18n } from '../i18n/useI18n'

const CLAIM_TYPES: Schemas['ClaimType'][] = [
  'NOT_RECEIVED',
  'WRONG_ITEM',
  'DAMAGED',
  'NOT_AS_DESCRIBED',
  'OTHER',
]
const MAX_CLAIM = 2000
const MAX_EVIDENCE = 4000

export function ReportProblemPage() {
  const { id = '' } = useParams()
  const { t, num } = useI18n()
  const navigate = useNavigate()
  const order = useAsync(() => calls.getOrder(id), [id])
  const [claimType, setClaimType] = useState<Schemas['ClaimType']>('NOT_RECEIVED')
  const [claim, setClaim] = useState('')
  const [evidence, setEvidence] = useState('')

  const submit = useAction(async () => {
    const dispute = await calls.createDispute({
      order_id: id,
      claim_text: claim.trim(),
      evidence_text: evidence.trim(),
      claim_type: claimType,
    })
    navigate(`/dispute/${dispute.id}`)
  })

  if (order.loading) return <Spinner label={t('common.loading')} />
  if (order.error) return <ErrorNotice error={order.error} onRetry={order.reload} />
  if (!order.data?.can_report_problem) {
    return (
      <Card tone="warn">
        <p className="mb-3">{t('report.notallowed')}</p>
        <Link to={`/order/${id}`} className="font-semibold text-blue-800 underline">
          {t('common.back')}
        </Link>
      </Card>
    )
  }

  return (
    <Card>
      <h2 className="mb-1 text-lg font-bold">{t('report.title')}</h2>
      <p className="mb-4 text-slate-700">{t('report.intro')}</p>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (claim.trim()) void submit.run()
        }}
      >
        <div>
          <Label htmlFor="claim-type">{t('report.type')}</Label>
          <Select
            id="claim-type"
            value={claimType}
            onChange={(e) => setClaimType(e.target.value as Schemas['ClaimType'])}
          >
            {CLAIM_TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`report.type.${type}`)}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="claim">{t('report.claim')}</Label>
          <TextArea
            id="claim"
            value={claim}
            maxLength={MAX_CLAIM}
            placeholder={t('report.claim.placeholder')}
            onChange={(e) => setClaim(e.target.value)}
          />
          <p className="text-xs text-slate-500">
            {num(MAX_CLAIM - claim.length)} {t('chars.left')}
          </p>
        </div>
        <div>
          <Label htmlFor="evidence">{t('report.evidence')}</Label>
          <TextArea
            id="evidence"
            value={evidence}
            maxLength={MAX_EVIDENCE}
            placeholder={t('report.evidence.placeholder')}
            onChange={(e) => setEvidence(e.target.value)}
          />
          <div className="mt-2 flex items-center gap-3">
            <Button variant="secondary" disabled aria-describedby="photo-note">
              {t('report.photo')}
            </Button>
            <span id="photo-note" className="text-xs text-slate-600">
              {t('report.photo.note')}
            </span>
          </div>
        </div>
        {submit.error && <ErrorNotice error={submit.error} />}
        <Button type="submit" disabled={!claim.trim() || submit.pending} className="w-full">
          {submit.pending ? t('common.sending') : t('report.submit')}
        </Button>
        <p className="text-xs text-slate-500">{t('report.limits')}</p>
      </form>
    </Card>
  )
}
