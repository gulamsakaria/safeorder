import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type Schemas = components['schemas']

/** One switch decides the data source: VITE_USE_MOCK=true uses the in-browser mock server. */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
export const DEMO_BUYER_ID: string = import.meta.env.VITE_DEMO_BUYER_ID ?? 'B-000001'

export const api = createClient<paths>({
  // The mock intercepts requests to this same origin, so no other code changes between modes.
  baseUrl: API_BASE_URL,
  // Look fetch up at call time: a mock installed after this module loaded must still be hit.
  fetch: (request) => globalThis.fetch(request),
})

export class ApiProblem extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response }

/** Unwraps an openapi-fetch result: returns the data or throws an ApiProblem with the API error. */
export function unwrap<T>(result: Result<T>): T {
  if (result.data !== undefined) return result.data
  const body = result.error as { error?: { code?: string; message?: string } } | undefined
  throw new ApiProblem(
    result.response.status,
    body?.error?.code ?? 'UNKNOWN',
    body?.error?.message ?? 'Request failed',
  )
}
