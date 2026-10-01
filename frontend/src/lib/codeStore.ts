/** The sandbox delivery code is shown once; keep it for this browser tab so a refresh does not lose it. */
const memory = new Map<string, string>()
const keyOf = (orderId: string) => `safeorder.code.${orderId}`

export function rememberCode(orderId: string, code: string): void {
  memory.set(orderId, code)
  try {
    sessionStorage.setItem(keyOf(orderId), code)
  } catch {
    // storage may be unavailable; the in-memory copy still works for this page view
  }
}

export function recallCode(orderId: string): string | undefined {
  try {
    return sessionStorage.getItem(keyOf(orderId)) ?? memory.get(orderId)
  } catch {
    return memory.get(orderId)
  }
}
