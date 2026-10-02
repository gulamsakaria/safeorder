/**
 * The seller trust model in the browser: LightGBM trees (exported as plain arrays), exact tree
 * SHAP for the reasons, Platt calibration, the score, the band and the reason texts. A port of
 * backend/app/trust and backend/app/rules.py; the parity tests compare it with the Python code.
 */

import reasonsBn from '../../../backend/app/i18n/reasons_bn.json'
import reasonsEn from '../../../backend/app/i18n/reasons_en.json'
import { bnDigits, format, pyFixed, pyRound } from './py'

export interface Tree {
  feature: number[]
  threshold: number[]
  default_left: boolean[]
  missing: number[] // 0 none, 1 zero, 2 nan
  count: number[]
  left: number[] // >= 0 internal node, < 0 is ~leaf
  right: number[]
  leaf_value: number[]
  leaf_count: number[]
}

export interface TrustModelData {
  version: string
  feature_columns: string[]
  medians: Record<string, number>
  platt: [number, number]
  trees: Tree[]
}

export interface TrustRules {
  trusted_min: number
  caution_min: number
  limited_history_max_age_days: number
  limited_history_min_orders: number
  high_risk_requires_confirmation: boolean
  limited_history_override_max_score: number | null
}

export interface ReasonSettings {
  min: number
  max: number
  min_abs_contribution: number
}

export type Band = 'TRUSTED' | 'CAUTION' | 'HIGH_RISK' | 'LIMITED_HISTORY'

export interface Reason {
  key: string
  direction: string
  text_en: string
  text_bn: string
}

export interface TrustResult {
  score: number | null
  model_score: number
  band: Band
  limited_history: boolean
  reasons: Reason[]
  probability: number
  requires_extra_confirmation: boolean
}

const K_ZERO = 1e-35

// ---- trees ------------------------------------------------------------------------------------

/** LightGBM's numerical decision: true = go left. */
function goesLeft(tree: Tree, node: number, x: number[]): boolean {
  let value = x[tree.feature[node]]
  const missing = tree.missing[node]
  if (Number.isNaN(value) && missing !== 2) value = 0
  if ((missing === 1 && Math.abs(value) <= K_ZERO) || (missing === 2 && Number.isNaN(value))) {
    return tree.default_left[node]
  }
  return value <= tree.threshold[node]
}

function leafValue(tree: Tree, x: number[]): number {
  if (tree.feature.length === 0) return tree.leaf_value[0]
  let node = 0
  for (;;) {
    const next = goesLeft(tree, node, x) ? tree.left[node] : tree.right[node]
    if (next < 0) return tree.leaf_value[~next]
    node = next
  }
}

export function rawMargin(model: TrustModelData, x: number[]): number {
  let sum = 0
  for (const tree of model.trees) sum += leafValue(tree, x)
  return sum
}

interface PathElement {
  feature: number
  zero: number
  one: number
  weight: number
}

function extendPath(path: PathElement[], depth: number, zero: number, one: number, feature: number) {
  path[depth] = { feature, zero, one, weight: depth === 0 ? 1 : 0 }
  for (let i = depth - 1; i >= 0; i--) {
    path[i + 1].weight += (one * path[i].weight * (i + 1)) / (depth + 1)
    path[i].weight = (zero * path[i].weight * (depth - i)) / (depth + 1)
  }
}

function unwindPath(path: PathElement[], depth: number, index: number) {
  const one = path[index].one
  const zero = path[index].zero
  let next = path[depth].weight
  for (let i = depth - 1; i >= 0; i--) {
    if (one !== 0) {
      const tmp = path[i].weight
      path[i].weight = (next * (depth + 1)) / ((i + 1) * one)
      next = tmp - (path[i].weight * zero * (depth - i)) / (depth + 1)
    } else {
      path[i].weight = (path[i].weight * (depth + 1)) / (zero * (depth - i))
    }
  }
  for (let i = index; i < depth; i++) {
    path[i].feature = path[i + 1].feature
    path[i].zero = path[i + 1].zero
    path[i].one = path[i + 1].one
  }
}

function unwoundPathSum(path: PathElement[], depth: number, index: number): number {
  const one = path[index].one
  const zero = path[index].zero
  let next = path[depth].weight
  let total = 0
  for (let i = depth - 1; i >= 0; i--) {
    if (one !== 0) {
      const tmp = (next * (depth + 1)) / ((i + 1) * one)
      total += tmp
      next = path[i].weight - tmp * zero * ((depth - i) / (depth + 1))
    } else {
      total += path[i].weight / zero / ((depth - i) / (depth + 1))
    }
  }
  return total
}

function nodeCount(tree: Tree, child: number): number {
  return child < 0 ? tree.leaf_count[~child] : tree.count[child]
}

function treeShap(
  tree: Tree,
  x: number[],
  phi: number[],
  node: number,
  depth: number,
  parentPath: PathElement[],
  parentZero: number,
  parentOne: number,
  parentFeature: number,
) {
  const path = parentPath.slice(0, depth + 1).map((e) => ({ ...e }))
  extendPath(path, depth, parentZero, parentOne, parentFeature)
  if (node < 0) {
    const value = tree.leaf_value[~node]
    for (let i = 1; i <= depth; i++) {
      const w = unwoundPathSum(path, depth, i)
      const el = path[i]
      phi[el.feature] += w * (el.one - el.zero) * value
    }
    return
  }
  const feature = tree.feature[node]
  const left = goesLeft(tree, node, x)
  const hot = left ? tree.left[node] : tree.right[node]
  const cold = left ? tree.right[node] : tree.left[node]
  const total = tree.count[node]
  const hotZero = nodeCount(tree, hot) / total
  const coldZero = nodeCount(tree, cold) / total
  let incomingZero = 1
  let incomingOne = 1
  let depthNow = depth
  let found = -1
  for (let i = 0; i <= depth; i++) {
    if (path[i].feature === feature) {
      found = i
      break
    }
  }
  if (found >= 0) {
    incomingZero = path[found].zero
    incomingOne = path[found].one
    unwindPath(path, depth, found)
    depthNow -= 1
  }
  treeShap(tree, x, phi, hot, depthNow + 1, path, hotZero * incomingZero, incomingOne, feature)
  treeShap(tree, x, phi, cold, depthNow + 1, path, coldZero * incomingZero, 0, feature)
}

/** Exact per-feature contributions in log-odds (LightGBM's pred_contrib without the bias). */
export function contributions(model: TrustModelData, x: number[]): number[] {
  const phi = new Array<number>(model.feature_columns.length).fill(0)
  for (const tree of model.trees) {
    if (tree.feature.length === 0) continue // a single leaf only adds to the bias
    treeShap(tree, x, phi, 0, 0, [], 1, 1, -1)
  }
  return phi
}

// ---- rules ------------------------------------------------------------------------------------

export function scoreFromProbability(p: number): number {
  const raw = Math.floor(100 * (1 - p) + 0.5)
  return Math.max(0, Math.min(100, raw))
}

export function isLimitedHistory(ageDays: number, orders: number, rules: TrustRules): boolean {
  return ageDays < rules.limited_history_max_age_days || orders < rules.limited_history_min_orders
}

export function trustBand(score: number, ageDays: number, orders: number, rules: TrustRules): Band {
  if (isLimitedHistory(ageDays, orders, rules)) {
    const override = rules.limited_history_override_max_score
    if (override !== null && score <= override) return 'HIGH_RISK'
    return 'LIMITED_HISTORY'
  }
  if (score >= rules.trusted_min) return 'TRUSTED'
  if (score >= rules.caution_min) return 'CAUTION'
  return 'HIGH_RISK'
}

// ---- reasons ----------------------------------------------------------------------------------

type Catalog = { labels: Record<string, string>; reasons: Record<string, string>; units: Record<string, string> }
const CATALOG: Record<'en' | 'bn', Catalog> = { en: reasonsEn, bn: reasonsBn }

const RISK = 'risk'
const PROTECTIVE = 'protective'
const NEUTRAL = 'neutral'
const HIGH = 'high'
const LOW = 'low'
const ANY = 'any'

const REASON_KEYS: Record<string, string> = {}
for (const [feature, direction, level, key] of [
  ['account_age_days', RISK, LOW, 'ACCOUNT_VERY_NEW'],
  ['account_age_days', PROTECTIVE, HIGH, 'ACCOUNT_ESTABLISHED'],
  ['account_age_days', PROTECTIVE, LOW, 'YOUNG_BUT_NOT_A_WARNING'],
  ['orders_7d', RISK, HIGH, 'ORDER_SURGE_7D'],
  ['orders_7d', RISK, LOW, 'FEW_ORDERS_7D'],
  ['orders_7d', PROTECTIVE, HIGH, 'ACTIVE_RECENT_ORDERS'],
  ['orders_7d', PROTECTIVE, LOW, 'NO_ORDER_RUSH_7D'],
  ['orders_30d', RISK, HIGH, 'ORDER_SURGE_30D'],
  ['orders_30d', RISK, LOW, 'FEW_ORDERS_30D'],
  ['orders_30d', PROTECTIVE, HIGH, 'STEADY_ORDERS_30D'],
  ['orders_30d', PROTECTIVE, LOW, 'NO_ORDER_RUSH_30D'],
  ['unique_buyers_24h', RISK, HIGH, 'BUYER_BURST'],
  ['unique_buyers_24h', PROTECTIVE, ANY, 'NORMAL_DAILY_BUYERS'],
  ['unique_buyers_30d', RISK, HIGH, 'MANY_BUYERS_30D'],
  ['unique_buyers_30d', RISK, LOW, 'FEW_BUYERS_30D'],
  ['unique_buyers_30d', PROTECTIVE, HIGH, 'BROAD_CUSTOMER_BASE'],
  ['buyer_burst_ratio', RISK, HIGH, 'SUDDEN_BUYER_SPIKE'],
  ['buyer_burst_ratio', PROTECTIVE, ANY, 'STABLE_BUYER_FLOW'],
  ['repeat_buyer_ratio', RISK, LOW, 'FEW_REPEAT_BUYERS'],
  ['repeat_buyer_ratio', RISK, HIGH, 'REPEAT_BUYER_CIRCLE'],
  ['repeat_buyer_ratio', PROTECTIVE, HIGH, 'REPEAT_BUYERS'],
  ['buyer_concentration', RISK, HIGH, 'FEW_BUYERS_DOMINATE'],
  ['buyer_concentration', PROTECTIVE, ANY, 'ORDERS_SPREAD_OUT'],
  ['refund_rate', RISK, HIGH, 'HIGH_REFUND_RATE'],
  ['refund_rate', PROTECTIVE, ANY, 'LOW_REFUND_RATE'],
  ['dispute_rate', RISK, HIGH, 'HIGH_DISPUTE_RATE'],
  ['dispute_rate', PROTECTIVE, ANY, 'LOW_DISPUTE_RATE'],
  ['median_cashout_latency_min', RISK, LOW, 'FAST_CASHOUT'],
  ['median_cashout_latency_min', PROTECTIVE, HIGH, 'NORMAL_CASHOUT_RHYTHM'],
  ['median_cashout_latency_min', PROTECTIVE, LOW, 'CASHOUT_NOT_UNUSUAL'],
  ['ticket_vs_category_ratio', RISK, HIGH, 'HIGH_TICKET'],
  ['ticket_vs_category_ratio', PROTECTIVE, ANY, 'NORMAL_TICKET'],
  ['shared_buyer_overlap', RISK, HIGH, 'SHARED_BUYER_GROUP'],
  ['shared_buyer_overlap', PROTECTIVE, ANY, 'NO_SHARED_BUYERS'],
]) {
  REASON_KEYS[`${feature}|${direction}|${level}`] = key
}

const COUNT_FEATURES = new Set(['account_age_days', 'orders_7d', 'orders_30d', 'unique_buyers_24h', 'unique_buyers_30d'])
const PERCENT_FEATURES = new Set(['repeat_buyer_ratio', 'buyer_concentration', 'refund_rate', 'dispute_rate', 'shared_buyer_overlap'])
const TIMES_FEATURES = new Set(['buyer_burst_ratio', 'ticket_vs_category_ratio'])
const MINUTES_PER_HOUR = 60
const MINUTES_PER_DAY = 1440

function duration(minutes: number, lang: 'en' | 'bn'): string {
  const units = CATALOG[lang].units
  if (minutes < 120) return format(units.minutes, { n: Math.max(1, pyRound(minutes)) })
  if (minutes < 2 * MINUTES_PER_DAY) return format(units.hours, { n: pyRound(minutes / MINUTES_PER_HOUR) })
  return format(units.days, { n: pyRound(minutes / MINUTES_PER_DAY) })
}

function formatValue(feature: string, value: number, lang: 'en' | 'bn'): string {
  if (feature === 'median_cashout_latency_min') return duration(value, lang)
  if (COUNT_FEATURES.has(feature)) return String(pyRound(value))
  if (PERCENT_FEATURES.has(feature)) return String(pyRound(value * 100))
  if (TIMES_FEATURES.has(feature)) return pyFixed(value, 1)
  return pyFixed(value, 2)
}

function unitSuffix(feature: string, lang: 'en' | 'bn'): string {
  if (PERCENT_FEATURES.has(feature)) return '%'
  if (feature === 'account_age_days') return lang === 'en' ? ' days' : ' দিন'
  return ''
}

function selectKey(feature: string, direction: string, level: string): string {
  for (const candidate of [level, ANY]) {
    const key = REASON_KEYS[`${feature}|${direction}|${candidate}`]
    if (key) return key
  }
  return direction === RISK ? 'GENERIC_RISK' : 'GENERIC_PROTECTIVE'
}

function render(key: string, feature: string | null, value: number | null, lang: 'en' | 'bn'): string {
  const catalog = CATALOG[lang]
  const fields = { value: '', label: '' }
  if (feature !== null && value !== null) {
    fields.value = formatValue(feature, value, lang)
    fields.label = catalog.labels[feature]
    if (key.startsWith('GENERIC')) fields.value += unitSuffix(feature, lang)
  }
  const text = format(catalog.reasons[key], fields)
  return lang === 'bn' ? bnDigits(text) : text
}

export function buildReasons(
  values: Record<string, number>,
  contribution: Record<string, number>,
  medians: Record<string, number>,
  score: number,
  limitedHistory: boolean,
  rules: TrustRules,
  settings: ReasonSettings,
): Reason[] {
  const primary = score < rules.trusted_min ? RISK : PROTECTIVE
  const candidates: { other: number; neg: number; feature: string; direction: string }[] = []
  for (const [feature, c] of Object.entries(contribution)) {
    const value = values[feature]
    if (value === undefined || Number.isNaN(value) || c === 0) continue
    const direction = c > 0 ? RISK : PROTECTIVE
    candidates.push({ other: direction !== primary ? 1 : 0, neg: -Math.abs(c), feature, direction })
  }
  candidates.sort(
    (a, b) =>
      a.other - b.other ||
      a.neg - b.neg ||
      (a.feature < b.feature ? -1 : a.feature > b.feature ? 1 : 0) ||
      (a.direction < b.direction ? -1 : a.direction > b.direction ? 1 : 0),
  )
  const reasons: Reason[] = []
  if (limitedHistory) {
    reasons.push({
      key: 'LIMITED_HISTORY',
      direction: NEUTRAL,
      text_en: render('LIMITED_HISTORY', null, null, 'en'),
      text_bn: render('LIMITED_HISTORY', null, null, 'bn'),
    })
  }
  for (const { neg, feature, direction } of candidates) {
    if (reasons.length >= settings.max) break
    const strong = -neg >= settings.min_abs_contribution
    if (reasons.length >= settings.min && !strong) continue
    const level = values[feature] >= medians[feature] ? HIGH : LOW
    const key = selectKey(feature, direction, level)
    reasons.push({
      key,
      direction,
      text_en: render(key, feature, values[feature], 'en'),
      text_bn: render(key, feature, values[feature], 'bn'),
    })
  }
  return reasons
}

// ---- Trust Check ------------------------------------------------------------------------------

export function predictTrust(
  model: TrustModelData,
  features: Record<string, number | null>,
  orderCount: number,
  rules: TrustRules,
  settings: ReasonSettings,
): TrustResult {
  const values: Record<string, number> = {}
  for (const c of model.feature_columns) {
    const v = features[c]
    values[c] = v === null || v === undefined ? Number.NaN : v
  }
  const x = model.feature_columns.map((c) => values[c])
  const [a, b] = model.platt
  const probability = 1 / (1 + Math.exp(-(a * rawMargin(model, x) + b)))
  const modelScore = scoreFromProbability(probability)
  const age = values.account_age_days
  const band = trustBand(modelScore, age, orderCount, rules)
  const limited = isLimitedHistory(age, orderCount, rules)
  const phi = contributions(model, x)
  const byFeature = Object.fromEntries(model.feature_columns.map((c, i) => [c, phi[i]]))
  const reasons = buildReasons(values, byFeature, model.medians, modelScore, band === 'LIMITED_HISTORY', rules, settings)
  return {
    score: band === 'LIMITED_HISTORY' ? null : modelScore,
    model_score: modelScore,
    band,
    limited_history: limited,
    reasons,
    probability,
    requires_extra_confirmation: band === 'HIGH_RISK' && rules.high_risk_requires_confirmation,
  }
}
