import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { calls } from '../api/calls'
import type { Schemas } from '../api/client'
import { useAction, useAsync } from '../api/hooks'
import { BandBadge } from '../components/BandBadge'
import { DecisionPanel } from '../components/DecisionPanel'
import { ErrorNotice } from '../components/ErrorNotice'
import { FlagChips, ProbabilityBars, RouteBadge, TrustChangeView } from '../components/analyst'
import { Timeline } from '../components/Timeline'
import { UserText } from '../components/UserText'
import { Button, Card, Spinner } from '../components/ui'
import { useI18n } from '../i18n/useI18n'
import { formatDateTime, formatMoney } from '../lib/format'

const POLL_MS = 6000

function EvidenceItems({
  items,
  party,
}: {
  items: Schemas['DisputeOut']['evidence']
  party: 'BUYER' | 'SELLER'
}) {
  const { lang } = useI18n()
  const own = items.filter((i) => i.party === party)
  return (
    <ul className="space-y-2">
      {own.map((item, i) => (
        <li key={i} className="rounded-xl bg-slate-50 p-3">
          <p className="mb-1 text-xs text-slate-600">{formatDateTime(item.created_at, lang)}</p>
          <UserText>{item.description_text}</UserText>
        </li>
      ))}
    </ul>
  )
}

function Outcome({ outcome }: { outcome: Schemas['DecisionOut'] }) {
  const { t } = useI18n()
  return (
    <Card tone="good" role="status" aria-label="decision-outcome" className="space-y-3">
      <h3 className="text-lg font-bold">✓ {t('decision.done')}</h3>
      <p className="font-semibold">{t(`decision.${outcome.decision}`)}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <dt className="text-slate-700">{t('decision.order.status')}</dt>
        <dd className="font-bold" data-testid="outcome-order-status">
          {t(`status.${outcome.order_status}`)}
        </dd>
        <dt className="text-slate-700">{t('decision.ledger')}</dt>
        <dd>{outcome.ledger_balanced ? `✓ ${t('order.ledger.balanced')}` : '⚠'}</dd>
        {outcome.followed_suggestion !== null && (
          <>
            <dt className="text-slate-700">&nbsp;</dt>
            <dd>{outcome.followed_suggestion ? t('decision.followed') : t('decision.notfollowed')}</dd>
          </>
        )}
      </dl>
      {outcome.trust ? <TrustChangeView change={outcome.trust} /> : (
        outcome.decision === 'REFUND_BUYER' || outcome.decision === 'REJECT_CLAIM'
          ? <p className="text-sm text-slate-700">{t('score.none')}</p>
          : null
      )}
    </Card>
  )
}

export function AnalystCasePage() {
  const { id = '' } = useParams()
  const { t, lang, num } = useI18n()
  const state = useAsync(() => calls.analystCase(id), [id], POLL_MS)
  const [outcome, setOutcome] = useState<Schemas['DecisionOut'] | null>(null)
  const analyze = useAction(async () => {
    await calls.analyze(id)
    state.reload()
  })

  if (state.loading && !state.data) return <Spinner label={t('common.loading')} />
  if (state.error && !state.data) return <ErrorNotice error={state.error} onRetry={state.reload} />
  if (!state.data) return null
  const { dispute, order, buyer, seller, seller_trust, analysis, decisions } = state.data
  const sections = analysis?.explanation_sections[lang]
  const resolved = dispute.status === 'RESOLVED'

  return (
    <>
      <Card className="space-y-2">
        <Link to="/analyst" className="text-blue-800 underline">
          ← {t('case.back')}
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl font-bold">
            {t('case.title')} {dispute.id}
          </h2>
          <span className="font-bold" data-testid="dispute-status">
            {t(`dispute.status.${dispute.status}`)}
          </span>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-base">
          <dt className="text-slate-600">{t('order.number')}</dt>
          <dd>{order.id}</dd>
          <dt className="text-slate-600">{t('order.amount')}</dt>
          <dd className="font-semibold">{formatMoney(order.amount_bdt, lang, t('common.bdt'))}</dd>
          <dt className="text-slate-600">{t('order.status')}</dt>
          <dd>{t(`status.${order.status}`)}</dd>
          <dt className="text-slate-600">{t('order.courier')}</dt>
          <dd>{t(`courier.${order.courier_status}`)}</dd>
          <dt className="text-slate-600">{t('dispute.buyer')}</dt>
          <dd>{buyer.display_name}</dd>
          <dt className="text-slate-600">{t('dispute.seller')}</dt>
          <dd>
            {seller.display_name}{' '}
            <Link className="text-sm text-blue-800 underline" to={`/analyst/seller/${seller.id}`}>
              {t('score.history.link')}
            </Link>
          </dd>
        </dl>
        {seller_trust && (
          <p className="flex flex-wrap items-center gap-2">
            {t('case.seller.trust')}: <BandBadge band={seller_trust.band} />
            {seller_trust.score !== null && <strong>{num(seller_trust.score)}</strong>}
          </p>
        )}
      </Card>

      {analysis?.injection_detected && (
        <Card tone="danger" role="alert">
          <p className="font-bold text-red-900">⚠ {t('case.injection.title')}</p>
          <p>{t('case.injection.body')}</p>
        </Card>
      )}

      {!analysis && (
        <Card tone="info">
          <p className="mb-3">{t('case.analysis.none')}</p>
          {analyze.error && <ErrorNotice error={analyze.error} />}
          {!resolved && (
            <Button onClick={() => void analyze.run()} disabled={analyze.pending}>
              {analyze.pending ? t('case.analysis.running') : t('case.analysis.run')}
            </Button>
          )}
        </Card>
      )}

      {analysis && sections && (
        <section aria-label="analysis" className="space-y-3">
          <p className="text-sm font-semibold text-slate-700">{t('case.analysis.suggestion')}</p>
          <div className="grid gap-3 md:grid-cols-3">
            <Card aria-label="q-what">
              <h3 className="mb-1 font-bold">{t('case.q.what')}</h3>
              <p>{sections.what_happened}</p>
            </Card>
            <Card aria-label="q-risk">
              <h3 className="mb-1 font-bold">{t('case.q.risk')}</h3>
              <p>{sections.why_risky}</p>
            </Card>
            <Card aria-label="q-next">
              <h3 className="mb-1 font-bold">{t('case.q.next')}</h3>
              <p>{sections.next_step}</p>
            </Card>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Card className="space-y-2">
              <h3 className="font-bold">{t('case.flags')}</h3>
              <FlagChips flags={analysis.flags} />
              <p className="pt-2 font-bold">
                {t('case.route')}: <RouteBadge route={analysis.route} />
              </p>
              {analysis.route_reasons.length > 0 && (
                <p className="text-sm">
                  {t('case.route.why')}:{' '}
                  {analysis.route_reasons.map((r) => t(`reason.${r}`)).join(' · ')}
                </p>
              )}
              <p className="text-xs text-slate-600" data-testid="model-versions">
                {t('case.model.versions')}:{' '}
                {Object.entries(analysis.model_versions)
                  .map(([k, v]) => `${k} ${v}`)
                  .join(', ')}
              </p>
            </Card>
            <Card className="space-y-2">
              <h3 className="font-bold">{t('case.probs')}</h3>
              <ProbabilityBars probs={analysis.class_probs} />
              <p className="font-semibold">{t(`rec.${analysis.recommendation}`)}</p>
            </Card>
          </div>
        </section>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <Card aria-label="buyer-side" className="space-y-2">
          <h3 className="font-bold">{t('case.buyer.side')}</h3>
          {dispute.claim_type && (
            <p className="text-sm font-semibold text-slate-700">
              {t('case.claimtype')}: {t(`report.type.${dispute.claim_type}`)}
            </p>
          )}
          <UserText>{dispute.claim_text}</UserText>
          <p className="text-xs text-slate-600">{formatDateTime(dispute.opened_at, lang)}</p>
          <EvidenceItems items={dispute.evidence} party="BUYER" />
        </Card>
        <Card aria-label="seller-side" className="space-y-2">
          <h3 className="font-bold">{t('case.seller.side')}</h3>
          {dispute.seller_response_text ? (
            <UserText>{dispute.seller_response_text}</UserText>
          ) : (
            <p className="text-slate-600">{t('case.seller.noresponse')}</p>
          )}
          <EvidenceItems items={dispute.evidence} party="SELLER" />
        </Card>
      </div>

      <Card>
        <h3 className="mb-3 font-bold">{t('case.timeline')}</h3>
        <Timeline events={analysis?.timeline ?? order.timeline} />
      </Card>

      {decisions.length > 0 && (
        <Card aria-label="decision-history">
          <h3 className="mb-2 font-bold">{t('decision.history')}</h3>
          <ul className="space-y-2">
            {decisions.map((d, i) => (
              <li key={i} className="rounded-xl bg-slate-50 p-3">
                <p className="font-semibold">
                  {t(`decision.${d.decision}`)} · {d.analyst_id} · {formatDateTime(d.created_at, lang)}
                </p>
                <UserText>{d.note}</UserText>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {outcome && <Outcome outcome={outcome} />}

      {resolved ? (
        !outcome && (
          <Card tone="info" role="status">
            <p>{t('decision.resolved')}</p>
          </Card>
        )
      ) : (
        <DecisionPanel
          dispute={dispute}
          analysis={analysis}
          onDecided={(o) => {
            setOutcome(o)
            state.reload()
          }}
        />
      )}
    </>
  )
}
