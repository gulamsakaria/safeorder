/**
 * Loads the exported models and data (public/engine/*.json) and offers the three things the
 * screens need without a backend: Trust Check, the evidence analysis, and the seller table.
 */

import { analyzeCase } from './analyzer'
import type { Analysis, AnalyzerConfig, DisputeCase } from './analyzer'
import { prepareClassifier } from './classifier'
import type { ClassifierData, ClassifierModel } from './classifier'
import { setPatterns } from './text'
import type { Patterns } from './text'
import { predictTrust } from './trust'
import type { ReasonSettings, TrustModelData, TrustResult, TrustRules } from './trust'

export interface SellerRow {
  id: string
  display_name: string
  wallet_no: string
  category: string
  created_at: string
  features: Record<string, number | null>
}

export interface BuyerRow {
  id: string
  display_name: string
  wallet_no: string
  created_at: string
}

export interface Scenarios {
  picks: Record<string, string>
  texts: Record<string, string>
  prior_claim_amounts: number[]
  analyst: string
  amounts: Record<string, number>
}

interface Config extends AnalyzerConfig {
  rules: AnalyzerConfig['rules'] & {
    hold_period_hours: number
    seller_response_deadline_hours: number
    dispatch_deadline_hours: number
    trust: TrustRules
  }
  trust_model: { version: string; reasons: ReasonSettings }
  api: { delivery_code_digits: number }
}

export interface Engine {
  config: Config
  trust: TrustModelData
  classifier: ClassifierModel
  sellers: SellerRow[]
  buyers: BuyerRow[]
  scenarios: Scenarios
  summary: unknown
  byId: Map<string, SellerRow>
}

let loaded: Engine | null = null

export function getEngine(): Engine {
  if (!loaded) throw new Error('the engine is not loaded yet')
  return loaded
}

export function isEngineLoaded(): boolean {
  return loaded !== null
}

export function installEngine(raw: {
  config: Config
  trust: TrustModelData
  classifier: ClassifierData
  patterns: Patterns
  sellers: { feature_columns: string[]; sellers: unknown[][]; buyers: BuyerRow[] }
  scenarios: Scenarios
  summary: unknown
}): Engine {
  setPatterns(raw.patterns)
  const columns = raw.sellers.feature_columns
  const sellers: SellerRow[] = raw.sellers.sellers.map((row) => ({
    id: row[0] as string,
    display_name: row[1] as string,
    wallet_no: row[2] as string,
    category: row[3] as string,
    created_at: row[4] as string,
    features: Object.fromEntries(columns.map((c, i) => [c, row[5 + i] as number | null])),
  }))
  loaded = {
    config: raw.config,
    trust: raw.trust,
    classifier: prepareClassifier(raw.classifier),
    sellers,
    buyers: raw.sellers.buyers,
    scenarios: raw.scenarios,
    summary: raw.summary,
    byId: new Map(sellers.map((s) => [s.id, s])),
  }
  return loaded
}

/** Fetches the exported files next to the page and installs the engine. */
export async function loadEngine(base = './engine/'): Promise<Engine> {
  const get = async <T>(name: string): Promise<T> => {
    const response = await fetch(`${base}${name}`)
    if (!response.ok) throw new Error(`could not load ${name}: ${response.status}`)
    return (await response.json()) as T
  }
  const [config, trust, classifier, patterns, sellers, scenarios, summary] = await Promise.all([
    get<Config>('config.json'),
    get<TrustModelData>('trust_model.json'),
    get<ClassifierData>('classifier.json'),
    get<Patterns>('patterns.json'),
    get<{ feature_columns: string[]; sellers: unknown[][]; buyers: BuyerRow[] }>('sellers.json'),
    get<Scenarios>('scenarios.json'),
    get<unknown>('summary.json'),
  ])
  return installEngine({ config, trust, classifier, patterns, sellers, scenarios, summary })
}

export interface Counters {
  orders_total: number
  refund_count: number
  dispute_count: number
}

/** Features of a seller after the counters changed by resolved disputes (see applyFeedback). */
export function effectiveFeatures(seller: SellerRow, counters?: Counters): Record<string, number | null> {
  const features = { ...seller.features }
  if (counters) {
    features.orders_total = counters.orders_total
    features.refund_count = counters.refund_count
    features.dispute_count = counters.dispute_count
    features.refund_rate = counters.refund_count / counters.orders_total
    features.dispute_rate = counters.dispute_count / counters.orders_total
  }
  return features
}

export function trustCheck(seller: SellerRow, counters?: Counters): TrustResult {
  const e = getEngine()
  const features = effectiveFeatures(seller, counters)
  return predictTrust(e.trust, features, features.orders_total ?? 0, e.config.rules.trust, e.config.trust_model.reasons)
}

/** The counters after one more resolved dispute (a refund counts as a refund and a dispute). */
export function nextCounters(seller: SellerRow, current: Counters | undefined, atFault: boolean): Counters {
  const base = current ?? {
    orders_total: seller.features.orders_total ?? 0,
    refund_count: seller.features.refund_count ?? 0,
    dispute_count: seller.features.dispute_count ?? 0,
  }
  return {
    orders_total: base.orders_total + 1,
    refund_count: base.refund_count + (atFault ? 1 : 0),
    dispute_count: base.dispute_count + (atFault ? 1 : 0),
  }
}

export function analyze(c: DisputeCase): Analysis {
  const e = getEngine()
  return analyzeCase(c, e.classifier, e.config)
}
