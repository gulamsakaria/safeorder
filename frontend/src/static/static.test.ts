import { beforeAll, describe, expect, it } from 'vitest'
import classifier from '../../public/engine/classifier.json'
import config from '../../public/engine/config.json'
import patterns from '../../public/engine/patterns.json'
import scenarios from '../../public/engine/scenarios.json'
import sellers from '../../public/engine/sellers.json'
import summary from '../../public/engine/summary.json'
import trust from '../../public/engine/trust_model.json'
import type { ClassifierData } from '../engine/classifier'
import { installEngine } from '../engine/engine'
import type { Scenarios } from '../engine/engine'
import type { Patterns } from '../engine/text'
import type { TrustModelData } from '../engine/trust'
import { resetStore } from '../mocks/data'
import { staticFetch } from './fetch'
import { installSellers } from './handlers'

async function api<T = any>(method: string, path: string, body?: unknown): Promise<{ status: number; body: T }> {
  const response = await staticFetch(
    new Request(`http://localhost/api${path}`, {
      method,
      headers: { 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  )
  return { status: response.status, body: (await response.json()) as T }
}

beforeAll(() => {
  installEngine({
    config: config as never,
    trust: trust as unknown as TrustModelData,
    classifier: classifier as unknown as ClassifierData,
    patterns: patterns as unknown as Patterns,
    sellers: sellers as never,
    scenarios: scenarios as unknown as Scenarios,
    summary,
  })
  installSellers()
  resetStore()
})

describe('the static site answers the whole API in the browser', () => {
  it('searches the 3,000 synthetic sellers and runs the real trust model', async () => {
    const found = await api('GET', '/sellers/search?q=Synthetic%20Shop%201411')
    expect(found.body).toHaveLength(1)
    const fake = await api('POST', '/trust/check', { seller_id: scenarios.picks.fake })
    expect(fake.body.band).toBe('HIGH_RISK')
    expect(fake.body.requires_extra_confirmation).toBe(true)
    expect(fake.body.reasons.length).toBeGreaterThanOrEqual(2)
    const fresh = await api('POST', '/trust/check', { seller_id: scenarios.picks.new })
    expect(fresh.body.band).toBe('LIMITED_HISTORY')
    expect(fresh.body.score).toBeNull()
    const honest = await api('POST', '/trust/check', { seller_id: scenarios.picks.happy })
    expect(honest.body.band).toBe('TRUSTED')
    expect((await api('POST', '/trust/check', { seller_id: 'S-9999' })).status).toBe(404)
  })

  it('shows the evaluation summary exactly as the evaluation scripts wrote it', async () => {
    const metrics = await api('GET', '/metrics/summary')
    expect(metrics.body.available).toBe(true)
    expect(metrics.body.summary).toEqual(summary)
  })

  it('loads the seven demo scenarios and analyses three of them with the real classifier', async () => {
    const reset = await api('POST', '/demo/reset', { scenario_set: 'demo' })
    const by = Object.fromEntries(reset.body.scenarios.map((s: any) => [s.key, s]))
    expect(reset.body.scenarios.map((s: any) => s.number)).toEqual([1, 2, 3, 4, 5, 6, 7])
    expect(['seller_fault', 'false_claim', 'injection'].map((k) => by[k].analysis)).toEqual(['done', 'done', 'done'])

    const falseClaim = await api('GET', `/analyst/disputes/${by.false_claim.dispute_id}`)
    const analysis = falseClaim.body.analysis
    expect(analysis.flags).toEqual(expect.arrayContaining(['CODE_CONTRADICTION', 'REPEAT_CLAIMANT']))
    expect(analysis.route).toBe('HUMAN_REVIEW')
    expect(analysis.model_versions.dispute).toBe('dispute_baseline_v1')

    const injection = await api('GET', `/analyst/disputes/${by.injection.dispute_id}`)
    expect(injection.body.analysis.injection_detected).toBe(true)
    expect(injection.body.analysis.route).toBe('HUMAN_REVIEW')

    const queue = await api('GET', '/analyst/queue')
    expect(queue.body.map((q: any) => q.dispute_id).sort()).toEqual(
      ['seller_fault', 'false_claim', 'injection'].map((k) => by[k].dispute_id).sort(),
    )
  })

  it('a refund updates the seller score with the real model and the books balance', async () => {
    const reset = await api('POST', '/demo/reset', { scenario_set: 'demo' })
    const fault = reset.body.scenarios.find((s: any) => s.key === 'seller_fault')
    const decision = await api('POST', `/analyst/disputes/${fault.dispute_id}/decision`, {
      decision: 'REFUND_BUYER',
      note: 'seller never shipped',
      analyst_id: 'tester',
    })
    expect(decision.body.order_status).toBe('REFUNDED')
    expect(decision.body.ledger_balanced).toBe(true)
    expect(decision.body.trust.after.score).toBeLessThan(decision.body.trust.before.score)
    const history = await api('GET', `/sellers/${fault.seller_id}/score-history`)
    expect(history.body.snapshots.map((s: any) => s.trigger)).toEqual(['INITIAL', 'DISPUTE_RESOLVED'])
    const again = await api('POST', `/analyst/disputes/${fault.dispute_id}/decision`, {
      decision: 'REFUND_BUYER',
      note: 'again',
      analyst_id: 'tester',
    })
    expect(again.status).toBe(409)
  })

  it('the happy path releases the held money after the hold period', async () => {
    const reset = await api('POST', '/demo/reset', { scenario_set: 'demo' })
    const happy = reset.body.scenarios.find((s: any) => s.key === 'happy_path')
    const confirmed = await api('POST', `/orders/${happy.order_id}/confirm-delivery`, { code: happy.delivery_code })
    expect(confirmed.body.status).toBe('DELIVERED')
    await api('POST', '/sim/advance-clock', { hours: 72 })
    const order = await api('GET', `/orders/${happy.order_id}`)
    expect(order.body.status).toBe('RELEASED')
    expect(order.body.ledger_balanced).toBe(true)
  })

  it("a judge's own words get probabilities that sum to one, a recommendation and a route", async () => {
    const reset = await api('POST', '/demo/reset', { scenario_set: 'demo' })
    const judge = reset.body.scenarios.find((s: any) => s.key === 'judge_case')
    const filed = await api('POST', '/disputes', {
      order_id: judge.order_id,
      claim_text: 'পণ্য এখনো হাতে পাইনি, কুরিয়ার ফোন ধরছে না।',
      evidence_text: '',
    })
    expect(filed.status).toBe(201)
    const analysis = await api('POST', `/disputes/${filed.body.id}/analyze`, {})
    const total = Object.values(analysis.body.class_probs as Record<string, number>).reduce((a, b) => a + b, 0)
    expect(total).toBeCloseTo(1, 9)
    expect(['HUMAN_REVIEW', 'FAST_LANE_CONFIRM']).toContain(analysis.body.route)
    expect(analysis.body.explanation_sections.bn.what_happened).toMatch(/টাকার/)
  })

  it('unknown routes answer 404 in the normal error format', async () => {
    const missing = await api('GET', '/nothing/here')
    expect(missing.status).toBe(404)
    expect(missing.body.error.code).toBe('NOT_FOUND')
  })
})
