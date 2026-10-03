import { useEffect, useState } from 'react'
import { RUNTIME_API, STATIC } from './client'

export type SameOriginBackend = 'checking' | 'yes' | 'no'

/** True when `GET /health` on this address answers {"status":"ok"} (the page was served by the API). */
export async function probeSameOrigin(fetcher: typeof fetch = fetch): Promise<boolean> {
  try {
    const response = await fetcher('/health', { cache: 'no-store' })
    if (!response.ok) return false
    const body: unknown = await response.json()
    return typeof body === 'object' && body !== null && (body as { status?: unknown }).status === 'ok'
  } catch {
    return false // plain web hosting answers with a page or an error, not with our JSON
  }
}

/**
 * A static build with no backend address in config.js can still be served by the SafeOrder server
 * itself (python run_local.py, Docker). This asks the page's own address once. When a backend is
 * named in config.js, or the build is not static, there is nothing to ask and the answer is 'yes'.
 */
export function useSameOriginBackend(): SameOriginBackend {
  const needed = STATIC && !RUNTIME_API
  const [state, setState] = useState<SameOriginBackend>(needed ? 'checking' : 'yes')
  useEffect(() => {
    if (!needed) return
    let cancelled = false
    void probeSameOrigin().then((ok) => {
      if (!cancelled) setState(ok ? 'yes' : 'no')
    })
    return () => {
      cancelled = true
    }
  }, [needed])
  return state
}
