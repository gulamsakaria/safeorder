import { http, HttpResponse } from 'msw'
import type { Schemas } from '../api/client'
import {
  SELLERS,
  SELLER_DEADLINE_HOURS,
  TRUST,
  addEvent,
  deliveryCodeFor,
  hoursFromNow,
  iso,
  nowMs,
  persist,
  processTimers,
  resetStore,
  store,
  transfer,
} from './data'
import { analystHandlers, ensureSnapshot } from './analyst'
import { REPORTABLE, deliver, findOrder, problem, view } from './shared'

/**
 * An in-browser stand-in for the API. Request and response shapes use the generated types, so a
 * change in docs/openapi.json breaks the build here before it can break a screen.
 */
export const handlers = [
  http.get('*/api/sellers/search', ({ request }) => {
    const q = (new URL(request.url).searchParams.get('q') ?? '').trim().toLowerCase()
    if (!q) return problem(422, 'VALIDATION_ERROR', 'q: field required')
    const found = SELLERS.filter(
      (s) => s.display_name.toLowerCase().includes(q) || s.wallet_no.toLowerCase().includes(q),
    )
    return HttpResponse.json<Schemas['SellerPublic'][]>(found)
  }),

  http.post('*/api/trust/check', async ({ request }) => {
    const body = (await request.json()) as Schemas['TrustCheckRequest']
    const result = TRUST[body.seller_id ?? '']
    if (!result) return problem(404, 'NOT_FOUND', 'seller not found')
    ensureSnapshot(result.seller_id)
    persist()
    return HttpResponse.json<Schemas['TrustCheckResponse']>(result)
  }),

  http.post('*/api/orders', async ({ request }) => {
    const body = (await request.json()) as Schemas['CreateOrderRequest']
    if (!SELLERS.some((s) => s.id === body.seller_id)) return problem(404, 'NOT_FOUND', 'seller not found')
    if (!(body.amount_bdt > 0)) return problem(422, 'VALIDATION_ERROR', 'amount_bdt: must be positive')
    store.orderSeq += 1
    const id = `O-${String(store.orderSeq).padStart(4, '0')}`
    const order: Schemas['OrderOut'] = {
      id,
      buyer_id: body.buyer_id,
      seller_id: body.seller_id,
      product_category: body.product_category,
      amount_bdt: body.amount_bdt,
      status: 'HELD',
      placed_at: iso(nowMs()),
      delivered_at: null,
      hold_until: null,
      released_at: null,
      courier_status: 'not_dispatched',
      ledger: [],
      ledger_balanced: true,
      timeline: [],
      dispute_ids: [],
      can_report_problem: true,
      server_time: iso(nowMs()),
      delivery_code: null,
    }
    transfer(order, 'BUYER_WALLET', 'HOLD', 'SAFE_ORDER_HOLD')
    addEvent(order, 'ORDER_PLACED_AND_HELD')
    const code = deliveryCodeFor(store.orderSeq)
    store.orders.set(id, { order, code, dispatched: false })
    persist()
    return HttpResponse.json<Schemas['OrderOut']>(view(order, code), { status: 201 })
  }),

  http.get('*/api/orders/:id', ({ params }) => {
    const found = findOrder(String(params.id))
    if (!found) return problem(404, 'NOT_FOUND', `order ${String(params.id)} not found`)
    return HttpResponse.json<Schemas['OrderOut']>(view(found.order))
  }),

  http.post('*/api/orders/:id/confirm-delivery', async ({ params, request }) => {
    const found = findOrder(String(params.id))
    if (!found) return problem(404, 'NOT_FOUND', `order ${String(params.id)} not found`)
    const { code } = (await request.json()) as Schemas['ConfirmDeliveryRequest']
    if (code !== found.code) {
      addEvent(found.order, 'DELIVERY_CODE_REJECTED')
      persist()
      return problem(400, 'INVALID_CODE', 'the delivery code is wrong')
    }
    if (found.order.status === 'HELD') {
      addEvent(found.order, 'DELIVERY_CODE_CONFIRMED')
      deliver(found.order, 'DELIVERED')
    } else if (found.order.status === 'DELIVERED') {
      addEvent(found.order, 'DELIVERY_CODE_CONFIRMED')
    } else {
      return problem(409, 'ILLEGAL_STATE', `cannot confirm delivery in status ${found.order.status}`)
    }
    persist()
    return HttpResponse.json<Schemas['OrderOut']>(view(found.order))
  }),

  http.post('*/api/sim/courier-event', async ({ request }) => {
    const body = (await request.json()) as Schemas['CourierEventRequest']
    const found = findOrder(body.order_id)
    if (!found) return problem(404, 'NOT_FOUND', `order ${body.order_id} not found`)
    found.order.courier_status = body.status
    addEvent(found.order, `COURIER_${body.status.toUpperCase()}`)
    if (body.status === 'in_transit' || body.status === 'delivered') found.dispatched = true
    if (found.order.status === 'HELD' && body.status === 'delivered') deliver(found.order, 'DELIVERED')
    if (found.order.status === 'HELD' && body.status === 'lost') {
      found.order.status = 'DISPUTABLE'
      addEvent(found.order, 'MARKED_DISPUTABLE_PARCEL_LOST')
    }
    persist()
    return HttpResponse.json<Schemas['OrderOut']>(view(found.order))
  }),

  http.post('*/api/sim/advance-clock', async ({ request }): Promise<Response> => {
    const { hours } = (await request.json()) as Schemas['AdvanceClockRequest']
    if (hours < 0) return problem(422, 'VALIDATION_ERROR', 'hours: must be >= 0')
    store.offsetMs += hours * 3_600_000
    const fired = processTimers()
    persist()
    return HttpResponse.json<Schemas['ClockOut']>({ now: iso(nowMs()), fired })
  }),

  http.post('*/api/demo/reset', async () => {
    resetStore()
    persist()
    return HttpResponse.json<Schemas['DemoResetOut']>({
      scenario_set: 'default',
      loaded: { sellers: SELLERS.length, buyers: 1 },
      now: iso(nowMs()),
    })
  }),

  http.post('*/api/disputes', async ({ request }) => {
    const body = (await request.json()) as Schemas['CreateDisputeRequest']
    const found = findOrder(body.order_id)
    if (!found) return problem(404, 'NOT_FOUND', `order ${body.order_id} not found`)
    if (!REPORTABLE.includes(found.order.status)) {
      return problem(409, 'ILLEGAL_STATE', `event DISPUTE_FILED is not allowed in status ${found.order.status}`)
    }
    store.disputeSeq += 1
    const id = `D-${String(store.disputeSeq).padStart(4, '0')}`
    const evidence: Schemas['DisputeOut']['evidence'] = body.evidence_text?.trim()
      ? [{ party: 'BUYER', description_text: body.evidence_text.trim(), created_at: iso(nowMs()) }]
      : []
    const dispute: Schemas['DisputeOut'] = {
      id,
      order_id: body.order_id,
      status: 'OPEN',
      opened_by: 'BUYER',
      claim_text: body.claim_text.trim(),
      claim_type: body.claim_type ?? null,
      opened_at: iso(nowMs()),
      seller_deadline: hoursFromNow(SELLER_DEADLINE_HOURS),
      seller_response_text: null,
      seller_responded_at: null,
      evidence,
    }
    store.disputes.set(id, dispute)
    found.order.status = 'DISPUTED'
    found.order.dispute_ids.push(id)
    addEvent(found.order, 'DISPUTE_FILED')
    persist()
    return HttpResponse.json<Schemas['DisputeOut']>(dispute, { status: 201 })
  }),

  http.get('*/api/disputes/:id', ({ params }) => {
    const dispute = store.disputes.get(String(params.id))
    if (!dispute) return problem(404, 'NOT_FOUND', `dispute ${String(params.id)} not found`)
    return HttpResponse.json<Schemas['DisputeOut']>(dispute)
  }),

  http.post('*/api/disputes/:id/seller-response', async ({ params, request }) => {
    const dispute = store.disputes.get(String(params.id))
    if (!dispute) return problem(404, 'NOT_FOUND', `dispute ${String(params.id)} not found`)
    if (dispute.status !== 'OPEN' && dispute.status !== 'SELLER_RESPONDED') {
      return problem(409, 'ILLEGAL_STATE', `the seller cannot respond in status ${dispute.status}`)
    }
    if (dispute.seller_deadline && nowMs() > Date.parse(dispute.seller_deadline)) {
      return problem(409, 'DEADLINE_PASSED', 'the seller response deadline has passed')
    }
    const body = (await request.json()) as Schemas['SellerResponseRequest']
    dispute.seller_response_text = body.response_text.trim()
    dispute.seller_responded_at = iso(nowMs())
    dispute.status = 'SELLER_RESPONDED'
    if (body.evidence_text?.trim()) {
      dispute.evidence.push({
        party: 'SELLER',
        description_text: body.evidence_text.trim(),
        created_at: iso(nowMs()),
      })
    }
    persist()
    return HttpResponse.json<Schemas['DisputeOut']>(dispute)
  }),

  http.post('*/api/disputes/:id/buyer-evidence', async ({ params, request }) => {
    const dispute = store.disputes.get(String(params.id))
    if (!dispute) return problem(404, 'NOT_FOUND', `dispute ${String(params.id)} not found`)
    const body = (await request.json()) as Schemas['BuyerEvidenceRequest']
    dispute.evidence.push({
      party: 'BUYER',
      description_text: body.evidence_text.trim(),
      created_at: iso(nowMs()),
    })
    persist()
    return HttpResponse.json<Schemas['DisputeOut']>(dispute)
  }),
  ...analystHandlers,
]
