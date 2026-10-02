import { describe, expect, it } from 'vitest'
import classifier from '../../public/engine/classifier.json'
import patterns from '../../public/engine/patterns.json'
import fixtures from './fixtures/parity.json'
import { predictProba, prepareClassifier } from './classifier'
import type { ClassifierData } from './classifier'
import { setPatterns } from './text'
import type { Patterns } from './text'

setPatterns(patterns as unknown as Patterns)
const model = prepareClassifier(classifier as unknown as ClassifierData)

describe('dispute classifier parity with the Python code', () => {
  fixtures.classifier.forEach((fx, n) => {
    it(`text ${n}: ${JSON.stringify(fx.text).slice(0, 50)}`, () => {
      const probs = predictProba(model, fx.text)
      expect(probs).toHaveLength(4)
      fx.probs.forEach((expected, i) => expect(probs[i]).toBeCloseTo(expected, 7))
    })
  })
})
