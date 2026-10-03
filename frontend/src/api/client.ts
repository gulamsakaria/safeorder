import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type Schemas = components['schemas']

/** One switch decides the data source: VITE_USE_MOCK=true uses the in-browser mock server. */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
/** VITE_STATIC=true: no backend at all; the real models run in the browser (src/static). */
export const STATIC = import.meta.env.VITE_STATIC === 'true'

declare global {
  interface Window {
    SAFEORDER_API?: string
  }
}

/** A backend chosen at run time in config.js (for example a Render service); '' means none. */
export const RUNTIME_API: string = (globalThis.window?.SAFEORDER_API ?? '').trim().replace(/\/+$/, '')
/** True when the in-browser models answer: a static build and no backend address in config.js. */
export const IN_BROWSER = STATIC && RUNTIME_API === ''
/** An empty VITE_API_BASE_URL means the API is served from the same address as the page. */
export const API_BASE_URL: string = RUNTIME_API || (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000')
export const DEMO_CODE_KEY = 'safeorder.demoCode'
export const DEMO_BUYER_ID: string = import.meta.env.VITE_DEMO_BUYER_ID ?? 'B-000001'

export const api = createClient<paths>({
  // The mock intercepts requests to this same origin, so no other code changes between modes.
  baseUrl: API_BASE_URL || globalThis.location?.origin || '',
  // Look fetch up at call time: a mock installed after this module loaded must still be hit.
  fetch: async (request) =>
    IN_BROWSER ? (await import('../static/fetch')).staticFetch(request) : globalThis.fetch(request),
})

// The sandbox controls may be protected by a demo code (set on the server); send it when present.
api.use({
  onRequest({ request }) {
    const path = new URL(request.url).pathname
    if (path.startsWith('/api/demo') || path.startsWith('/api/sim')) {
      try {
        const code = sessionStorage.getItem(DEMO_CODE_KEY)
        if (code) request.headers.set('X-Demo-Code', code)
      } catch {
        // storage may be blocked; the request then goes without a code
      }
    }
    return request
  },
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
