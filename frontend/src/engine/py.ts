/**
 * Small helpers that make JavaScript behave like the Python the models were written in, so the
 * browser gives the same answers as the backend (checked by the parity tests).
 */

const WORD = '\\p{L}\\p{N}_' // Python's \w: letters, digits and underscore (marks are not included)

/** Python's round(): halves go to the even neighbour. */
export function pyRound(value: number): number {
  const floor = Math.floor(value)
  const diff = value - floor
  if (diff < 0.5) return floor
  if (diff > 0.5) return floor + 1
  return floor % 2 === 0 ? floor : floor + 1
}

/** Python's f"{value:.{digits}f}": correctly rounded, ties to even. */
export function pyFixed(value: number, digits: number): string {
  const scaled = value * 10 ** digits
  const floor = Math.floor(scaled)
  const exactTie = scaled - floor === 0.5 && Number.isFinite(scaled) && Math.abs(scaled) < 2 ** 52
  if (exactTie) {
    const even = floor % 2 === 0 ? floor : floor + 1
    return (even / 10 ** digits).toFixed(digits)
  }
  return value.toFixed(digits)
}

/** str.format with named fields: replaces {name} with the value. */
export function format(template: string, fields: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in fields ? String(fields[name]) : whole,
  )
}

const BN_DIGITS = '০১২৩৪৫৬৭৮৯'
export function bnDigits(text: string): string {
  return text.replace(/[0-9]/g, (d) => BN_DIGITS[Number(d)])
}
export function bnToAscii(text: string): string {
  return text.replace(/[০-৯]/g, (d) => String(BN_DIGITS.indexOf(d)))
}

/** Number of code points (Python's len). */
export function pyLen(text: string): number {
  let n = 0
  for (const _ of text) n += 1 // eslint-disable-line @typescript-eslint/no-unused-vars
  return n
}

/** Python's str.split(): split on whitespace, no empty parts. */
export function pySplit(text: string): string[] {
  return text.split(/\s+/u).filter((part) => part.length > 0)
}

/** Python's str.strip() for whitespace. */
export function pyStrip(text: string): string {
  return text.replace(/^\s+|\s+$/gu, '')
}

/**
 * Convert the source of a Python (re) pattern to a JavaScript RegExp with the same meaning on
 * Unicode text: \\b, \\w, \\W and \\d follow Python (\\w excludes combining marks).
 */
export function pyRegex(source: string, flags = ''): RegExp {
  let out = ''
  let inClass = false
  for (let i = 0; i < source.length; i++) {
    const ch = source[i]
    if (ch === '\\') {
      const next = source[i + 1]
      i += 1
      if (next === 'b' && !inClass) {
        out += `(?:(?<=[${WORD}])(?![${WORD}])|(?<![${WORD}])(?=[${WORD}]))`
      } else if (next === 'w') {
        out += inClass ? WORD : `[${WORD}]`
      } else if (next === 'W') {
        out += inClass ? '' : `[^${WORD}]`
      } else if (next === 'd') {
        out += '\\p{Nd}'
      } else {
        out += `\\${next}`
      }
      continue
    }
    if (ch === '[' && !inClass) inClass = true
    else if (ch === ']' && inClass) inClass = false
    out += ch
  }
  return new RegExp(out, `${flags}u`)
}

export const WORD_CHARS = new RegExp(`[${WORD}]+`, 'gu')

/** Python's str.lower() for the characters that matter here. */
export function pyLower(text: string): string {
  return text.toLowerCase()
}
