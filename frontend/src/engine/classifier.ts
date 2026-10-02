/**
 * The dispute classifier in the browser: TF-IDF (word 1-2 grams and character 2-5 grams) +
 * logistic regression + sigmoid calibration. A port of backend/app/disputes/baseline.py working
 * on the weights exported by scripts/export_static.py (public/engine/classifier.json).
 */

import { WORD_CHARS, pyLen, pySplit } from './py'

interface Vocabulary {
  terms: string[]
  idf: number[]
  ngram_range: [number, number]
}

export interface ClassifierData {
  version: string
  classes: string[]
  word: Vocabulary
  char: Vocabulary
  coef: number[][]
  intercept: number[]
  calibrators: { a: number; b: number }[]
}

export interface ClassifierModel {
  data: ClassifierData
  wordIndex: Map<string, number>
  charIndex: Map<string, number>
}

export function prepareClassifier(data: ClassifierData): ClassifierModel {
  const index = (terms: string[]) => new Map(terms.map((term, i) => [term, i]))
  return { data, wordIndex: index(data.word.terms), charIndex: index(data.char.terms) }
}

function wordTerms(text: string, range: [number, number]): string[] {
  const tokens = text.toLowerCase().match(WORD_CHARS) ?? []
  const terms = [...tokens]
  for (let n = Math.max(2, range[0]); n < Math.min(range[1] + 1, tokens.length + 1); n++) {
    for (let i = 0; i < tokens.length - n + 1; i++) terms.push(tokens.slice(i, i + n).join(' '))
  }
  return terms
}

function charTerms(text: string, range: [number, number]): string[] {
  const normalized = text.toLowerCase().replace(/\s\s+/gu, ' ')
  const terms: string[] = []
  for (const word of pySplit(normalized)) {
    const w = Array.from(` ${word} `)
    const length = w.length
    for (let n = range[0]; n <= range[1]; n++) {
      let offset = 0
      terms.push(w.slice(offset, offset + n).join(''))
      while (offset + n < length) {
        offset += 1
        terms.push(w.slice(offset, offset + n).join(''))
      }
      if (offset === 0) break // a short word counts once
    }
  }
  return terms
}

/** Sublinear TF x IDF, L2-normalised, as a sparse map from feature index to weight. */
function vectorize(terms: string[], index: Map<string, number>, idf: number[]): Map<number, number> {
  const counts = new Map<number, number>()
  for (const term of terms) {
    const i = index.get(term)
    if (i !== undefined) counts.set(i, (counts.get(i) ?? 0) + 1)
  }
  const vector = new Map<number, number>()
  let norm = 0
  for (const [i, count] of counts) {
    const value = (1 + Math.log(count)) * idf[i]
    vector.set(i, value)
    norm += value * value
  }
  norm = Math.sqrt(norm)
  if (norm > 0) for (const [i, value] of vector) vector.set(i, value / norm)
  return vector
}

/** Calibrated probabilities in the fixed class order. */
export function predictProba(model: ClassifierModel, text: string): number[] {
  const { data } = model
  const word = vectorize(wordTerms(text, data.word.ngram_range), model.wordIndex, data.word.idf)
  const char = vectorize(charTerms(text, data.char.ngram_range), model.charIndex, data.char.idf)
  const offset = data.word.terms.length
  const calibrated = data.classes.map((_, c) => {
    let score = data.intercept[c]
    for (const [i, v] of word) score += data.coef[c][i] * v
    for (const [i, v] of char) score += data.coef[c][offset + i] * v
    const { a, b } = data.calibrators[c]
    return 1 / (1 + Math.exp(a * score + b))
  })
  const total = calibrated.reduce((s, p) => s + p, 0)
  return total === 0 ? calibrated.map(() => 1 / calibrated.length) : calibrated.map((p) => p / total)
}

export { pyLen }
