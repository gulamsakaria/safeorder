import { api, unwrap } from '../api/client'
import type { Schemas } from '../api/client'

/** Typed calls of the wallet app. Each one maps to one endpoint of docs/openapi.json. */
export const wallet = {
  register: async (body: Schemas['RegisterRequest']) =>
    unwrap(await api.POST('/api/auth/register', { body })),
  login: async (body: Schemas['LoginRequest']) => unwrap(await api.POST('/api/auth/login', { body })),
  logout: async () => unwrap(await api.POST('/api/auth/logout')),
  me: async () => unwrap(await api.GET('/api/me')),
  sellerMode: async (body: Schemas['SellerModeRequest']) =>
    unwrap(await api.POST('/api/me/seller-mode', { body })),
  changePin: async (body: Schemas['ChangePinRequest']) =>
    unwrap(await api.POST('/api/me/pin', { body })),
  addMoney: async (amount: number) =>
    unwrap(await api.POST('/api/wallet/add-money', { body: { amount_bdt: amount } })),
  history: async () => unwrap(await api.GET('/api/wallet/history')),
  lookup: async (phone: string) =>
    unwrap(await api.GET('/api/wallet/lookup', { params: { query: { phone } } })),
  pay: async (body: Schemas['PayRequest']) => unwrap(await api.POST('/api/wallet/pay', { body })),
  orders: async (role: 'BUYER' | 'SELLER') =>
    unwrap(await api.GET('/api/my/orders', { params: { query: { role } } })),
  order: async (id: string) =>
    unwrap(await api.GET('/api/my/orders/{order_id}', { params: { path: { order_id: id } } })),
  proofImage: async (id: string) =>
    unwrap(
      await api.GET('/api/my/orders/{order_id}/proof-image', { params: { path: { order_id: id } } }),
    ),
  accept: async (id: string) =>
    unwrap(
      await api.POST('/api/my/orders/{order_id}/accept', { params: { path: { order_id: id } } }),
    ),
  report: async (id: string, body: Schemas['ReportRequest']) =>
    unwrap(
      await api.POST('/api/my/orders/{order_id}/report', {
        params: { path: { order_id: id } },
        body,
      }),
    ),
  claim: async (orderNo: string) =>
    unwrap(await api.POST('/api/seller/claim', { body: { order_no: orderNo } })),
  proof: async (id: string, body: Schemas['ProofRequest']) =>
    unwrap(
      await api.POST('/api/my/orders/{order_id}/proof', {
        params: { path: { order_id: id } },
        body,
      }),
    ),
  dispute: async (id: string) =>
    unwrap(await api.GET('/api/disputes/{dispute_id}', { params: { path: { dispute_id: id } } })),
  sellerResponse: async (id: string, responseText: string) =>
    unwrap(
      await api.POST('/api/disputes/{dispute_id}/seller-response', {
        params: { path: { dispute_id: id } },
        body: { response_text: responseText, evidence_text: '' },
      }),
    ),
  buyerEvidence: async (id: string, text: string) =>
    unwrap(
      await api.POST('/api/disputes/{dispute_id}/buyer-evidence', {
        params: { path: { dispute_id: id } },
        body: { evidence_text: text },
      }),
    ),
}

export const admin = {
  overview: async () => unwrap(await api.GET('/api/admin/overview')),
  users: async () => unwrap(await api.GET('/api/admin/users')),
  freeze: async (id: string, frozen: boolean) =>
    unwrap(
      await api.POST('/api/admin/users/{user_id}/freeze', {
        params: { path: { user_id: id } },
        body: { frozen },
      }),
    ),
  grant: async (id: string, amount: number) =>
    unwrap(
      await api.POST('/api/admin/users/{user_id}/grant', {
        params: { path: { user_id: id } },
        body: { amount_bdt: amount },
      }),
    ),
  orders: async (onlyOpen: boolean) =>
    unwrap(await api.GET('/api/admin/orders', { params: { query: { only_open: onlyOpen } } })),
  proofImage: async (id: string) =>
    unwrap(
      await api.GET('/api/admin/orders/{order_id}/proof-image', {
        params: { path: { order_id: id } },
      }),
    ),
  decide: async (id: string, decision: 'RELEASE_TO_SELLER' | 'REFUND_TO_BUYER', note: string) =>
    unwrap(
      await api.POST('/api/admin/orders/{order_id}/decision', {
        params: { path: { order_id: id } },
        body: { decision, note },
      }),
    ),
  advanceClock: async (hours: number) =>
    unwrap(await api.POST('/api/admin/advance-clock', { body: { hours } })),
}
