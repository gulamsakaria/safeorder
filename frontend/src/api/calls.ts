import { api, unwrap } from './client'
import type { Schemas } from './client'

/** Typed calls used by the screens. Each one maps to one endpoint of docs/openapi.json. */
export const calls = {
  searchSellers: async (q: string) =>
    unwrap(await api.GET('/api/sellers/search', { params: { query: { q } } })),

  trustCheck: async (sellerId: string) =>
    unwrap(await api.POST('/api/trust/check', { body: { seller_id: sellerId } })),

  createOrder: async (body: Schemas['CreateOrderRequest']) =>
    unwrap(await api.POST('/api/orders', { body })),

  getOrder: async (orderId: string) =>
    unwrap(await api.GET('/api/orders/{order_id}', { params: { path: { order_id: orderId } } })),

  confirmDelivery: async (orderId: string, code: string) =>
    unwrap(
      await api.POST('/api/orders/{order_id}/confirm-delivery', {
        params: { path: { order_id: orderId } },
        body: { code },
      }),
    ),

  createDispute: async (body: Schemas['CreateDisputeRequest']) =>
    unwrap(await api.POST('/api/disputes', { body })),

  getDispute: async (disputeId: string) =>
    unwrap(
      await api.GET('/api/disputes/{dispute_id}', { params: { path: { dispute_id: disputeId } } }),
    ),

  sellerResponse: async (disputeId: string, body: Schemas['SellerResponseRequest']) =>
    unwrap(
      await api.POST('/api/disputes/{dispute_id}/seller-response', {
        params: { path: { dispute_id: disputeId } },
        body,
      }),
    ),

  buyerEvidence: async (disputeId: string, evidenceText: string) =>
    unwrap(
      await api.POST('/api/disputes/{dispute_id}/buyer-evidence', {
        params: { path: { dispute_id: disputeId } },
        body: { evidence_text: evidenceText },
      }),
    ),

  courierEvent: async (orderId: string, status: Schemas['CourierStatus']) =>
    unwrap(await api.POST('/api/sim/courier-event', { body: { order_id: orderId, status } })),

  advanceClock: async (hours: number) =>
    unwrap(await api.POST('/api/sim/advance-clock', { body: { hours } })),

  demoReset: async () =>
    unwrap(await api.POST('/api/demo/reset', { body: { scenario_set: 'default' } })),
}
