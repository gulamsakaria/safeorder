import { useI18n } from '../i18n/useI18n'
import { formatRemaining } from '../lib/format'
import { useServerNow } from '../lib/serverClock'

/** Time left until `targetIso`, measured on the server's simulated clock. */
export function Countdown({
  targetIso,
  serverTimeIso,
  endedText,
}: {
  targetIso: string
  serverTimeIso: string | undefined
  endedText: string
}) {
  const { lang } = useI18n()
  const now = useServerNow(serverTimeIso)
  const units =
    lang === 'bn'
      ? { d: 'দিন', h: 'ঘণ্টা', m: 'মিনিট', s: 'সেকেন্ড' }
      : { d: 'd', h: 'h', m: 'min', s: 's' }
  const text = formatRemaining(Date.parse(targetIso) - now, lang, units)
  return (
    <span data-testid="countdown" className="text-xl font-bold tabular-nums">
      {text ?? endedText}
    </span>
  )
}
