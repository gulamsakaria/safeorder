import { describe, expect, it } from 'vitest'
import config from '../../public/engine/config.json'
import trustModel from '../../public/engine/trust_model.json'
import fixtures from './fixtures/parity.json'
import { contributions, predictTrust, rawMargin } from './trust'
import type { TrustModelData } from './trust'

const model = trustModel as unknown as TrustModelData
const rules = config.rules.trust
const settings = config.trust_model.reasons

describe('trust model parity with the Python code', () => {
  for (const fx of fixtures.trust) {
    it(`${fx.seller_id}: margin, contributions, score, band and reasons`, () => {
      const x = model.feature_columns.map((c) => {
        const v = (fx.values as Record<string, number | null>)[c]
        return v === null ? Number.NaN : v
      })
      expect(rawMargin(model, x)).toBeCloseTo(fx.margin, 8)
      const phi = contributions(model, x)
      fx.contributions.forEach((expected, i) => expect(phi[i]).toBeCloseTo(expected, 8))
      const result = predictTrust(model, fx.values as Record<string, number | null>, fx.order_count, rules, settings)
      expect(result.probability).toBeCloseTo(fx.probability, 8)
      expect(result.model_score).toBe(fx.model_score)
      expect(result.score).toBe(fx.score)
      expect(result.band).toBe(fx.band)
      expect(result.limited_history).toBe(fx.limited_history)
      expect(result.reasons).toEqual(fx.reasons)
    })
  }
})
