import { describe, expect, it } from 'vitest'
import classifier from '../../public/engine/classifier.json'
import config from '../../public/engine/config.json'
import patterns from '../../public/engine/patterns.json'
import fixtures from './fixtures/parity.json'
import { analyzeCase } from './analyzer'
import type { AnalyzerConfig, DisputeCase } from './analyzer'
import { prepareClassifier } from './classifier'
import type { ClassifierData } from './classifier'
import { sanitize, scan, setPatterns } from './text'
import type { Patterns } from './text'

setPatterns(patterns as unknown as Patterns)
const model = prepareClassifier(classifier as unknown as ClassifierData)
const cfg = config as unknown as AnalyzerConfig

describe('evidence analyzer parity with the Python code', () => {
  fixtures.analyzer.forEach((fx, n) => {
    it(`case ${n} (${fx.case.dispute_id})`, () => {
      const out = analyzeCase(fx.case as unknown as DisputeCase, model, cfg)
      const expected = fx.expected
      expect(out.flags).toEqual(expected.flags)
      expect(out.injection_detected).toBe(expected.injection_detected)
      expect(out.route).toBe(expected.route)
      expect(out.route_reasons).toEqual(expected.route_reasons)
      expect(out.recommendation).toBe(expected.recommendation)
      expect(out.timeline).toEqual(expected.timeline)
      expect(out.model_versions).toEqual(expected.model_versions)
      for (const [cls, p] of Object.entries(expected.class_probs)) expect(out.class_probs[cls]).toBeCloseTo(p as number, 7)
      expect(out.explanation_sections).toEqual(expected.explanation_sections)
      expect(out.explanation_en).toBe(expected.explanation_en)
      expect(out.explanation_bn).toBe(expected.explanation_bn)
      expect(out.flag_details).toEqual(expected.flag_details)
    })
  })

  fixtures.injection.forEach((fx, n) => {
    it(`injection screen ${n}: ${JSON.stringify(fx.text).slice(0, 40)}`, () => {
      expect(scan(fx.text)).toEqual(fx.scan)
      expect(sanitize(fx.text)).toEqual(fx.sanitized)
    })
  })
})
