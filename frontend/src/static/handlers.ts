/**
 * Request handlers of the static site: the same HTTP contract as the backend, answered in the
 * browser by the real models (src/engine). They come first; the order, dispute and clock handlers
 * of the mock server (src/mocks) follow, so one set of rules serves both.
 */

import { HttpResponse, getResponse, http } from 'msw'
import type { RequestHandler } from 'msw'
import type { Schemas } from '../api/client'
import { analyze, getEngine, nextCounters, trustCheck } from '../engine/engine'
import type { SellerRow } from '../engine/engine'
import type { DisputeCase } from '../engine/analyzer'
import type { TrustResult } from '../engine/trust'
import { SELLERS, SELLER_DEADLINE_HOURS, addEvent, hoursFromNow, iso, nowMs, persist, resetStore, store, transfer } from '../mocks/data'
import { handlers as mockHandlers } from '../mocks/handlers'
import { findOrder, problem, view } from '../mocks/shared'

type Analysis = Schemas['AnalysisOut']
const SEARCH_LIMIT = 10
const RESPONSE_WINDOW_DAYS = 90
const DAY_MS = 86_400_000
const ROUTE_PRIORITY: Record<string, number> = { HUMAN_REVIEW: 0, NOT_ANALYZED: 1, FAST_LANE_CONFIRM: 2 }
const AGREES: Record<string, string[]> = {
  SUGGEST_REFUND_BUYER: ['REFUND_BUYER'],
  SUGGEST_REJECT_CLAIM: ['REJECT_CLAIM'],
  SUGGEST_COURIER_ISSUE: ['REFUND_BUYER'],
  NEEDS_MORE_EVIDENCE: ['REQUEST_MORE_EVIDENCE'],
}

/** Puts the 3,000 synthetic sellers of the exported data in place of the mock's four. */
export function installSellers(): void {
  const rows = getEngine().sellers
  SELLERS.splice(
    0,
    SELLERS.length,
    ...rows.map(({ id, display_name, wallet_no, category, created_at }) => ({ id, display_name, wallet_no, category, created_at })),
  )
}

function sellerRow(id: string): SellerRow | undefined {
  return getEngine().byId.get(id)
}

function toResponse(result: TrustResult, sellerId: string): Schemas['TrustCheckResponse'] {
  return {
    seller_id: sellerId,
    score: result.score,
    band: result.band,
    limited_history: result.limited_history,
    reasons: result.reasons as Schemas['ReasonOut'][],
    model_version: getEngine().trust.version,
    generated_at: iso(nowMs()),
    requires_extra_confirmation: result.requires_extra_confirmation,
  }
}

function snapshotOf(result: TrustResult, trigger: Schemas['SnapshotTrigger']): Schemas['SnapshotOut'] {
  store.snapshotSeq += 1
  return {
    id: store.snapshotSeq,
    score: result.score,
    band: result.band,
    reasons: result.reasons as Schemas['ReasonOut'][],
    model_version: getEngine().trust.version,
    trigger,
    created_at: iso(nowMs()),
  }
}

function ensureSnapshot(sellerId: string): Schemas['SnapshotOut'] {
  const list = store.snapshots.get(sellerId) ?? []
  if (list.length === 0) {
    const seller = sellerRow(sellerId)!
    list.push(snapshotOf(trustCheck(seller, store.counters.get(sellerId)), 'INITIAL'))
    store.snapshots.set(sellerId, list)
  }
  return list[list.length - 1]
}

function buyerOf(id: string): Schemas['BuyerPublic'] {
  const known = getEngine().buyers.find((b) => b.id === id)
  if (known) return known
  const digits = id.replace(/\D/g, '').padStart(6, '0')
  return { id, display_name: `Synthetic Buyer ${digits}`, wallet_no: `SIM-W-B${digits}`, created_at: '2025-01-01T00:00:00Z' }
}

/** The facts of a dispute, in the shape the analyzer expects (the same as backend/app/analyzer/case.py). */
function caseOf(disputeId: string): DisputeCase {
  const dispute = store.disputes.get(disputeId)!
  const order = findOrder(dispute.order_id)!.order
  const events = order.timeline
  const courier: [string, string][] = events
    .filter((e) => e.event.startsWith('COURIER_'))
    .map((e) => [e.event.slice('COURIER_'.length).toLowerCase(), e.t])
  const confirmed = events.find((e) => e.event === 'DELIVERY_CODE_CONFIRMED')
  const opened = Date.parse(dispute.opened_at)
  let count = 0
  for (const other of store.disputes.values()) {
    const otherOrder = findOrder(other.order_id)?.order
    const at = Date.parse(other.opened_at)
    if (otherOrder?.buyer_id === order.buyer_id && other.opened_by === 'BUYER' && at <= opened && at > opened - RESPONSE_WINDOW_DAYS * DAY_MS) {
      count += 1
    }
  }
  return {
    dispute_id: dispute.id,
    order_id: order.id,
    amount_bdt: order.amount_bdt,
    placed_at: order.placed_at,
    opened_at: dispute.opened_at,
    claim_text: dispute.claim_text,
    courier_events: courier,
    code_confirmed_at: confirmed ? confirmed.t : null,
    claim_type: dispute.claim_type ?? null,
    seller_response_text: dispute.seller_response_text,
    seller_responded_at: dispute.seller_responded_at,
    buyer_evidence: dispute.evidence.filter((e) => e.party === 'BUYER').map((e) => e.description_text),
    seller_evidence: dispute.evidence.filter((e) => e.party === 'SELLER').map((e) => e.description_text),
    buyer_disputes_in_window: Math.max(1, count),
  }
}

const staticHandlers: RequestHandler[] = [
  http.get('*/api/sellers/search', ({ request }) => {
    const q = (new URL(request.url).searchParams.get('q') ?? '').trim().toLowerCase()
    if (!q) return problem(422, 'VALIDATION_ERROR', 'q: field required')
    const found = SELLERS.filter((s) => s.display_name.toLowerCase().includes(q) || s.wallet_no.toLowerCase().includes(q)).slice(0, SEARCH_LIMIT)
    return HttpResponse.json<Schemas['SellerPublic'][]>(found)
  }),

  http.post('*/api/trust/check', async ({ request }) => {
    const body = (await request.json()) as Schemas['TrustCheckRequest']
    const seller = body.seller_id ? sellerRow(body.seller_id) : getEngine().sellers.find((s) => s.wallet_no === body.wallet_no)
    if (!seller) return problem(404, 'NOT_FOUND', 'seller not found')
    ensureSnapshot(seller.id)
    persist()
    return HttpResponse.json<Schemas['TrustCheckResponse']>(toResponse(trustCheck(seller, store.counters.get(seller.id)), seller.id))
  }),

  http.get('*/api/sellers/:id/score-history', ({ params }) => {
    const id = String(params.id)
    if (!sellerRow(id)) return problem(404, 'NOT_FOUND', 'seller not found')
    return HttpResponse.json<Schemas['ScoreHistoryOut']>({ seller_id: id, snapshots: store.snapshots.get(id) ?? [] })
  }),

  http.get('*/api/metrics/summary', () =>
    HttpResponse.json<Schemas['MetricsOut']>({ available: true, summary: getEngine().summary as Record<string, unknown>, reports: {} }),
  ),

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
    const order = findOrder(dispute.order_id)!.order
    const seller = SELLERS.find((s) => s.id === order.seller_id)!
    const snapshots = store.snapshots.get(order.seller_id)
    return HttpResponse.json<Schemas['AnalystCaseOut']>({
      dispute,
      order: view(order),
      buyer: buyerOf(order.buyer_id),
      seller,
      seller_trust: snapshots?.[snapshots.length - 1] ?? null,
      analysis: store.analyses.get(dispute.id) ?? null,
      decisions: store.decisions.get(dispute.id) ?? [],
    })
  }),

  http.post('*/api/disputes/:id/analyze', ({ params }) => {
    const dispute = store.disputes.get(String(params.id))
    if (!dispute) return problem(404, 'NOT_FOUND', `dispute ${String(params.id)} not found`)
    if (dispute.status === 'RESOLVED') return problem(409, 'ILLEGAL_STATE', 'this dispute is already resolved')
    const { flag_details: _details, ...analysis } = analyze(caseOf(dispute.id))
    void _details
    store.analyses.set(dispute.id, analysis as Analysis)
    if (dispute.status === 'OPEN' || dispute.status === 'SELLER_RESPONDED') dispute.status = 'ANALYZED'
    persist()
    return HttpResponse.json<Analysis>(analysis as Analysis)
  }),

  http.post('*/api/analyst/disputes/:id/decision', async ({ params, request }) => {
    const dispute = store.disputes.get(String(params.id))
    if (!dispute) return problem(404, 'NOT_FOUND', `dispute ${String(params.id)} not found`)
    const body = (await request.json()) as Schemas['DecisionRequest']
    if (!body.note?.trim()) return problem(422, 'VALIDATION_ERROR', 'note: a decision needs a written note')
    const order = findOrder(dispute.order_id)!.order
    const resolvedOrder = order.status !== 'DISPUTED' && order.status !== 'ESCALATED'
    const escalatedBlocked = order.status === 'ESCALATED' && (body.decision === 'ESCALATE' || body.decision === 'REQUEST_MORE_EVIDENCE')
    if (dispute.status === 'RESOLVED' || resolvedOrder || escalatedBlocked) {
      return problem(409, 'ILLEGAL_STATE', `decision ${body.decision} is not allowed in status ${order.status}`)
    }
    const analysis = store.analyses.get(dispute.id)
    const followed = analysis && body.decision !== 'ESCALATE' ? (AGREES[analysis.recommendation] ?? []).includes(body.decision) : null
    let trust: Schemas['TrustChange'] | null = null

    if (body.decision === 'REFUND_BUYER' || body.decision === 'REJECT_CLAIM') {
      const refund = body.decision === 'REFUND_BUYER'
      order.status = refund ? 'REFUNDED' : 'RELEASED'
      if (!refund) order.released_at = iso(nowMs())
      transfer(order, 'HOLD', refund ? 'BUYER_WALLET' : 'SELLER_WALLET', refund ? 'REFUND_TO_BUYER' : 'CLAIM_REJECTED_RELEASE')
      addEvent(order, refund ? 'REFUNDED_TO_BUYER' : 'FUNDS_RELEASED_TO_SELLER')
      dispute.status = 'RESOLVED'
      const seller = sellerRow(order.seller_id)!
      const before = ensureSnapshot(order.seller_id)
      const counters = nextCounters(seller, store.counters.get(seller.id), refund)
      store.counters.set(seller.id, counters)
      const after = snapshotOf(trustCheck(seller, counters), 'DISPUTE_RESOLVED')
      store.snapshots.get(seller.id)!.push(after)
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

  http.post('*/api/demo/reset', async ({ request }) => {
    const { scenario_set: set = 'default' } = (await request.json()) as Schemas['DemoResetRequest']
    resetStore()
    const scenarios = set === 'demo' ? await loadScenarios() : []
    persist()
    return HttpResponse.json<Schemas['DemoResetOut']>({
      scenario_set: set,
      loaded: { sellers: SELLERS.length, buyers: getEngine().buyers.length },
      now: iso(nowMs()),
      scenarios,
    })
  }),
]

/** Every handler, the static ones first. */
export const allHandlers: RequestHandler[] = [...staticHandlers, ...mockHandlers]

const ORIGIN = (): string => globalThis.location?.origin ?? 'http://localhost'

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const request = new Request(`${ORIGIN()}/api${path}`, {
    method,
    headers: { 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const response = await getResponse(allHandlers, request)
  if (!response || !response.ok) throw new Error(`demo setup: ${method} ${path} failed (${response?.status})`)
  return (await response.json()) as T
}

/** The seven demo scenarios, set up through the same endpoints as the backend does it. */
async function loadScenarios(): Promise<Schemas['DemoScenarioOut'][]> {
  const { scenarios } = getEngine()
  const { picks, texts, amounts } = scenarios
  const buyers = getEngine().buyers.map((b) => b.id)
  const [happyBuyer, faultBuyer, claimant, injector, judgeBuyer] = buyers
  const name = (id: string) => sellerRow(id)?.display_name ?? null
  const place = (buyer: string, sellerId: string, amount: number) =>
    call<Schemas['OrderOut']>('POST', '/orders', {
      buyer_id: buyer, seller_id: sellerId, amount_bdt: amount,
      product_category: sellerRow(sellerId)?.category ?? 'clothing',
    })
  const report = (orderId: string, claim: string, evidence: string) =>
    call<Schemas['DisputeOut']>('POST', '/disputes', { order_id: orderId, claim_type: 'NOT_RECEIVED', claim_text: claim, evidence_text: evidence })
  const analyse = async (id: string) => {
    await call('POST', `/disputes/${id}/analyze`, {})
    return 'done'
  }
  const out: Schemas['DemoScenarioOut'][] = []

  out.push({ number: 1, key: 'fake_seller', seller_id: picks.fake, seller_name: name(picks.fake), detail: 'Open Trust Check for this seller: HIGH_RISK with reasons.' })

  let order = await place(happyBuyer, picks.happy, amounts.happy)
  await call('POST', '/sim/courier-event', { order_id: order.id, status: 'in_transit' })
  out.push({ number: 2, key: 'happy_path', seller_id: picks.happy, seller_name: name(picks.happy), buyer_id: happyBuyer, order_id: order.id, delivery_code: order.delivery_code, detail: 'Confirm with the code, then fast-forward 72 hours: the hold is released.' })

  order = await place(faultBuyer, picks.fault, amounts.fault)
  let dispute = await report(order.id, texts.CLAIM_NOT_RECEIVED_BN, texts.SELLER_FAULT_EVIDENCE_BN)
  await call('POST', `/disputes/${dispute.id}/seller-response`, { response_text: texts.SELLER_FAULT_RESPONSE_BN, evidence_text: '' })
  out.push({ number: 3, key: 'seller_fault', seller_id: picks.fault, seller_name: name(picks.fault), buyer_id: faultBuyer, order_id: order.id, dispute_id: dispute.id, analysis: await analyse(dispute.id), detail: "Analyst refunds the buyer; the seller's score drops (before and after)." })

  for (const [key, amount] of [['prior_a', scenarios.prior_claim_amounts[0]], ['prior_b', scenarios.prior_claim_amounts[1]]] as const) {
    const earlier = await place(claimant, picks[key], amount)
    const earlierDispute = await report(earlier.id, texts.PRIOR_CLAIM_BN, texts.PRIOR_EVIDENCE_BN)
    await call('POST', `/analyst/disputes/${earlierDispute.id}/decision`, { decision: 'REJECT_CLAIM', note: texts.PRIOR_NOTE, analyst_id: scenarios.analyst })
  }
  order = await place(claimant, picks.false_claim, amounts.false_claim)
  await call('POST', '/sim/courier-event', { order_id: order.id, status: 'in_transit' })
  await call('POST', '/sim/courier-event', { order_id: order.id, status: 'delivered' })
  await call('POST', `/orders/${order.id}/confirm-delivery`, { code: order.delivery_code })
  dispute = await report(order.id, texts.CLAIM_NOT_RECEIVED_BN, texts.FALSE_CLAIM_EVIDENCE_BN)
  await call('POST', `/disputes/${dispute.id}/seller-response`, { response_text: texts.FALSE_CLAIM_RESPONSE_BN, evidence_text: texts.FALSE_CLAIM_SELLER_EVIDENCE_BN })
  out.push({ number: 4, key: 'false_claim', seller_id: picks.false_claim, seller_name: name(picks.false_claim), buyer_id: claimant, order_id: order.id, dispute_id: dispute.id, analysis: await analyse(dispute.id), detail: 'Code was used but the buyer says not received, third claim: human review.' })

  out.push({ number: 5, key: 'honest_new', seller_id: picks.new, seller_name: name(picks.new), detail: 'Open Trust Check: LIMITED_HISTORY, not treated as a scammer.' })

  order = await place(injector, picks.injection, amounts.injection)
  dispute = await report(order.id, texts.INJECTION_CLAIM_BN, texts.INJECTION_EVIDENCE)
  out.push({ number: 6, key: 'injection', seller_id: picks.injection, seller_name: name(picks.injection), buyer_id: injector, order_id: order.id, dispute_id: dispute.id, analysis: await analyse(dispute.id), detail: 'Evidence text tells the AI to approve: only the injection flag changes.' })

  order = await place(judgeBuyer, picks.happy, amounts.judge)
  out.push({ number: 7, key: 'judge_case', seller_id: picks.happy, seller_name: name(picks.happy), buyer_id: judgeBuyer, order_id: order.id, delivery_code: order.delivery_code, detail: 'A judge reports a problem on this held order in their own words; the analyst console then shows the probabilities and the route.' })
  return out
}
