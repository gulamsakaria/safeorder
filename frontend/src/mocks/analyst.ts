import { http, HttpResponse } from 'msw'
import type { Schemas } from '../api/client'
import { STRINGS } from '../i18n/strings'
import {
  SELLERS,
  SELLER_DEADLINE_HOURS,
  TRUST,
  addEvent,
  hoursFromNow,
  iso,
  nowMs,
  persist,
  store,
  transfer,
} from './data'
import { findOrder, problem, view } from './shared'

type Analysis = Schemas['AnalysisOut']
const MOCK_VERSION = 'mock_illustration'
const HIGH_AMOUNT = 5000
const MIN_CONFIDENCE = 0.8
const INJECTION = /approve the refund|ignore (all )?(previous|prior)|এআই|রিফান্ড অনুমোদন/i
const CLASSES = ['SELLER_FAULT', 'BUYER_FALSE_CLAIM', 'COURIER_ISSUE', 'INSUFFICIENT_EVIDENCE']
const RECOMMENDATION: Record<string, string> = {
  SELLER_FAULT: 'SUGGEST_REFUND_BUYER',
  BUYER_FALSE_CLAIM: 'SUGGEST_REJECT_CLAIM',
  COURIER_ISSUE: 'SUGGEST_COURIER_ISSUE',
  INSUFFICIENT_EVIDENCE: 'NEEDS_MORE_EVIDENCE',
}
const AGREES: Record<string, string[]> = {
  SUGGEST_REFUND_BUYER: ['REFUND_BUYER'],
  SUGGEST_REJECT_CLAIM: ['REJECT_CLAIM'],
  SUGGEST_COURIER_ISSUE: ['REFUND_BUYER'],
  NEEDS_MORE_EVIDENCE: ['REQUEST_MORE_EVIDENCE'],
}
const ROUTE_PRIORITY: Record<string, number> = { HUMAN_REVIEW: 0, NOT_ANALYZED: 1, FAST_LANE_CONFIRM: 2 }
const BUYER = {
  display_name: 'Synthetic Buyer 000001',
  wallet_no: 'SIM-W-B000001',
  created_at: '2025-11-02T00:00:00Z',
}

/** Snapshots of a seller's trust; the first one is created on demand, like the real API does. */
export function ensureSnapshot(sellerId: string): Schemas['SnapshotOut'] {
  const list = store.snapshots.get(sellerId) ?? []
  if (list.length === 0) {
    const trust = TRUST[sellerId]
    store.snapshotSeq += 1
    list.push({
      id: store.snapshotSeq,
      score: trust.score,
      band: trust.band,
      reasons: trust.reasons,
      model_version: trust.model_version,
      trigger: 'INITIAL',
      created_at: iso(nowMs()),
    })
    store.snapshots.set(sellerId, list)
  }
  return list[list.length - 1]
}

function bandFor(score: number): Schemas['TrustBand'] {
  return score >= 70 ? 'TRUSTED' : score >= 40 ? 'CAUTION' : 'HIGH_RISK'
}

/**
 * An illustration of what the analyzer returns, built with simple rules so the console can be
 * shown without a trained classifier. It is labelled `mock_illustration` in the model versions.
 */
function buildAnalysis(order: Schemas['OrderOut'], dispute: Schemas['DisputeOut']): Analysis {
  const codeConfirmed = order.timeline.some((e) => e.event === 'DELIVERY_CODE_CONFIRMED')
  const texts = [dispute.claim_text, dispute.seller_response_text ?? '', ...dispute.evidence.map((e) => e.description_text)]
  const injection = texts.some((text) => INJECTION.test(text))
  const flags: string[] = []
  if (codeConfirmed && dispute.claim_type === 'NOT_RECEIVED') flags.push('CODE_CONTRADICTION')
  if (!dispute.evidence.some((e) => e.party === 'BUYER')) flags.push('EVIDENCE_EMPTY_OR_VAGUE')

  const [top, p] =
    dispute.claim_type === 'NOT_RECEIVED'
      ? codeConfirmed
        ? ['BUYER_FALSE_CLAIM', 0.82]
        : ['INSUFFICIENT_EVIDENCE', 0.55]
      : dispute.claim_type === 'DAMAGED'
        ? ['COURIER_ISSUE', 0.9]
        : dispute.claim_type === 'WRONG_ITEM'
          ? ['SELLER_FAULT', 0.9]
          : ['INSUFFICIENT_EVIDENCE', 0.6]
  const rest = (1 - (p as number)) / (CLASSES.length - 1)
  const probs = Object.fromEntries(CLASSES.map((c) => [c, c === top ? p : rest])) as Record<string, number>

  const reasons: string[] = []
  if (top === 'INSUFFICIENT_EVIDENCE') reasons.push('INSUFFICIENT_EVIDENCE_PREDICTED')
  if (flags.length) reasons.push('FLAGS_PRESENT')
  if (injection) reasons.push('INJECTION_DETECTED')
  if ((p as number) < MIN_CONFIDENCE) reasons.push('LOW_CONFIDENCE')
  if (order.amount_bdt > HIGH_AMOUNT) reasons.push('HIGH_AMOUNT')

  const timeline = [...order.timeline.filter((e) => !e.event.startsWith('DISPUTE'))]
  timeline.push({ t: dispute.opened_at, event: 'BUYER_DISPUTE_FILED' })
  if (dispute.seller_responded_at) timeline.push({ t: dispute.seller_responded_at, event: 'SELLER_RESPONDED' })
  timeline.sort((a, b) => a.t.localeCompare(b.t))

  const recommendation = RECOMMENDATION[top as string]
  const section = (lang: 'bn' | 'en') => {
    const S = STRINGS[lang]
    const flagText = flags.length ? flags.map((f) => S[`flag.${f}`]).join('; ') : lang === 'bn' ? 'কোনো অসঙ্গতি পাওয়া যায়নি।' : 'No consistency problems were found.'
    return {
      what_happened: `${order.amount_bdt} ${S['common.bdt']} · ${S[`courier.${order.courier_status}`]} · ${S[`status.${order.status}`]}`,
      why_risky: `${flagText} ${S[`class.${top}`]}: ${Math.round((p as number) * 100)}%.`,
      next_step: `${S[`rec.${recommendation}`]}. ${reasons.length ? reasons.map((r) => S[`reason.${r}`]).join(', ') : S['analyst.route.FAST_LANE_CONFIRM']}`,
    }
  }
  return {
    dispute_id: dispute.id,
    order_id: order.id,
    timeline,
    class_probs: probs,
    flags: injection ? [...flags, 'INJECTION_DETECTED'] : flags,
    injection_detected: injection,
    recommendation,
    route: reasons.length ? 'HUMAN_REVIEW' : 'FAST_LANE_CONFIRM',
    route_reasons: reasons,
    explanation_en: '',
    explanation_bn: '',
    explanation_sections: { en: section('en'), bn: section('bn') },
    model_versions: { dispute: MOCK_VERSION, rules: 'rules_v1' },
  }
}

function sellerOf(order: Schemas['OrderOut']): Schemas['SellerPublic'] {
  return SELLERS.find((s) => s.id === order.seller_id) ?? SELLERS[0]
}

export const analystHandlers = [
  http.get('*/api/analyst/queue', ({ request }) => {
    const url = new URL(request.url)
    const routeFilter = url.searchParams.get('route')
    const minAmount = Number(url.searchParams.get('min_amount_bdt') ?? 0)
    const items: Schemas['QueueItemOut'][] = []
    for (const dispute of store.disputes.values()) {
      if (dispute.status === 'RESOLVED') continue
      const order = store.orders.get(dispute.order_id)?.order
      const analysis = store.analyses.get(dispute.id)
      const route = analysis?.route ?? null
      if (routeFilter && (route ?? 'NOT_ANALYZED') !== routeFilter) continue
      if ((order?.amount_bdt ?? 0) < minAmount) continue
      items.push({
        dispute_id: dispute.id,
        order_id: dispute.order_id,
        status: dispute.status,
        amount_bdt: order?.amount_bdt ?? 0,
        opened_at: dispute.opened_at,
        seller_deadline: dispute.seller_deadline,
        analyzed: analysis !== undefined,
        route,
        recommendation: analysis?.recommendation ?? null,
        flags: analysis?.flags ?? [],
      })
    }
    items.sort(
      (a, b) =>
        ROUTE_PRIORITY[a.route ?? 'NOT_ANALYZED'] - ROUTE_PRIORITY[b.route ?? 'NOT_ANALYZED'] ||
        b.amount_bdt - a.amount_bdt ||
        a.opened_at.localeCompare(b.opened_at),
    )
    return HttpResponse.json<Schemas['QueueItemOut'][]>(items)
  }),

  http.get('*/api/analyst/disputes/:id', ({ params }) => {
    const dispute = store.disputes.get(String(params.id))
    if (!dispute) return problem(404, 'NOT_FOUND', `dispute ${String(params.id)} not found`)
    const found = findOrder(dispute.order_id)!
    const snapshots = store.snapshots.get(found.order.seller_id)
    return HttpResponse.json<Schemas['AnalystCaseOut']>({
      dispute,
      order: view(found.order),
      buyer: { id: found.order.buyer_id, ...BUYER },
      seller: sellerOf(found.order),
      seller_trust: snapshots?.[snapshots.length - 1] ?? null,
      analysis: store.analyses.get(dispute.id) ?? null,
      decisions: store.decisions.get(dispute.id) ?? [],
    })
  }),

  http.post('*/api/disputes/:id/analyze', ({ params }) => {
    const dispute = store.disputes.get(String(params.id))
    if (!dispute) return problem(404, 'NOT_FOUND', `dispute ${String(params.id)} not found`)
    if (dispute.status === 'RESOLVED') return problem(409, 'ILLEGAL_STATE', 'this dispute is already resolved')
    const analysis = buildAnalysis(findOrder(dispute.order_id)!.order, dispute)
    store.analyses.set(dispute.id, analysis)
    if (dispute.status === 'OPEN' || dispute.status === 'SELLER_RESPONDED') dispute.status = 'ANALYZED'
    persist()
    return HttpResponse.json<Analysis>(analysis)
  }),

  http.post('*/api/analyst/disputes/:id/decision', async ({ params, request }) => {
    const dispute = store.disputes.get(String(params.id))
    if (!dispute) return problem(404, 'NOT_FOUND', `dispute ${String(params.id)} not found`)
    const body = (await request.json()) as Schemas['DecisionRequest']
    if (!body.note?.trim()) return problem(422, 'VALIDATION_ERROR', 'note: a decision needs a written note')
    const order = findOrder(dispute.order_id)!.order
    const resolvedOrder = order.status !== 'DISPUTED' && order.status !== 'ESCALATED'
    const escalatedBlocked =
      order.status === 'ESCALATED' && (body.decision === 'ESCALATE' || body.decision === 'REQUEST_MORE_EVIDENCE')
    if (dispute.status === 'RESOLVED' || resolvedOrder || escalatedBlocked) {
      return problem(409, 'ILLEGAL_STATE', `decision ${body.decision} is not allowed in status ${order.status}`)
    }

    const analysis = store.analyses.get(dispute.id)
    const followed =
      analysis && body.decision !== 'ESCALATE'
        ? (AGREES[analysis.recommendation] ?? []).includes(body.decision)
        : null
    let trust: Schemas['TrustChange'] | null = null

    if (body.decision === 'REFUND_BUYER' || body.decision === 'REJECT_CLAIM') {
      const refund = body.decision === 'REFUND_BUYER'
      order.status = refund ? 'REFUNDED' : 'RELEASED'
      if (!refund) order.released_at = iso(nowMs())
      transfer(order, 'HOLD', refund ? 'BUYER_WALLET' : 'SELLER_WALLET', refund ? 'REFUND_TO_BUYER' : 'CLAIM_REJECTED_RELEASE')
      addEvent(order, refund ? 'REFUNDED_TO_BUYER' : 'FUNDS_RELEASED_TO_SELLER')
      dispute.status = 'RESOLVED'
      const before = ensureSnapshot(order.seller_id)
      const score = before.score === null ? null : refund ? Math.max(0, before.score - 3) : before.score
      store.snapshotSeq += 1
      const after: Schemas['SnapshotOut'] = {
        ...before,
        id: store.snapshotSeq,
        score,
        band: score === null ? before.band : bandFor(score),
        trigger: 'DISPUTE_RESOLVED',
        created_at: iso(nowMs()),
      }
      store.snapshots.get(order.seller_id)!.push(after)
      trust = { before, after }
    } else if (body.decision === 'ESCALATE') {
      order.status = 'ESCALATED'
      dispute.status = 'ESCALATED'
      addEvent(order, 'ESCALATED')
    } else {
      dispute.status = 'OPEN'
      dispute.seller_deadline = hoursFromNow(SELLER_DEADLINE_HOURS)
      addEvent(order, 'MORE_EVIDENCE_REQUESTED')
    }

    const records = store.decisions.get(dispute.id) ?? []
    records.push({ analyst_id: body.analyst_id, decision: body.decision, note: body.note.trim(), created_at: iso(nowMs()) })
    store.decisions.set(dispute.id, records)
    persist()
    return HttpResponse.json<Schemas['DecisionOut']>({
      dispute_id: dispute.id,
      decision: body.decision,
      order_status: order.status,
      dispute_status: dispute.status,
      ledger_balanced: view(order).ledger_balanced,
      followed_suggestion: followed,
      trust,
      seller_deadline: dispute.seller_deadline,
    })
  }),

  http.get('*/api/sellers/:id/score-history', ({ params }) => {
    const id = String(params.id)
    if (!SELLERS.some((s) => s.id === id)) return problem(404, 'NOT_FOUND', 'seller not found')
    return HttpResponse.json<Schemas['ScoreHistoryOut']>({
      seller_id: id,
      snapshots: store.snapshots.get(id) ?? [],
    })
  }),
]
