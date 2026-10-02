/**
 * The evidence analyzer in the browser: injection screen, consistency flags, classifier, router,
 * timeline and the Bangla/English explanation. A port of backend/app/analyzer/*.py; the parity
 * tests compare every output with the Python result on the same cases.
 */

import explainBn from '../../../backend/app/i18n/explain_bn.json'
import explainEn from '../../../backend/app/i18n/explain_en.json'
import { predictProba } from './classifier'
import type { ClassifierModel } from './classifier'
import { bnDigits, format, pyLen, pyRound, pySplit } from './py'
import { buildText, detectNotReceived, extractAmounts, sanitize } from './text'

export interface DisputeCase {
  dispute_id: string
  order_id: string
  amount_bdt: number
  placed_at: string
  opened_at: string
  claim_text: string
  courier_events: [string, string][]
  code_confirmed_at: string | null
  claim_type: string | null
  seller_response_text: string | null
  seller_responded_at: string | null
  buyer_evidence: string[]
  seller_evidence: string[]
  buyer_disputes_in_window: number
}

export interface AnalyzerConfig {
  rules: {
    routing: {
      min_class_probability: number
      high_amount_bdt: number
      repeat_claimant_count: number
      repeat_claimant_window_days: number
      always_human_classes: string[]
    }
  }
  analyzer: {
    rules_version: string
    min_evidence_chars: number
    min_evidence_words: number
    late_report_hours: number
    amount_tolerance: number
    amount_bands_bdt: number[]
    proof_keywords: string[]
  }
}

export interface Flag {
  code: string
  detail: Record<string, number | string[]>
}

export interface Analysis {
  dispute_id: string
  order_id: string
  timeline: { t: string; event: string }[]
  class_probs: Record<string, number>
  flags: string[]
  injection_detected: boolean
  recommendation: string
  route: string
  route_reasons: string[]
  explanation_en: string
  explanation_bn: string
  explanation_sections: Record<'en' | 'bn', Record<string, string>>
  model_versions: Record<string, string>
  flag_details: Record<string, Record<string, number | string[]>>
}

const CLASSES = ['SELLER_FAULT', 'BUYER_FALSE_CLAIM', 'COURIER_ISSUE', 'INSUFFICIENT_EVIDENCE']
const RECOMMENDATIONS: Record<string, string> = {
  SELLER_FAULT: 'SUGGEST_REFUND_BUYER',
  BUYER_FALSE_CLAIM: 'SUGGEST_REJECT_CLAIM',
  COURIER_ISSUE: 'SUGGEST_COURIER_ISSUE',
  INSUFFICIENT_EVIDENCE: 'NEEDS_MORE_EVIDENCE',
}
const PROOF = ['in_transit', 'delivered', 'returned']
const SECONDS_PER_HOUR = 3600

const ms = (iso: string): number => Date.parse(iso)

export function toIso(value: number | string): string {
  const date = new Date(value)
  return date.toISOString().replace(/\.\d{3}Z$/, 'Z')
}

// ---- case facts -------------------------------------------------------------------------------

function courierStatus(c: DisputeCase): string {
  return c.courier_events.length ? c.courier_events[c.courier_events.length - 1][0] : 'not_dispatched'
}

function deliveredAt(c: DisputeCase): string | null {
  const hit = c.courier_events.find(([status]) => status === 'delivered')
  return hit ? hit[1] : null
}

// ---- consistency flags ------------------------------------------------------------------------

interface Texts {
  claim: string
  sellerResponse: string
  buyerEvidence: string[]
  sellerEvidence: string[]
}

function isVague(text: string, minChars: number, minWords: number): boolean {
  const stripped = text.trim()
  return pyLen(stripped) < minChars || pySplit(stripped).length < minWords
}

export function checkConsistency(c: DisputeCase, texts: Texts, cfg: AnalyzerConfig): Flag[] {
  const s = cfg.analyzer
  const routing = cfg.rules.routing
  const flags: Flag[] = []
  const delivered = deliveredAt(c)
  const claimType = c.claim_type ?? (detectNotReceived(texts.claim) ? 'NOT_RECEIVED' : null)
  if (delivered !== null && c.code_confirmed_at !== null && claimType === 'NOT_RECEIVED') {
    flags.push({ code: 'CODE_CONTRADICTION', detail: {} })
  }

  const dispatched = c.courier_events.some(([status]) => PROOF.includes(status))
  const sellerText = [texts.sellerResponse, ...texts.sellerEvidence].join(' ').toLowerCase()
  const hasProofText = s.proof_keywords.some((word) => sellerText.includes(word.toLowerCase()))
  if (!dispatched && !hasProofText) flags.push({ code: 'NO_COURIER_PROOF', detail: {} })

  const vague: string[] = []
  if (isVague(texts.buyerEvidence.join(' '), s.min_evidence_chars, s.min_evidence_words)) vague.push('BUYER')
  if (c.seller_responded_at !== null && isVague(texts.sellerEvidence.join(' '), s.min_evidence_chars, s.min_evidence_words)) {
    vague.push('SELLER')
  }
  if (vague.length) flags.push({ code: 'EVIDENCE_EMPTY_OR_VAGUE', detail: { parties: vague } })

  if (c.buyer_disputes_in_window >= routing.repeat_claimant_count) {
    flags.push({
      code: 'REPEAT_CLAIMANT',
      detail: { count: c.buyer_disputes_in_window, days: routing.repeat_claimant_window_days },
    })
  }

  const stated = [texts.claim, texts.sellerResponse, ...texts.buyerEvidence, ...texts.sellerEvidence].flatMap(extractAmounts)
  const tolerance = s.amount_tolerance * c.amount_bdt
  if (stated.length && !stated.some((a) => Math.abs(a - c.amount_bdt) <= tolerance)) {
    flags.push({ code: 'AMOUNT_MISMATCH', detail: { stated: pyRound(stated[0]), order_amount: c.amount_bdt } })
  }

  if (delivered !== null) {
    const hours = (ms(c.opened_at) - ms(delivered)) / 1000 / SECONDS_PER_HOUR
    if (hours > s.late_report_hours) flags.push({ code: 'LATE_REPORT', detail: { hours: pyRound(hours) } })
  }
  return flags
}

// ---- routing ----------------------------------------------------------------------------------

export function topClass(probs: Record<string, number>): [string, number] {
  let best = CLASSES[0]
  for (const c of CLASSES) if (probs[c] > probs[best]) best = c
  return [best, probs[best]]
}

export interface Routing {
  topClass: string
  topProbability: number
  recommendation: string
  route: string
  reasons: string[]
}

export function decideRoute(
  probs: Record<string, number>,
  amount: number,
  flags: string[],
  injection: boolean,
  cfg: AnalyzerConfig,
): Routing {
  const routing = cfg.rules.routing
  const [best, probability] = topClass(probs)
  const reasons: string[] = []
  if (routing.always_human_classes.includes(best)) reasons.push('INSUFFICIENT_EVIDENCE_PREDICTED')
  if (flags.length) reasons.push('FLAGS_PRESENT')
  if (injection) reasons.push('INJECTION_DETECTED')
  if (probability < routing.min_class_probability) reasons.push('LOW_CONFIDENCE')
  if (amount > routing.high_amount_bdt) reasons.push('HIGH_AMOUNT')
  return {
    topClass: best,
    topProbability: probability,
    recommendation: RECOMMENDATIONS[best],
    route: reasons.length ? 'HUMAN_REVIEW' : 'FAST_LANE_CONFIRM',
    reasons,
  }
}

// ---- timeline and explanation -----------------------------------------------------------------

export function buildTimeline(c: DisputeCase): { t: string; event: string }[] {
  const events: [string, string][] = [[c.placed_at, 'ORDER_PLACED_AND_HELD']]
  for (const [status, when] of c.courier_events) events.push([when, `COURIER_${status.toUpperCase()}`])
  if (c.code_confirmed_at !== null) events.push([c.code_confirmed_at, 'DELIVERY_CODE_CONFIRMED'])
  events.push([c.opened_at, 'BUYER_DISPUTE_FILED'])
  if (c.seller_responded_at !== null) events.push([c.seller_responded_at, 'SELLER_RESPONDED'])
  return events
    .map((event, index) => ({ event, index }))
    .sort((a, b) => ms(a.event[0]) - ms(b.event[0]) || a.index - b.index)
    .map(({ event }) => ({ t: toIso(event[0]), event: event[1] }))
}

type Templates = typeof explainEn
const TEMPLATES: Record<'en' | 'bn', Templates> = { en: explainEn, bn: explainBn as Templates }

function flagSentences(flag: Flag, lang: 'en' | 'bn'): string[] {
  const t = TEMPLATES[lang] as unknown as Record<string, Record<string, string>>
  const template = t.flags[flag.code]
  if (flag.code === 'EVIDENCE_EMPTY_OR_VAGUE') {
    return (flag.detail.parties as string[]).map((p) => format(template, { party: t.parties[p] }))
  }
  return [format(template, flag.detail as Record<string, string | number>)]
}

function utcStamp(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`
}

function explainLanguage(c: DisputeCase, flags: Flag[], routing: Routing, lang: 'en' | 'bn'): Record<string, string> {
  const t = TEMPLATES[lang] as unknown as Record<string, Record<string, string> & string>
  const text = TEMPLATES[lang] as unknown as Record<string, string>
  const status = courierStatus(c)
  const happened = [format(text.order, { amount: c.amount_bdt }), t.courier[status]]
  if (c.code_confirmed_at !== null || status === 'delivered') {
    happened.push(t.code[c.code_confirmed_at !== null ? 'used' : 'not_used'])
  }
  happened.push(format(text.dispute, { when: utcStamp(c.opened_at) }))
  happened.push(t.seller[c.seller_responded_at !== null ? 'responded' : 'pending'])

  const risky = flags.flatMap((f) => flagSentences(f, lang))
  if (risky.length === 0) risky.push(text.no_flags)
  risky.push(
    format(text.model, {
      percent: pyRound(routing.topProbability * 100),
      class_description: t.classes[routing.topClass],
    }),
  )
  const reasons = routing.reasons.map((r) => t.route_reasons[r]).join(text.reason_separator)
  const nextStep = [t.recommendation[routing.recommendation], format(t.route[routing.route], { reasons })]
  const sections: Record<string, string> = {
    what_happened: happened.join(' '),
    why_risky: risky.join(' '),
    next_step: nextStep.join(' '),
  }
  return Object.fromEntries(Object.entries(sections).map(([k, v]) => [k, lang === 'bn' ? bnDigits(v) : v]))
}

// ---- pipeline ---------------------------------------------------------------------------------

export function analyzeCase(
  c: DisputeCase,
  classifier: ClassifierModel,
  cfg: AnalyzerConfig,
): Analysis {
  const codes: string[] = []
  const clean = (text: string | null): string => {
    const [cleaned, found] = sanitize(text)
    codes.push(...found)
    return cleaned
  }
  const texts: Texts = {
    claim: clean(c.claim_text),
    sellerResponse: clean(c.seller_response_text),
    buyerEvidence: c.buyer_evidence.map(clean),
    sellerEvidence: c.seller_evidence.map(clean),
  }
  const injectionCodes = [...new Set(codes)].sort()
  const injection = injectionCodes.length > 0

  const flags = checkConsistency(c, texts, cfg)
  const classifierText = buildText(
    {
      courierStatus: courierStatus(c),
      codeUsed: c.code_confirmed_at !== null,
      amountBdt: c.amount_bdt,
      buyerClaim: texts.claim,
      sellerResponse: texts.sellerResponse,
      buyerEvidence: texts.buyerEvidence.join(' '),
      sellerEvidence: texts.sellerEvidence.join(' '),
    },
    cfg.analyzer.amount_bands_bdt,
  )
  const values = predictProba(classifier, classifierText)
  const probs = Object.fromEntries(CLASSES.map((cls) => [cls, values[classifier.data.classes.indexOf(cls)]]))
  const routing = decideRoute(probs, c.amount_bdt, flags.map((f) => f.code), injection, cfg)
  const allFlags = injection ? [...flags, { code: 'INJECTION_DETECTED', detail: {} }] : flags

  const sections = { en: explainLanguage(c, allFlags, routing, 'en'), bn: explainLanguage(c, allFlags, routing, 'bn') }
  const join = (lang: 'en' | 'bn') => {
    const headings = TEMPLATES[lang].headings as Record<string, string>
    return Object.entries(sections[lang])
      .map(([k, v]) => `${headings[k]}: ${v}`)
      .join('\n')
  }
  return {
    dispute_id: c.dispute_id,
    order_id: c.order_id,
    timeline: buildTimeline(c),
    class_probs: probs,
    flags: [...flags.map((f) => f.code), ...(injection ? ['INJECTION_DETECTED'] : [])],
    injection_detected: injection,
    recommendation: routing.recommendation,
    route: routing.route,
    route_reasons: routing.reasons,
    explanation_en: join('en'),
    explanation_bn: join('bn'),
    explanation_sections: sections,
    model_versions: { dispute: classifier.data.version, rules: cfg.analyzer.rules_version },
    flag_details: Object.fromEntries(flags.filter((f) => Object.keys(f.detail).length).map((f) => [f.code, f.detail])),
  }
}
