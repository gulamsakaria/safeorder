/**
 * Text handling of the evidence analyzer: the prompt-injection screen, the "not received" claim
 * detector and the classifier input text. A port of backend/app/disputes/{injection,claim_type,
 * text_format}.py; the regular expressions come from the Python modules (public/engine/patterns.json).
 */

import { bnToAscii, pyRegex, pyStrip } from './py'

export interface Patterns {
  injection: [string, string, string][]
  negations: [string, string]
  sentence_break: string
  zero_width: string
  negation_lookback: number
  negation_sensitive: string[]
  not_received: [string, string][]
  amounts: [string, string][]
}

interface Compiled {
  injection: [string, RegExp][]
  negations: RegExp
  sentenceBreak: RegExp
  zeroWidth: RegExp
  lookback: number
  sensitive: Set<string>
  notReceived: RegExp[]
  amounts: RegExp[]
}

let compiled: Compiled | null = null

export function setPatterns(p: Patterns): void {
  const global = (source: string, flags: string) => {
    const re = pyRegex(source, flags)
    return new RegExp(re.source, `${re.flags}g`)
  }
  compiled = {
    injection: p.injection.map(([code, source, flags]) => [code, global(source, flags)]),
    negations: pyRegex(p.negations[0], p.negations[1]),
    sentenceBreak: pyRegex(p.sentence_break),
    zeroWidth: new RegExp(`[${p.zero_width}]`, 'gu'),
    lookback: p.negation_lookback,
    sensitive: new Set(p.negation_sensitive),
    notReceived: p.not_received.map(([source, flags]) => pyRegex(source, flags)),
    amounts: p.amounts.map(([source, flags]) => global(source, flags)),
  }
}

function patterns(): Compiled {
  if (!compiled) throw new Error('the engine patterns are not loaded')
  return compiled
}

export function normalize(text: string): string {
  const folded = text.normalize('NFKC').replace(patterns().zeroWidth, '').toLowerCase()
  return pyStrip(folded.replace(/\s+/gu, ' '))
}

/** Pattern codes found in one piece of text (empty when clean). */
export function scan(text: string): string[] {
  const c = patterns()
  const normalized = normalize(text || '')
  const found: string[] = []
  for (const [code, source] of c.injection) {
    const re = new RegExp(source.source, source.flags)
    for (let match = re.exec(normalized); match !== null; match = re.exec(normalized)) {
      if (match[0].length === 0) re.lastIndex += 1
      const before = normalized.slice(Math.max(0, match.index - c.lookback), match.index)
      if (c.sensitive.has(code) && c.negations.test(before)) continue
      found.push(code)
      break
    }
  }
  return found
}

/** The text without instruction-like sentences, and the codes found. */
export function sanitize(text: string | null | undefined): [string, string[]] {
  if (!text) return ['', []]
  const kept: string[] = []
  const codes: string[] = []
  for (const sentence of text.split(patterns().sentenceBreak)) {
    const hits = scan(sentence)
    if (hits.length > 0) codes.push(...hits)
    else kept.push(sentence)
  }
  return [pyStrip(kept.join(' ')), [...new Set(codes)].sort()]
}

export function detectNotReceived(text: string | null | undefined): boolean {
  if (!text) return false
  const normalized = text.normalize('NFKC')
  return patterns().notReceived.some((re) => re.test(normalized))
}

/** Amounts written next to a currency word or sign, in taka. */
export function extractAmounts(text: string): number[] {
  const folded = bnToAscii(text.normalize('NFKC'))
  const out: number[] = []
  for (const source of patterns().amounts) {
    const re = new RegExp(source.source, source.flags)
    for (let match = re.exec(folded); match !== null; match = re.exec(folded)) {
      const value = Number.parseFloat(match[1].replace(/,/g, ''))
      if (!Number.isNaN(value)) out.push(value)
    }
  }
  return out
}

// ---- classifier input ------------------------------------------------------------------------

const MISSING = 'NONE'
const THOUSAND = 1000

export function amountBand(amount: number, edges: number[]): string {
  if (amount < edges[0]) return `<${Math.floor(edges[0] / THOUSAND)}k`
  for (let i = 0; i + 1 < edges.length; i++) {
    if (edges[i] <= amount && amount < edges[i + 1]) {
      return `${Math.floor(edges[i] / THOUSAND)}k-${Math.floor(edges[i + 1] / THOUSAND)}k`
    }
  }
  return `>=${Math.floor(edges[edges.length - 1] / THOUSAND)}k`
}

function clean(text: string | null | undefined): string {
  const collapsed = pyStrip((text ?? '').replace(/\s+/gu, ' '))
  return collapsed || MISSING
}

export interface TextParts {
  courierStatus: string
  codeUsed: boolean
  amountBdt: number
  buyerClaim: string | null
  sellerResponse: string | null
  buyerEvidence: string | null
  sellerEvidence: string | null
}

export function buildText(parts: TextParts, bands: number[]): string {
  return (
    `[COURIER=${parts.courierStatus}] [CODE=${String(parts.codeUsed)}] ` +
    `[AMOUNT_BAND=${amountBand(parts.amountBdt, bands)}] ` +
    `BUYER: ${clean(parts.buyerClaim)} SELLER: ${clean(parts.sellerResponse)} ` +
    `BUYER_EVIDENCE: ${clean(parts.buyerEvidence)} SELLER_EVIDENCE: ${clean(parts.sellerEvidence)}`
  )
}
