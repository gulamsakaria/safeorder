import { useEffect, useState } from 'react'
import { API_BASE_URL, RUNTIME_API } from './client'

export type BackendStatus = 'ready' | 'waking' | 'down'
const POLL_MS = 3000
const GIVE_UP_MS = 120_000

/**
 * With a backend chosen in config.js (a free Render service falls asleep when idle and needs up to a
 * minute to wake), this polls /health and tells the layout whether to show a "waking up" notice.
 * Without a backend address it is always 'ready'.
 */
export function useBackendStatus(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>(RUNTIME_API ? 'waking' : 'ready')
  useEffect(() => {
    if (!RUNTIME_API) return
    let cancelled = false
    const started = Date.now()
    const check = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`, { cache: 'no-store' })
        if (!cancelled && response.ok) {
          setStatus('ready')
          return
        }
      } catch {
        // the server is still starting, or unreachable
      }
      if (cancelled) return
      if (Date.now() - started > GIVE_UP_MS) setStatus('down')
      else setTimeout(() => void check(), POLL_MS)
    }
    void check()
    return () => {
      cancelled = true
    }
  }, [])
  return status
}
