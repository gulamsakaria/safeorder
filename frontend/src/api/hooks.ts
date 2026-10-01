import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiProblem } from './client'

export interface AsyncState<T> {
  data: T | undefined
  error: ApiProblem | undefined
  loading: boolean
  reload: () => void
}

function asProblem(error: unknown): ApiProblem {
  if (error instanceof ApiProblem) return error
  return new ApiProblem(0, 'NETWORK', error instanceof Error ? error.message : 'network error')
}

/** Loads data on mount and whenever `deps` change; optional polling keeps a page fresh. */
export function useAsync<T>(
  load: () => Promise<T>,
  deps: unknown[],
  pollMs?: number,
): AsyncState<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<ApiProblem>()
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const loader = useRef(load)
  useEffect(() => {
    loader.current = load
  })

  useEffect(() => {
    let cancelled = false
    const run = (first: boolean) => {
      if (first) setLoading(true)
      loader
        .current()
        .then((result) => {
          if (cancelled) return
          setData(result)
          setError(undefined)
        })
        .catch((e: unknown) => {
          if (!cancelled) setError(asProblem(e))
        })
        .finally(() => {
          if (!cancelled && first) setLoading(false)
        })
    }
    run(true)
    const id = pollMs ? setInterval(() => run(false), pollMs) : undefined
    return () => {
      cancelled = true
      if (id) clearInterval(id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version, pollMs])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  return { data, error, loading, reload }
}

export interface ActionState<A extends unknown[], R> {
  run: (...args: A) => Promise<R | undefined>
  pending: boolean
  error: ApiProblem | undefined
  clearError: () => void
}

/** Wraps a button action: tracks pending and error state, never throws into the component. */
export function useAction<A extends unknown[], R>(
  action: (...args: A) => Promise<R>,
): ActionState<A, R> {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiProblem>()
  // Always call the latest action: it reads form state that changes between renders.
  const latest = useRef(action)
  useEffect(() => {
    latest.current = action
  })
  const run = useCallback(
    async (...args: A) => {
      setPending(true)
      setError(undefined)
      try {
        return await latest.current(...args)
      } catch (e) {
        setError(asProblem(e))
        return undefined
      } finally {
        setPending(false)
      }
    },
    [],
  )
  return { run, pending, error, clearError: () => setError(undefined) }
}
