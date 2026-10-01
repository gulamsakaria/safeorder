import { useEffect, useState } from 'react'

const TICK_MS = 1000

/**
 * The server's simulated "now", kept ticking between fetches. The server time is sent with every
 * order, so a fast-forwarded demo clock is respected without any client-side guessing.
 *
 * The local clock is read only inside the interval callback (never during render); a newly
 * fetched server time re-anchors the estimate, so the drift is at most one tick.
 */
export function useServerNow(serverTimeIso: string | undefined): number {
  const [localNow, setLocalNow] = useState(() => Date.now())
  const [anchor, setAnchor] = useState(() => ({
    iso: serverTimeIso,
    server: serverTimeIso ? Date.parse(serverTimeIso) : localNow,
    local: localNow,
  }))

  if (serverTimeIso && serverTimeIso !== anchor.iso) {
    setAnchor({ iso: serverTimeIso, server: Date.parse(serverTimeIso), local: localNow })
  }

  useEffect(() => {
    const id = setInterval(() => setLocalNow(Date.now()), TICK_MS)
    return () => clearInterval(id)
  }, [])

  return anchor.server + (localNow - anchor.local)
}
