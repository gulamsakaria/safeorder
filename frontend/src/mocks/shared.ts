import { HttpResponse } from 'msw'
import type { Schemas } from '../api/client'
import { HOLD_HOURS, addEvent, hoursFromNow, iso, nowMs, store } from './data'

export const REPORTABLE: Schemas['OrderStatus'][] = ['HELD', 'DELIVERED', 'DISPUTABLE']

export function problem(status: number, code: string, message: string) {
  return HttpResponse.json({ error: { code, message } }, { status })
}

export function view(order: Schemas['OrderOut'], code?: string): Schemas['OrderOut'] {
  return {
    ...order,
    can_report_problem: REPORTABLE.includes(order.status),
    server_time: iso(nowMs()),
    delivery_code: code ?? null,
    ledger_balanced:
      order.ledger.reduce((s, e) => s + e.debit, 0) === order.ledger.reduce((s, e) => s + e.credit, 0),
  }
}

export function findOrder(id: string) {
  return store.orders.get(id)
}

export function deliver(order: Schemas['OrderOut'], event: string) {
  order.status = 'DELIVERED'
  order.delivered_at = iso(nowMs())
  order.hold_until = hoursFromNow(HOLD_HOURS)
  addEvent(order, event)
}

