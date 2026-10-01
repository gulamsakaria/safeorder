import type { Schemas } from '../api/client'

const HOUR_MS = 3_600_000
export const HOLD_HOURS = 72
export const SELLER_DEADLINE_HOURS = 48
export const CODE_LENGTH = 6

type Reason = Schemas['ReasonOut']

export const SELLERS: Schemas['SellerPublic'][] = [
  { id: 'S-0001', display_name: 'Synthetic Shop 0001', wallet_no: 'SIM-W-S0001', category: 'shoes', created_at: '2024-08-12T00:00:00Z' },
  { id: 'S-0002', display_name: 'Synthetic Shop 0002', wallet_no: 'SIM-W-S0002', category: 'electronics', created_at: '2026-09-28T00:00:00Z' },
  { id: 'S-0003', display_name: 'Synthetic Shop 0003', wallet_no: 'SIM-W-S0003', category: 'clothing', created_at: '2026-09-24T00:00:00Z' },
  { id: 'S-0004', display_name: 'Synthetic Shop 0004', wallet_no: 'SIM-W-S0004', category: 'food', created_at: '2026-03-02T00:00:00Z' },
]

const reasons = {
  trusted: [
    { key: 'NORMAL_CASHOUT_RHYTHM', direction: 'protective', text_en: 'Money usually stays about 4 days before it is cashed out', text_bn: 'টাকা আসার পর তুলতে সাধারণত সময় লাগে প্রায় ৪ দিন' },
    { key: 'NORMAL_TICKET', direction: 'protective', text_en: 'Order prices are in line with this kind of product', text_bn: 'অর্ডারের দাম এই ধরনের পণ্যের স্বাভাবিক দামের কাছাকাছি' },
    { key: 'ACCOUNT_ESTABLISHED', direction: 'protective', text_en: 'Account has been active for 396 days', text_bn: 'অ্যাকাউন্টটি ৩৯৬ দিন ধরে সক্রিয়' },
  ],
  fake: [
    { key: 'BUYER_BURST', direction: 'risk', text_en: '62 different buyers paid in the last 24 hours', text_bn: 'গত ২৪ ঘণ্টায় ৬২ জন আলাদা ক্রেতা টাকা দিয়েছেন' },
    { key: 'FAST_CASHOUT', direction: 'risk', text_en: 'Money is cashed out within 12 minutes of arriving', text_bn: 'টাকা আসার পর তুলে নিতে সময় লাগে মাত্র ১২ মিনিট' },
    { key: 'ACCOUNT_VERY_NEW', direction: 'risk', text_en: 'Account is only 3 days old', text_bn: 'অ্যাকাউন্টটি মাত্র ৩ দিন আগে খোলা হয়েছে' },
  ],
  limited: [
    { key: 'LIMITED_HISTORY', direction: 'neutral', text_en: 'This seller is new or has few orders, so a reliable score cannot be given yet', text_bn: 'এই বিক্রেতা নতুন বা তাঁর অর্ডার কম, তাই এখনই নির্ভরযোগ্য স্কোর দেওয়া যাচ্ছে না' },
    { key: 'NO_ORDER_RUSH_7D', direction: 'protective', text_en: 'No sudden rush of orders in the last 7 days (1)', text_bn: 'গত ৭ দিনে হঠাৎ অর্ডারের চাপ নেই (১টি)' },
  ],
  caution: [
    { key: 'HIGH_DISPUTE_RATE', direction: 'risk', text_en: '9% of orders ended in a dispute', text_bn: '৯% অর্ডারে অভিযোগ উঠেছে' },
    { key: 'ACCOUNT_ESTABLISHED', direction: 'protective', text_en: 'Account has been active for 210 days', text_bn: 'অ্যাকাউন্টটি ২১০ দিন ধরে সক্রিয়' },
  ],
} satisfies Record<string, Reason[]>

function trust(
  id: string,
  score: number | null,
  band: Schemas['TrustBand'],
  list: Reason[],
  extra = false,
): Schemas['TrustCheckResponse'] {
  return {
    seller_id: id,
    score,
    band,
    limited_history: band === 'LIMITED_HISTORY',
    reasons: list,
    model_version: 'trust_v1',
    generated_at: '2026-10-01T09:00:00Z',
    requires_extra_confirmation: extra,
  }
}

export const TRUST: Record<string, Schemas['TrustCheckResponse']> = {
  'S-0001': trust('S-0001', 95, 'TRUSTED', reasons.trusted),
  'S-0002': trust('S-0002', 9, 'HIGH_RISK', reasons.fake, true),
  'S-0003': trust('S-0003', null, 'LIMITED_HISTORY', reasons.limited),
  'S-0004': trust('S-0004', 55, 'CAUTION', reasons.caution),
}

interface MockOrder {
  order: Schemas['OrderOut']
  code: string
  dispatched: boolean
}

export const store = {
  orders: new Map<string, MockOrder>(),
  disputes: new Map<string, Schemas['DisputeOut']>(),
  offsetMs: 0,
  orderSeq: 0,
  disputeSeq: 0,
}

const STORAGE_KEY = 'safeorder.mock.store'

/** Keeps the mock's state for this browser tab, so a page refresh does not wipe the demo. */
export function persist(): void {
  try {
    sessionStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        orders: [...store.orders.entries()],
        disputes: [...store.disputes.entries()],
        offsetMs: store.offsetMs,
        orderSeq: store.orderSeq,
        disputeSeq: store.disputeSeq,
      }),
    )
  } catch {
    // storage may be blocked; the mock then simply forgets on reload
  }
}

function restore(): void {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const saved = JSON.parse(raw)
    store.orders = new Map(saved.orders)
    store.disputes = new Map(saved.disputes)
    store.offsetMs = saved.offsetMs
    store.orderSeq = saved.orderSeq
    store.disputeSeq = saved.disputeSeq
  } catch {
    // an unreadable saved state is ignored
  }
}

export function resetStore(): void {
  store.orders.clear()
  store.disputes.clear()
  store.offsetMs = 0
  store.orderSeq = 0
  store.disputeSeq = 0
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}

restore()

export const nowMs = (): number => Date.now() + store.offsetMs
export const iso = (ms: number): string => new Date(ms).toISOString()
export const hoursFromNow = (h: number): string => iso(nowMs() + h * HOUR_MS)

export function addEvent(order: Schemas['OrderOut'], event: string): void {
  order.timeline.push({ t: iso(nowMs()), event })
}

export function transfer(
  order: Schemas['OrderOut'],
  from: Schemas['LedgerEntryOut']['account'],
  to: Schemas['LedgerEntryOut']['account'],
  reason: string,
): void {
  const created_at = iso(nowMs())
  order.ledger.push({ account: from, debit: order.amount_bdt, credit: 0, reason, created_at })
  order.ledger.push({ account: to, debit: 0, credit: order.amount_bdt, reason, created_at })
}

/** Fires the time-based events the real backend fires after the clock moves. */
export function processTimers(): { order_id: string; event: string }[] {
  const fired: { order_id: string; event: string }[] = []
  for (const { order, dispatched } of store.orders.values()) {
    if (order.status === 'DELIVERED' && order.hold_until && Date.parse(order.hold_until) <= nowMs()) {
      order.status = 'RELEASED'
      order.released_at = iso(nowMs())
      transfer(order, 'HOLD', 'SELLER_WALLET', 'HOLD_RELEASED')
      addEvent(order, 'HOLD_ENDED_FUNDS_RELEASED')
      fired.push({ order_id: order.id, event: 'HOLD_EXPIRED' })
    } else if (
      order.status === 'HELD' &&
      !dispatched &&
      Date.parse(order.placed_at) + HOLD_HOURS * HOUR_MS <= nowMs()
    ) {
      order.status = 'DISPUTABLE'
      addEvent(order, 'DISPATCH_DEADLINE_MISSED')
      fired.push({ order_id: order.id, event: 'DISPATCH_DEADLINE_MISSED' })
    }
  }
  return fired
}

export function deliveryCodeFor(seq: number): string {
  return String((seq * 7919 + 482913) % 10 ** CODE_LENGTH).padStart(CODE_LENGTH, '0')
}
