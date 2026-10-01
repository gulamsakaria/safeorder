import { useState } from 'react'
import { calls } from '../api/calls'
import type { Schemas } from '../api/client'
import { useAction } from '../api/hooks'
import { useI18n } from '../i18n/useI18n'
import { ErrorNotice } from './ErrorNotice'
import { Button, Card, Label, TextArea, TextInput } from './ui'

const DECISIONS = ['REFUND_BUYER', 'REJECT_CLAIM', 'REQUEST_MORE_EVIDENCE', 'ESCALATE'] as const
type Decision = (typeof DECISIONS)[number]

/** Which decision matches which suggestion (a courier-issue suggestion is matched by a refund). */
const SUGGESTED: Record<string, Decision> = {
  SUGGEST_REFUND_BUYER: 'REFUND_BUYER',
  SUGGEST_REJECT_CLAIM: 'REJECT_CLAIM',
  SUGGEST_COURIER_ISSUE: 'REFUND_BUYER',
  NEEDS_MORE_EVIDENCE: 'REQUEST_MORE_EVIDENCE',
}
const ESCALATED_ALLOWED: Decision[] = ['REFUND_BUYER', 'REJECT_CLAIM']
const ANALYST_KEY = 'safeorder.analyst'
const DEFAULT_ANALYST = 'A-1'
const MAX_NOTE = 2000

function storedAnalyst(): string {
  try {
    return localStorage.getItem(ANALYST_KEY) || DEFAULT_ANALYST
  } catch {
    return DEFAULT_ANALYST
  }
}

/**
 * The only place money is moved after a dispute: a human writes a reason, picks an outcome, and
 * confirms. A fast-lane suggestion can be confirmed in one click, but never happens by itself.
 */
export function DecisionPanel({
  dispute,
  analysis,
  onDecided,
}: {
  dispute: Schemas['DisputeOut']
  analysis: Schemas['AnalysisOut'] | null
  onDecided: (outcome: Schemas['DecisionOut']) => void
}) {
  const { t } = useI18n()
  const [note, setNote] = useState('')
  const [analystId, setAnalystId] = useState(storedAnalyst)
  const [pending, setPending] = useState<Decision | null>(null)

  const send = useAction(async (decision: Decision, text: string) => {
    const outcome = await calls.decide(dispute.id, {
      decision,
      note: text,
      analyst_id: analystId.trim(),
    })
    try {
      localStorage.setItem(ANALYST_KEY, analystId.trim())
    } catch {
      // not remembering the analyst id is harmless
    }
    setPending(null)
    onDecided(outcome)
  })

  const escalated = dispute.status === 'ESCALATED'
  const suggested = analysis ? SUGGESTED[analysis.recommendation] : undefined
  const fastLane = analysis?.route === 'FAST_LANE_CONFIRM' && suggested
  const ready = note.trim().length > 0 && analystId.trim().length > 0
  const allowed = (d: Decision) => !escalated || ESCALATED_ALLOWED.includes(d)

  return (
    <Card aria-label="decision-panel" className="space-y-4">
      <h3 className="text-lg font-bold">{t('decision.title')}</h3>
      {escalated && <p className="text-sm font-semibold text-amber-900">{t('decision.locked.escalated')}</p>}

      <div>
        <Label htmlFor="decision-note">{t('decision.note')}</Label>
        <TextArea
          id="decision-note"
          value={note}
          maxLength={MAX_NOTE}
          placeholder={t('decision.note.placeholder')}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <div>
        <Label htmlFor="analyst-id">{t('decision.analyst')}</Label>
        <TextInput
          id="analyst-id"
          className="max-w-40"
          value={analystId}
          maxLength={40}
          onChange={(e) => setAnalystId(e.target.value)}
        />
      </div>

      {pending ? (
        <Card tone="warn" role="alertdialog" aria-label="confirm-decision">
          <p className="font-bold">{t('decision.confirm.title')}</p>
          <p className="font-semibold">{t(`decision.${pending}`)}</p>
          <p className="mb-3">{t(`decision.effect.${pending}`)}</p>
          {send.error && <ErrorNotice error={send.error} />}
          <div className="flex gap-2">
            <Button disabled={send.pending} onClick={() => void send.run(pending, note.trim())}>
              {send.pending ? t('decision.submitting') : t('decision.confirm')}
            </Button>
            <Button variant="secondary" disabled={send.pending} onClick={() => setPending(null)}>
              {t('decision.cancel')}
            </Button>
          </div>
        </Card>
      ) : (
        <>
          {fastLane && (
            <Button
              className="w-full"
              disabled={!analystId.trim() || send.pending}
              onClick={() => void send.run(suggested, note.trim() || t('decision.fastlane.note'))}
            >
              ⚡ {t('decision.fastlane')}: {t(`decision.${suggested}`)}
            </Button>
          )}
          <div className="grid gap-2 sm:grid-cols-2">
            {DECISIONS.map((d) => (
              <Button
                key={d}
                variant={d === 'REFUND_BUYER' ? 'danger' : 'secondary'}
                disabled={!ready || !allowed(d)}
                onClick={() => setPending(d)}
              >
                {t(`decision.${d}`)}
                {suggested === d && <span className="block text-xs font-normal">✓ {t('decision.suggested')}</span>}
              </Button>
            ))}
          </div>
          {send.error && <ErrorNotice error={send.error} />}
        </>
      )}
    </Card>
  )
}
